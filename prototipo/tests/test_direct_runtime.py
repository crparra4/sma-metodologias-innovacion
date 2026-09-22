import json
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock

from pydantic import BaseModel

from ruta_dia_agents.config import Settings
from ruta_dia_agents.contracts import ProjectContext, ProjectState
from ruta_dia_agents.direct_runtime import DirectOpenAIRuntime
from ruta_dia_agents.knowledge import KnowledgeCatalog


class ExampleOutput(BaseModel):
    value: str


def response(payload):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(payload)))],
        usage=None,
    )


def test_direct_runtime_uses_local_json_schema_without_crewai_execution():
    client = Mock()
    client.chat.completions.create.return_value = response({"value": "ok"})
    settings = replace(
        Settings.from_env(),
        base_url="http://127.0.0.1:18083/v1",
        api_key="test",
        thinking=True,
    )
    runtime = DirectOpenAIRuntime(settings, client=client)

    result = runtime._run("orchestrator", "Devuelve el valor", ExampleOutput)

    assert result.value == "ok"
    options = client.chat.completions.create.call_args.kwargs
    assert options["response_format"]["type"] == "json_schema"
    assert options["extra_body"]["chat_template_kwargs"]["enable_thinking"] is False
    assert options["max_tokens"] == 384


def test_direct_verifier_receives_the_larger_reasoning_budget():
    client = Mock()
    client.chat.completions.create.return_value = response({"value": "ok"})
    settings = replace(
        Settings.from_env(),
        base_url="http://127.0.0.1:18083/v1",
        api_key="test",
        thinking=True,
    )
    runtime = DirectOpenAIRuntime(settings, client=client)

    runtime._run("verifier", "Audita", ExampleOutput)

    options = client.chat.completions.create.call_args.kwargs
    assert options["extra_body"]["chat_template_kwargs"]["enable_thinking"] is True
    assert options["max_tokens"] == 1536


def test_explicit_request_corrects_a_model_that_keeps_the_old_tool():
    client = Mock()
    client.chat.completions.create.return_value = response({
        "selection": "1:cinco-porques",
        "intent": "Continuar cinco porqués",
        "expertise": "novel",
        "context_summary": "Seguir con la ficha anterior",
        "reason": "Mantener la herramienta",
    })
    settings = replace(Settings.from_env(), base_url="http://127.0.0.1:18083/v1", api_key="test")
    runtime = DirectOpenAIRuntime(settings, client=client)
    catalog = KnowledgeCatalog(settings.route_path)
    handoff = runtime.orchestrate(
        "Quiero aplicar PESTEL para analizar el entorno de este proyecto.",
        ProjectState(active_tool="cinco-porques", recent_turns=["Asistente: ¿Por qué ocurre?"]),
        catalog.route_index(),
    )
    assert handoff.active_tool == "pestel"
    assert handoff.stage == 1


def test_prompt_includes_declared_context_without_promoting_hypotheses_to_facts():
    client = Mock()
    client.chat.completions.create.return_value = response({
        "selection": "1:pestel", "intent": "Explorar entorno", "expertise": "novel",
        "context_summary": "Consulta inicial", "reason": "Entorno",
    })
    runtime = DirectOpenAIRuntime(
        replace(Settings.from_env(), base_url="http://127.0.0.1:18083/v1", api_key="test"),
        client=client,
    )
    state = ProjectState(
        context=ProjectContext(
            question="Reducir las llegadas tarde", hypothesis="El bus es la causa",
        ),
        shared_context=["Ana guardó el avance: entrevistar a estudiantes."],
    )
    runtime.orchestrate(
        "Continuemos", state, KnowledgeCatalog(runtime.settings.route_path).route_index()
    )
    prompt = client.chat.completions.create.call_args.kwargs["messages"][-1]["content"]
    assert "Reducir las llegadas tarde" in prompt
    assert "Ana guardó el avance: entrevistar a estudiantes." in prompt
    assert "no prueban causas ni resultados" in prompt
    assert "El bus es la causa" not in state.context.stated_context()
