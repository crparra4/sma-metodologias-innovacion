"""PESTEL del proyecto: los seis factores de la ficha, guardados por versiones como el árbol."""

import json

import pytest
from pydantic import ValidationError
from test_sharing import accept_first_invitation, login, logout, register
from test_tree_diagnosis import client_with
from test_why_analysis import RecordingRuntime, chat

from ruta_dia_agents.herramientas.pestel import FACTORS, PestelUpdate, context_lines, empty_pestel


def item(item_id, text, kind="", source="", priority=False):
    return {"id": item_id, "text": text, "kind": kind, "source": source, "priority": priority}


PESTEL = {
    "challenge": "Abrir una academia de programación para niños en Medellín",
    "politico": [item("p1", "Programa de becas de la alcaldía", "oportunidad",
                      "Página de la alcaldía", True)],
    "economico": [item("e1", "Las familias recortan gastos en cursos", "amenaza")],
    "social": [], "tecnologico": [], "ecologico": [],
    "legal": [item("l1", "Protección de datos de menores")],
}


def project(client):
    register(client, "ana", "Ana")
    created = client.post("/api/notebooks", json={
        "notebook_id": "Academia", "context": {"question": "Reto"},
    }).json()
    return created["project_id"], f"/api/projects/{created['project_id']}/pestel"


# ---------- el modelo ----------

def test_the_six_factors_match_the_card_fields():
    assert FACTORS == ("politico", "economico", "social", "tecnologico", "ecologico", "legal")
    assert set(empty_pestel()) == {"challenge", *FACTORS, "version", "updated_at"}


def test_a_complete_pestel_is_valid():
    saved = PestelUpdate(version=0, **PESTEL)
    assert saved.politico[0].priority and saved.legal[0].kind == ""


@pytest.mark.parametrize("change", [
    {"challenge": "   "},  # el paso 1 de la ficha: sin reto no hay análisis
    {"social": [item("p1", "Mismo identificador que el político")]},
    {"social": [item("s1", "Marcado con otra palabra", "riesgo")]},
    {"social": [item(f"s{n}", f"Elemento {n}") for n in range(9)]},  # tope por factor
    {"social": [item(f"s{n}", f"Elemento {n}", priority=True) for n in range(5)]},  # 6 con p1
])
def test_invalid_pestels_are_rejected(change):
    with pytest.raises(ValidationError):
        PestelUpdate(version=0, **{**PESTEL, **change})


def test_context_tells_the_agent_what_is_filled_and_what_is_not():
    lines = context_lines({**PESTEL, "version": 1})
    text = ". ".join(lines)
    assert lines[0].startswith("PESTEL (borrador del equipo, no verificado): reto analizado:")
    assert "Factor Político: Programa de becas de la alcaldía (oportunidad; prioritario; " \
           "origen declarado: Página de la alcaldía)" in text
    assert "Factor Legal: Protección de datos de menores " \
           "(sin marcar como oportunidad o amenaza; sin fuente)" in text
    assert "Factor Social: sin elementos todavía" in text
    assert context_lines(empty_pestel()) == []


# ---------- la API ----------

def test_save_reload_and_version_conflict(tmp_path):
    client = client_with(tmp_path, RecordingRuntime())
    with client:
        _, url = project(client)
        assert client.get(url).json() == empty_pestel()

        saved = client.put(url, json={"version": 0, **PESTEL})
        assert saved.status_code == 200, saved.text
        assert saved.json()["version"] == 1
        stored = client.get(url).json()
        assert stored["politico"][0]["text"] == "Programa de becas de la alcaldía"
        assert stored["version"] == 1 and stored["updated_at"]

        # guardar sobre una versión vieja no pisa el trabajo de otra persona
        stale = client.put(url, json={"version": 0, **PESTEL})
        assert stale.status_code == 409 and "Otra persona" in stale.json()["detail"]
        again = client.put(url, json={"version": 1, **PESTEL, "social": [
            item("s1", "Los padres buscan actividades extracurriculares", "oportunidad")]})
        assert again.json()["version"] == 2


def test_invalid_content_is_not_stored(tmp_path):
    client = client_with(tmp_path, RecordingRuntime())
    with client:
        _, url = project(client)
        response = client.put(url, json={"version": 0, **PESTEL, "challenge": ""})
        assert response.status_code == 422
        assert client.get(url).json()["version"] == 0


def test_a_viewer_reads_but_cannot_edit(tmp_path):
    client = client_with(tmp_path, RecordingRuntime())
    with client:
        project_id, url = project(client)
        assert client.put(url, json={"version": 0, **PESTEL}).status_code == 200
        logout(client)
        register(client, "luis", "Luis")
        logout(client)
        login(client, "ana")
        invited = client.post(f"/api/projects/{project_id}/invitations", json={
            "username": "luis", "role": "viewer",
        })
        assert invited.status_code == 201, invited.text
        logout(client)
        login(client, "luis")
        accept_first_invitation(client)
        assert client.get(url).json()["challenge"] == PESTEL["challenge"]
        assert client.put(url, json={"version": 1, **PESTEL}).status_code == 403


def test_the_saved_pestel_reaches_the_agent_as_context(tmp_path):
    runtime = RecordingRuntime()
    client = client_with(tmp_path, runtime)
    with client:
        project_id, url = project(client)
        assert client.put(url, json={"version": 0, **PESTEL}).status_code == 200
        chat(client, project_id, "Sigamos con el PESTEL")
        context = json.dumps(runtime.states[-1].shared_context, ensure_ascii=False)
        assert "PESTEL (borrador del equipo, no verificado)" in context
        assert "Programa de becas de la alcaldía" in context
