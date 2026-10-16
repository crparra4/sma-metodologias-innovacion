"""Mapa de empatía del proyecto: los seis bloques de la ficha, guardados por versiones."""

import json

import pytest
from pydantic import ValidationError
from test_sharing import accept_first_invitation, login, logout, register
from test_tree_diagnosis import client_with
from test_why_analysis import RecordingRuntime, chat

from ruta_dia_agents.config import Settings
from ruta_dia_agents.contracts import CandidateResponse, HandoffContract, VerificationAssessment
from ruta_dia_agents.empathy_map import (
    BLOCKS,
    EmpathyMapUpdate,
    context_lines,
    empty_empathy_map,
)
from ruta_dia_agents.knowledge import KnowledgeCatalog
from ruta_dia_agents.runtime import grounded_verdict, named_part


def note(note_id, text, basis="", source=""):
    return {"id": note_id, "text": text, "basis": basis, "source": source}


MAP = {
    "user": "Adultos mayores que usan la aplicación del banco",
    "piensa_siente": [note("p1", "Les da miedo equivocarse", "observado", "Entrevista 2")],
    "ve": [note("v1", "Sus nietos pagan todo desde el celular", "supuesto")],
    "oye": [], "dice_hace": [],
    "dolores": [note("d1", "La letra es muy pequeña")],
    "necesidades": [],
}


def project(client):
    register(client, "ana", "Ana")
    created = client.post("/api/notebooks", json={
        "notebook_id": "Banco", "context": {"question": "Reto"},
    }).json()
    return created["project_id"], f"/api/projects/{created['project_id']}/empathy-map"


# ---------- el modelo ----------

def test_the_six_blocks_follow_the_card():
    assert BLOCKS == ("piensa_siente", "ve", "oye", "dice_hace", "dolores", "necesidades")
    assert set(empty_empathy_map()) == {"user", *BLOCKS, "version", "updated_at"}


def test_a_map_is_valid_and_notes_start_unmarked():
    saved = EmpathyMapUpdate(version=0, **MAP)
    assert saved.piensa_siente[0].basis == "observado" and saved.dolores[0].basis == ""


@pytest.mark.parametrize("change", [
    {"user": "   "},  # la ficha empieza por definir el usuario
    {"ve": [note("p1", "Mismo identificador que otra nota")]},
    {"ve": [note("v1", "Marcada con otra palabra", "verificado")]},
    {"ve": [note(f"v{n}", f"Nota {n}") for n in range(9)]},  # tope por bloque
])
def test_invalid_maps_are_rejected(change):
    with pytest.raises(ValidationError):
        EmpathyMapUpdate(version=0, **{**MAP, **change})


def test_context_tells_the_agent_what_was_observed_and_what_is_assumed():
    lines = context_lines({**MAP, "version": 1})
    text = ". ".join(lines)
    assert lines[0].startswith("Mapa de empatía (borrador del equipo, no verificado): usuario:")
    assert "Bloque ¿Qué piensa y siente?: Les da miedo equivocarse " \
           "(observado; origen declarado: Entrevista 2)" in text
    assert "Sus nietos pagan todo desde el celular (supuesto; sin fuente)" in text
    assert "La letra es muy pequeña (sin marcar como observado o supuesto; sin fuente)" in text
    assert "Bloque ¿Qué oye?: sin notas todavía" in text
    assert context_lines(empty_empathy_map()) == []


def test_the_agent_recognises_a_block_named_in_the_message():
    fields = ["piensa_siente", "ve", "oye", "dice_hace", "esfuerzos_1"]
    message = "Quiero seguir con el mapa de empatía: bloque «¿Qué piensa y siente?»."
    assert named_part(message, fields) == "¿Qué piensa y siente?"
    assert named_part("Quiero seguir con el mapa de empatía: bloque «¿Qué oye?».", fields) == "oye"
    assert named_part("Quiero hacer un mapa de empatía", fields) == ""


# ---------- la API ----------

def test_save_reload_and_version_conflict(tmp_path):
    client = client_with(tmp_path, RecordingRuntime())
    with client:
        _, url = project(client)
        assert client.get(url).json() == empty_empathy_map()
        saved = client.put(url, json={"version": 0, **MAP})
        assert saved.status_code == 200, saved.text
        stored = client.get(url).json()
        assert stored["version"] == 1 and stored["piensa_siente"][0]["basis"] == "observado"
        stale = client.put(url, json={"version": 0, **MAP})
        assert stale.status_code == 409 and "Otra persona" in stale.json()["detail"]
        assert client.put(url, json={"version": 1, **MAP}).json()["version"] == 2


def test_a_map_without_a_user_is_not_stored(tmp_path):
    client = client_with(tmp_path, RecordingRuntime())
    with client:
        _, url = project(client)
        assert client.put(url, json={"version": 0, **MAP, "user": ""}).status_code == 422
        assert client.get(url).json()["version"] == 0


def test_a_viewer_reads_but_cannot_edit(tmp_path):
    client = client_with(tmp_path, RecordingRuntime())
    with client:
        project_id, url = project(client)
        assert client.put(url, json={"version": 0, **MAP}).status_code == 200
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
        assert client.get(url).json()["user"] == MAP["user"]
        assert client.put(url, json={"version": 1, **MAP}).status_code == 403


def test_the_saved_map_reaches_the_agent_as_context(tmp_path):
    runtime = RecordingRuntime()
    client = client_with(tmp_path, runtime)
    with client:
        project_id, url = project(client)
        assert client.put(url, json={"version": 0, **MAP}).status_code == 200
        chat(client, project_id, "Sigamos con el mapa de empatía")
        context = json.dumps(runtime.states[-1].shared_context, ensure_ascii=False)
        assert "Mapa de empatía (borrador del equipo, no verificado)" in context
        assert "Les da miedo equivocarse" in context


def test_a_block_name_with_question_marks_is_not_a_second_question():
    catalog = KnowledgeCatalog(Settings.from_env().route_path)
    card = catalog.tool_card("mapa-empatia")
    handoff = HandoffContract(
        intent="x", phase=catalog.stage(3).phase, stage=3, expertise="novel",
        recommendations=[{"tool_id": "mapa-empatia", "reason": "x"}],
        active_tool="mapa-empatia", context_summary="x",
    )

    def verdict(message):
        candidate = CandidateResponse(
            message=message, next_step="Preguntar por el bloque.", tool_id="mapa-empatia",
            source_sections=["Qué es"],
        )
        return grounded_verdict(
            VerificationAssessment(), candidate, handoff, card, "Sigamos con el mapa.",
        ).verdict

    assert verdict("En el bloque ¿Qué oye?, ¿qué otra frase dicen los padres?") == "approved"
    assert verdict("En el bloque ¿qué oye?, ¿qué frase escuchan? ¿Y quién la dice?") == "rejected"
