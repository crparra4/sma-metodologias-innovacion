import json
from dataclasses import replace
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

from ruta_dia_agents import web
from ruta_dia_agents.config import Settings
from ruta_dia_agents.respaldo_claude import Gasto, Respaldo, costo, esquema_para_claude
from ruta_dia_agents.variantes import PlanificadorConControles
from ruta_dia_agents.web import create_app, origen_del_turno


class Salida(BaseModel):
    message: str = Field(max_length=40)


class ClaudeFalso:
    """Imita `client.beta.messages.create`: devuelve en orden los textos de la lista."""

    def __init__(self, *textos, stop_reason="end_turn"):
        self.textos = list(textos)
        self.stop_reason = stop_reason
        self.pedidos = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self.create))

    def create(self, **pedido):
        self.pedidos.append(pedido)
        texto = self.textos.pop(0) if len(self.textos) > 1 else self.textos[0]
        return SimpleNamespace(
            model=pedido["model"], stop_reason=self.stop_reason,
            content=[SimpleNamespace(type="text", text=texto)],
            usage=SimpleNamespace(input_tokens=1000, output_tokens=100,
                                  cache_read_input_tokens=0, cache_creation_input_tokens=0),
        )


@pytest.fixture
def settings(tmp_path):
    return replace(
        Settings.from_env(), memory_path=tmp_path / "n.sqlite3",
        checkpoint_path=tmp_path / "c.sqlite3", audit_path=tmp_path / "a.jsonl",
        base_url="http://127.0.0.1:18083/v1", api_key="t", respaldo_claude=True,
        claude_gasto_path=tmp_path / "gasto.jsonl", claude_tope_usd=1.0,
    )


def test_schema_drops_what_the_api_does_not_accept():
    esquema = esquema_para_claude(Salida)
    assert "maxLength" not in json.dumps(esquema)
    assert esquema["additionalProperties"] is False


def test_spend_is_priced_per_model_saved_and_capped(settings):
    uso = SimpleNamespace(input_tokens=1_000_000, output_tokens=0)
    assert costo("claude-opus-5-5", uso) == 4.0 and costo("claude-sonnet-5-5", uso) == 2.0
    gasto = Gasto(settings.claude_gasto_path, tope=1.0)
    gasto.registrar("orchestrator", "claude-sonnet-5-5",
                    SimpleNamespace(input_tokens=400_000, output_tokens=0))
    assert gasto.disponible()
    gasto.registrar("methodologist", "claude-opus-5-5",
                    SimpleNamespace(input_tokens=100_000, output_tokens=0))
    assert not gasto.disponible()
    assert Gasto(settings.claude_gasto_path, tope=1.0).total == pytest.approx(1.2)


def test_each_agent_uses_its_model_and_the_planner_still_runs(settings):
    claude = ClaudeFalso(json.dumps({"message": "¿Qué pasa en lo político?"}))
    runtime = Respaldo(settings, cliente=claude).runtime(PlanificadorConControles, settings)
    assert isinstance(runtime, PlanificadorConControles)
    runtime._run("methodologist", "tarea", Salida)
    runtime._run("orchestrator", "tarea", Salida)
    assert [p["model"] for p in claude.pedidos] == ["claude-opus-5-5", "claude-sonnet-5-5"]
    pedido = claude.pedidos[0]
    assert pedido["fallbacks"] == "default" and pedido["output_config"]["effort"] == "low"
    assert pedido["output_config"]["format"]["type"] == "json_schema"
    assert [c["modelo"] for c in runtime.calls] == ["claude-opus-5-5", "claude-sonnet-5-5"]
    assert origen_del_turno(runtime.calls) == "claude"


def test_an_answer_that_breaks_the_contract_is_asked_again(settings):
    claude = ClaudeFalso(json.dumps({"message": "x" * 80}), json.dumps({"message": "Bien"}))
    runtime = Respaldo(settings, cliente=claude).runtime(PlanificadorConControles, settings)
    assert runtime._run("methodologist", "tarea", Salida).message == "Bien"
    assert len(claude.pedidos) == 2


def test_a_refusal_is_an_error_not_an_answer(settings):
    claude = ClaudeFalso("", stop_reason="refusal")
    runtime = Respaldo(settings, cliente=claude).runtime(PlanificadorConControles, settings)
    with pytest.raises(RuntimeError, match="declinó"):
        runtime._run("orchestrator", "tarea", Salida)


