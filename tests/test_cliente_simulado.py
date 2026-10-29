import re
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from hilo.config import Settings
from hilo.conocimiento.knowledge import KnowledgeCatalog
from hilo.practica.cliente_simulado import (
    REGLAS,
    instruccion_personaje,
    responder,
    retroalimentacion,
    revisar_pregunta,
)
from hilo.practica.registro import RegistroPracticas
from hilo.proyectos.memory import NotebookMemory
from hilo.web import create_app

PERSONA = "Don Hernando, 67 años, pensionado de Ibagué; desconfía de poner la clave en el celular."


def codigos(pregunta):
    return [r.codigo for r in revisar_pregunta(pregunta)]


def test_every_rule_quotes_the_field_work_card_literally():
    card = KnowledgeCatalog(Settings.from_env().route_path).tool_card("trabajo-de-campo")
    texto = re.sub(r"\s+", " ", card)
    for regla in REGLAS:
        assert regla.cita in texto, regla.codigo


@pytest.mark.parametrize("pregunta,esperado", [
    ("Cuéntame de la última vez que fuiste a la oficina.", ["historia"]),
    ("¿Cómo se sintió cuando le pidieron la clave?", ["historia"]),
    ("¿Usarías una app para ver tu certificado?", ["hipotetica", "si_no"]),
    ("¿No sería genial hacerlo desde el celular?", ["dirigida", "si_no"]),
    ("¿Normalmente cómo haces tus trámites?", ["generalidad"]),
    ("¿Tienes celular?", ["si_no"]),
    ("Yo creo que la app es confusa, ¿verdad?", ["dirigida", "si_no", "opinion"]),
])
def test_questions_are_classified_with_the_card_rules(pregunta, esperado):
    assert codigos(pregunta) == esperado


def test_feedback_counts_problems_and_keeps_the_quote():
    retro = retroalimentacion(["¿Tienes celular?", "Cuéntame de la última vez que fuiste.",
                               "¿Usarías la app?"])
    assert retro["preguntas"] == 3 and retro["sin_problemas"] == 1
    sino = next(c for c in retro["consejos"] if c["nombre"] == "Pregunta de sí o no")
    assert sino["veces"] == 2 and "sí/no" in sino["cita"]
    assert "no es evidencia" in retro["aviso"]


def test_the_simulated_client_only_knows_its_character():
    instruccion = instruccion_personaje(PERSONA, "Pensionados que no usan la app")
    assert "Don Hernando" in instruccion and "Pensionados" in instruccion
    for metodo in ("ficha", "PESTEL", "Metodólogo", "Orquestador", "mapa de empatía"):
        assert metodo not in instruccion


def test_the_client_hears_the_whole_interview():
    client = Mock()
    client.chat.completions.create.return_value = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="Pues voy a la oficina."))])
    turnos = [{"rol": "entrevistador", "texto": "Hola"}, {"rol": "cliente", "texto": "Hola"}]
    assert responder(client, "m", PERSONA, "reto", turnos, "¿Cómo hace sus trámites?") == (
        "Pues voy a la oficina.")
    mensajes = client.chat.completions.create.call_args.kwargs["messages"]
    assert [m["role"] for m in mensajes] == ["system", "user", "assistant", "user"]


@pytest.fixture
def app(tmp_path):
    class Runtime:
        def __init__(self, settings):
            self.client = Mock()
            self.client.chat.completions.create.return_value = SimpleNamespace(choices=[
                SimpleNamespace(message=SimpleNamespace(content="Uy, sí, claro que la usaría."))])

    settings = replace(
        Settings.from_env(), memory_path=tmp_path / "n.sqlite3",
        checkpoint_path=tmp_path / "c.sqlite3", audit_path=tmp_path / "a.jsonl",
        base_url="http://127.0.0.1:18083/v1", api_key="t",
    )
    return create_app(settings, runtime_factory=Runtime, model_probe=lambda _: True,
                      require_auth=False), settings


def test_practice_flow_never_touches_the_project_record(app):
    aplicacion, settings = app
    with TestClient(aplicacion) as client:
        client.post("/api/notebooks", json={"notebook_id": "p", "context": {
            "question": "Pensionados que no usan la app del fondo"}})
        practica = client.post("/api/projects/p/practicas", json={"persona": PERSONA}).json()
        assert "no es evidencia" in practica["aviso"]
        respuesta = client.post(f"/api/projects/p/practicas/{practica['id']}/mensajes",
                                json={"texto": "¿Usarías una app para tu certificado?"}).json()
        assert respuesta["respuesta"] == "Uy, sí, claro que la usaría."
        assert {e["nombre"] for e in respuesta["revision"]["evitar"]} == {
            "Pregunta hipotética", "Pregunta de sí o no"}
        vista = client.get(f"/api/projects/p/practicas/{practica['id']}").json()
        assert [t["rol"] for t in vista["turnos"]] == ["entrevistador", "cliente"]
        assert vista["retro"]["preguntas"] == 1
        cuaderno = client.get("/api/notebooks/p").json()
        assert cuaderno["turns"] == [] and cuaderno["state"]["validated_fields"] == {}
        assert client.get("/api/projects/p/practicas/otra").status_code == 404


def test_a_practice_belongs_to_whoever_created_it(tmp_path):
    with NotebookMemory(tmp_path / "n.sqlite3") as memoria:
        memoria.connection.execute(
            "INSERT INTO notebooks (notebook_id, phase, stage, role, active_tool, "
            "completed_tools_json, created_at, updated_at) VALUES ('p','D',1,'','','[]','x','x')")
        registro = RegistroPracticas(memoria.connection)
        practica = registro.crear("p", PERSONA, participant_id="ana")
        assert registro.obtener("p", practica["id"], "ana") is not None
        assert registro.obtener("p", practica["id"], "luis") is None


def test_practices_are_listed_newest_first_for_whoever_created_them(app):
    aplicacion, _ = app
    with TestClient(aplicacion) as client:
        client.post("/api/notebooks", json={"notebook_id": "p"})
        primera = client.post("/api/projects/p/practicas", json={"persona": PERSONA}).json()
        segunda = client.post("/api/projects/p/practicas", json={
            "persona": "Doña Gloria, 68 años, pensionada de Kennedy."}).json()
        lista = client.get("/api/projects/p/practicas").json()
    assert [p["id"] for p in lista] == [segunda["id"], primera["id"]]
