from dataclasses import replace
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from test_direct_runtime import ExampleOutput, response

from hilo.acompanamiento.variantes import (
    AGENTE_UNICO,
    SoloControlesEnCodigo,
    UnSoloAgente,
)
from hilo.compartido.contracts import (
    CandidateResponse,
    HandoffContract,
    ProjectState,
    Verdict,
)
from hilo.config import Settings
from hilo.web import create_app


def settings():
    return replace(
        Settings.from_env(), base_url="http://127.0.0.1:18083/v1", api_key="test", thinking=True,
    )


def handoff():
    return HandoffContract(
        intent="Aplicar PESTEL", phase="Descubrimiento", stage=1, expertise="novel",
        recommendations=[{"tool_id": "pestel", "reason": "Pedida"}], active_tool="pestel",
        context_summary="Reto declarado.", kind="trabajo",
    )


def candidate(message):
    return CandidateResponse(
        message=message, tool_id="pestel", next_step="Preguntar por el factor político",
        source_sections=["Qué es"], template_updates=[],
    )


def test_code_only_verifier_never_calls_the_model_and_keeps_the_code_checks():
    client = Mock()
    runtime = SoloControlesEnCodigo(settings(), client=client)
    state = ProjectState(notebook_id="a", stage=1, phase="Descubrimiento")
    card = "# PESTEL\n## Qué es\nFactores del entorno."

    ok = runtime.verify(candidate("¿Qué factor político afecta tu reto?"), handoff(), card,
                        message="Quiero un PESTEL", state=state)
    two = runtime.verify(candidate("¿Qué factor político? ¿Y cuál económico?"), handoff(), card,
                         message="Quiero un PESTEL", state=state)

    assert ok.verdict == Verdict.APPROVED
    assert two.verdict == Verdict.REJECTED  # dos preguntas: lo detecta el código
    client.chat.completions.create.assert_not_called()


def test_single_agent_keeps_one_instruction_and_one_growing_context_per_turn(monkeypatch):
    client = Mock()
    client.chat.completions.create.return_value = response({"value": "ok"})
    runtime = UnSoloAgente(settings(), client=client)

    runtime._run("orchestrator", "Elige la ficha", ExampleOutput)
    runtime._run("methodologist", "Guía con la ficha", ExampleOutput)

    messages = client.chat.completions.create.call_args.kwargs["messages"]
    assert [m["role"] for m in messages] == ["system", "user", "assistant", "user"]
    assert messages[0]["content"] == AGENTE_UNICO
    assert messages[1]["content"] == "Elige la ficha"
    assert messages[-1]["content"] == "Guía con la ficha"
    # Un turno nuevo empieza sin la conversación anterior.
    monkeypatch.setattr(SoloControlesEnCodigo, "orchestrate", lambda *args: None)
    runtime.orchestrate("Otro turno", None, "{}")
    assert runtime.conversation == []


def test_web_uses_the_configured_variant_and_rejects_unknown_ones(tmp_path):
    base = replace(
        settings(), memory_path=tmp_path / "n.sqlite3", checkpoint_path=tmp_path / "c.sqlite3",
        audit_path=tmp_path / "v.jsonl",
    )
    app = create_app(base, model_probe=lambda _: True, require_auth=False)
    with TestClient(app) as client:
        assert client.get("/api/status").json()["variant"] == "g"
    with pytest.raises(ValueError, match="RUTA_DIA_VARIANTE"):
        create_app(replace(base, variant="b"), model_probe=lambda _: True, require_auth=False)


def test_single_agent_keeps_tree_and_notes_roles_apart():
    client = Mock()
    client.chat.completions.create.return_value = response({"value": "ok"})
    runtime = UnSoloAgente(settings(), client=client)
    runtime._run("tree_reviewer", "Revisa el árbol", ExampleOutput)
    messages = client.chat.completions.create.call_args.kwargs["messages"]
    assert messages[0]["content"] != AGENTE_UNICO and runtime.conversation == []