def test_turn_origin():
    assert origen_del_turno([]) == "ninguno"
    assert origen_del_turno([{"modelo": "Qwen3.5-4B-Q4_K_M"}]) == "local"


def _app(settings, monkeypatch, claude, local):
    monkeypatch.setattr(web, "Respaldo", lambda s: Respaldo(s, cliente=claude))
    return create_app(settings, model_probe=lambda _: local, require_auth=False)


def test_status_reports_who_would_answer(settings, monkeypatch):
    with TestClient(_app(settings, monkeypatch, ClaudeFalso("{}"), local=False)) as client:
        estado = client.get("/api/status").json()
        assert estado["available"] and estado["modelo"] == "claude"
    with TestClient(_app(settings, monkeypatch, ClaudeFalso("{}"), local=True)) as client:
        assert client.get("/api/status").json()["modelo"] == "local"
    Gasto(settings.claude_gasto_path, 1.0).registrar(
        "orchestrator", "claude-opus-5-5", SimpleNamespace(input_tokens=300_000, output_tokens=0))
    with TestClient(_app(settings, monkeypatch, ClaudeFalso("{}"), local=False)) as client:
        estado = client.get("/api/status").json()
        assert not estado["available"] and estado["modelo"] is None


def test_the_simulated_client_answers_through_claude_when_the_local_model_is_off(
        settings, monkeypatch):
    claude = ClaudeFalso("Pues voy a la oficina cada mes.")
    with TestClient(_app(settings, monkeypatch, claude, local=False)) as client:
        client.post("/api/notebooks", json={"notebook_id": "p", "context": {
            "question": "Pensionados que no usan la app del fondo"}})
        practica = client.post("/api/projects/p/practicas", json={
            "persona": "Don Hernando, 67 años, pensionado de Ibagué."}).json()
        respuesta = client.post(f"/api/projects/p/practicas/{practica['id']}/mensajes",
                                json={"texto": "¿Cómo hace hoy sus trámites?"}).json()
    assert respuesta["respuesta"] == "Pues voy a la oficina cada mes."
    assert claude.pedidos[0]["model"] == "claude-sonnet-5-5"
    assert "Don Hernando" in claude.pedidos[0]["system"]


ORQUESTADOR = {"selection": "1:cinco-porques", "intent": "recomendacion", "kind": "trabajo",
               "expertise": "novel", "context_summary": "Bajaron las ventas de la tienda.",
               "reason": "Pide aplicar los cinco porqués."}
METODOLOGO = {"message": "¿Por qué han bajado las ventas en tu tienda de barrio?",
              "tool_id": "cinco-porques", "next_step": "Preguntar el primer porqué",
              "source_sections": ["Qué es", "Cómo se usa (paso a paso)"],
              "template_updates": []}


class ClaudePorRol(ClaudeFalso):
    """El Metodólogo va con Opus y el Orquestador con Sonnet: responde según el modelo."""

    def create(self, **pedido):
        self.textos = [json.dumps(METODOLOGO if "opus" in pedido["model"] else ORQUESTADOR)]
        return super().create(**pedido)


def test_a_chat_turn_with_the_local_model_off_is_answered_and_recorded_as_claude(
        settings, monkeypatch):
    claude = ClaudePorRol("")
    mensaje = ("Quiero aplicar los cinco porqués. En mi tienda de barrio las ventas bajaron "
               "este semestre y todavía no he investigado por qué. Ayúdame con el primer paso.")
    with TestClient(_app(settings, monkeypatch, claude, local=False)) as client:
        respuesta = client.post("/api/chat", json={"notebook_id": "tienda", "message": mensaje})
        eventos = [json.loads(linea[6:]) for linea in respuesta.text.splitlines()
                   if linea.startswith("data: ")]
        final = eventos[-1]
        assert final["type"] == "result", final
        assert final["result"]["modelo"] == "claude"
        assert {f["agente"]: f["modelo"] for f in final["consumo"]} == {
            "Orquestador": "claude-sonnet-5-5", "Metodólogo": "claude-opus-5-5"}
        cuaderno = client.get("/api/notebooks/tienda").json()
    assert cuaderno["turns"][-1]["metadata"]["modelo"] == "claude"
    assert Gasto(settings.claude_gasto_path, 1.0).total > 0
