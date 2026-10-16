"""Customer Journey Map del proyecto: etapas en orden, con lo que la ficha pide por etapa."""

import json

import pytest
from pydantic import ValidationError
from test_sharing import accept_first_invitation, login, logout, register
from test_tree_diagnosis import client_with
from test_why_analysis import RecordingRuntime, chat

from ruta_dia_agents.journey import LANES, JourneyUpdate, context_lines, empty_journey
from ruta_dia_agents.runtime import named_part


def note(note_id, text):
    return {"id": note_id, "text": text}


def stage(stage_id, name, emotion=0, critical=False, **lanes):
    return {"id": stage_id, "name": name, "emotion": emotion, "critical": critical,
            **{lane: lanes.get(lane, []) for lane in LANES}}


JOURNEY = {
    "user": "Paciente que pide una cita médica",
    "scenario": "Pedir la cita por teléfono",
    "stages": [
        stage("s1", "Llamar", 2, True,
              acciones=[note("a1", "Marca al número de la EPS")],
              dolores=[note("d1", "Espera veinte minutos en la línea")]),
        stage("s2", "Agendar", 4, contacto=[note("c1", "Asesor telefónico")]),
        stage("s3", "Asistir"),
    ],
}


def project(client):
    register(client, "ana", "Ana")
    created = client.post("/api/notebooks", json={
        "notebook_id": "Citas", "context": {"question": "Reto"},
    }).json()
    return created["project_id"], f"/api/projects/{created['project_id']}/journey"


# ---------- el modelo ----------

def test_the_lanes_follow_the_card():
    assert LANES == ("acciones", "contacto", "dolores", "oportunidades")
    assert empty_journey() == {
        "user": "", "scenario": "", "stages": [], "version": 0, "updated_at": None,
    }


def test_a_journey_keeps_its_stages_in_order():
    saved = JourneyUpdate(version=0, **JOURNEY)
    assert [item.name for item in saved.stages] == ["Llamar", "Agendar", "Asistir"]
    assert saved.stages[0].critical and saved.stages[2].emotion == 0


@pytest.mark.parametrize("change", [
    {"user": "  "},  # el paso 1 de la ficha: sin usuario no hay recorrido
    {"stages": [stage("s1", "Llamar"), stage("s1", "Repetida")]},
    {"stages": [stage("s1", "Llamar", acciones=[note("s1", "Mismo id que la etapa")])]},
    {"stages": [stage("s1", "Llamar", 6)]},  # la emoción va de 1 a 5
    {"stages": [stage("s1", "   ")]},
    {"stages": [stage(f"s{n}", f"Etapa {n}") for n in range(9)]},  # tope de etapas
    {"stages": [stage("s1", "Llamar", acciones=[note(f"a{n}", "x") for n in range(7)])]},
])
def test_invalid_journeys_are_rejected(change):
    with pytest.raises(ValidationError):
        JourneyUpdate(version=0, **{**JOURNEY, **change})


def test_context_tells_the_agent_what_each_stage_is_missing():
    lines = context_lines({**JOURNEY, "version": 1})
    text = ". ".join(lines)
    assert lines[0].startswith(
        "Customer Journey Map (borrador del equipo, no verificado): usuario:")
    assert "escenario: Pedir la cita por teléfono" in lines[0]
    assert "Etapas en orden: Llamar → Agendar → Asistir" in text
    assert "Etapa 1 «Llamar» (emoción: mal, marcada como crítica): " \
           "Acciones: Marca al número de la EPS. Puntos de contacto: sin anotar. " \
           "Dolores: Espera veinte minutos en la línea. Oportunidades de mejora: sin anotar" in text
    assert "Etapa 3 «Asistir» (emoción: sin marcar): Acciones: sin anotar" in text
    assert context_lines(empty_journey()) == []
    assert "falta listar el recorrido" in ". ".join(
        context_lines({**empty_journey(), "user": "Paciente"}))


def test_the_agent_recognises_a_stage_named_in_the_message():
    message = "Quiero seguir con el customer journey: etapa «Llamar a la EPS»."
    assert named_part(message, []) == "Llamar a la EPS"
    assert named_part("Quiero hacer un customer journey", []) == ""


# ---------- la API ----------

def test_save_reload_and_version_conflict(tmp_path):
    client = client_with(tmp_path, RecordingRuntime())
    with client:
        _, url = project(client)
        assert client.get(url).json() == empty_journey()
        saved = client.put(url, json={"version": 0, **JOURNEY})
        assert saved.status_code == 200, saved.text
        stored = client.get(url).json()
        assert stored["version"] == 1 and stored["stages"][0]["dolores"][0]["id"] == "d1"
        stale = client.put(url, json={"version": 0, **JOURNEY})
        assert stale.status_code == 409 and "Otra persona" in stale.json()["detail"]
        assert client.put(url, json={"version": 1, **JOURNEY}).json()["version"] == 2


def test_a_viewer_reads_but_cannot_edit(tmp_path):
    client = client_with(tmp_path, RecordingRuntime())
    with client:
        project_id, url = project(client)
        assert client.put(url, json={"version": 0, **JOURNEY}).status_code == 200
        logout(client)
        register(client, "luis", "Luis")
        logout(client)
        login(client, "ana")
        assert client.post(f"/api/projects/{project_id}/invitations", json={
            "username": "luis", "role": "viewer",
        }).status_code == 201
        logout(client)
        login(client, "luis")
        accept_first_invitation(client)
        assert client.get(url).json()["user"] == JOURNEY["user"]
        assert client.put(url, json={"version": 1, **JOURNEY}).status_code == 403


def test_the_saved_journey_reaches_the_agent_as_context(tmp_path):
    runtime = RecordingRuntime()
    client = client_with(tmp_path, runtime)
    with client:
        project_id, url = project(client)
        assert client.put(url, json={"version": 0, **JOURNEY}).status_code == 200
        chat(client, project_id, "Sigamos con el recorrido")
        context = json.dumps(runtime.states[-1].shared_context, ensure_ascii=False)
        assert "Customer Journey Map (borrador del equipo, no verificado)" in context
        assert "Espera veinte minutos en la línea" in context
