import sqlite3
from dataclasses import replace

from fastapi.testclient import TestClient
from test_langgraph_workflow import FakeRuntime
from test_sharing import (
    accept_first_invitation,
    login,
    logout,
    register,
    sharing_client,
    stream_events,
)

from ruta_dia_agents.config import Settings
from ruta_dia_agents.contracts import Verdict
from ruta_dia_agents.web import create_app


def shared_project(client, member_role="editor"):
    """Crea un proyecto de 'ana' compartido con 'maria' y deja la sesion de maria abierta."""
    register(client, "ana", "Ana")
    project_id = client.post("/api/notebooks", json={"notebook_id": "Movilidad"}).json()[
        "project_id"
    ]
    logout(client)
    member = register(client, "maria", "María")
    logout(client)
    login(client, "ana")
    assert client.post(f"/api/projects/{project_id}/invitations", json={
        "username": "maria", "role": member_role,
    }).status_code == 201
    logout(client)
    login(client, "maria")
    accept_first_invitation(client)
    return project_id, member


class RevokingRuntime(FakeRuntime):
    """Simula que el propietario cambia el acceso mientras Hilo responde."""

    def __init__(self, on_guide):
        super().__init__([Verdict.APPROVED])
        self.on_guide = on_guide

    def guide(self, *args, **kwargs):
        if self.on_guide:
            self.on_guide()
        return super().guide(*args, **kwargs)


def revoking_client(tmp_path, holder):
    settings = replace(
        Settings.from_env(),
        memory_path=tmp_path / "notebooks.sqlite3",
        checkpoint_path=tmp_path / "checkpoints.sqlite3",
        audit_path=tmp_path / "audit.jsonl",
        base_url="http://127.0.0.1:18083/v1",
    )
    return TestClient(create_app(
        settings,
        runtime_factory=lambda _: RevokingRuntime(holder.get("on_guide")),
        model_probe=lambda _: True,
    ))


def change_membership(tmp_path, sql, *params):
    with sqlite3.connect(tmp_path / "auth.sqlite3") as db:
        db.execute(sql, params)


def test_chat_is_not_saved_when_access_is_revoked_mid_turn(tmp_path):
    holder = {}
    client = revoking_client(tmp_path, holder)
    with client:
        project_id, member = shared_project(client)
        holder["on_guide"] = lambda: change_membership(
            tmp_path, "DELETE FROM project_members WHERE user_id=?", member["id"]
        )
        events = stream_events(client.post("/api/chat", json={
            "notebook_id": "Movilidad", "project_id": project_id, "message": "Sigamos",
        }))
        assert events[-1]["type"] == "error"
        assert "no se guardó" in events[-1]["message"]
        assert client.get(f"/api/notebooks/{project_id}").status_code in {403, 404}
        logout(client)

        holder["on_guide"] = None
        login(client, "ana")
        assert client.get(f"/api/notebooks/{project_id}").json()["turns"] == []


def test_chat_uses_the_current_role_when_it_changes_mid_turn(tmp_path):
    holder = {}
    client = revoking_client(tmp_path, holder)
    with client:
        project_id, member = shared_project(client)
        holder["on_guide"] = lambda: change_membership(
            tmp_path, "UPDATE project_members SET role='viewer' WHERE user_id=?", member["id"]
        )
        events = stream_events(client.post("/api/chat", json={
            "notebook_id": "Movilidad", "project_id": project_id, "message": "Mi idea",
        }))
        assert events[-1]["type"] == "result"
        # El intercambio se guardo como chat privado de la persona que ahora es lectora.
        assert len(client.get(f"/api/notebooks/{project_id}").json()["turns"]) == 2
        logout(client)
        holder["on_guide"] = None
        login(client, "ana")
        assert client.get(f"/api/notebooks/{project_id}").json()["turns"] == []


def test_advances_can_be_corrected_and_retired_with_versions(tmp_path):
    client = sharing_client(tmp_path)
    with client:
        project_id, _ = shared_project(client)
        advance = client.post(f"/api/projects/{project_id}/advances", json={
            "content": "Validar turnos digitales", "kind": "decision",
        }).json()
        assert advance["version"] == 1
        url = f"/api/projects/{project_id}/advances/{advance['id']}"

        corrected = client.put(url, json={
            "content": "Validar turnos digitales en dos sedes", "kind": "decision", "version": 1,
        })
        assert corrected.status_code == 200, corrected.text
        assert corrected.json()["version"] == 2
        stale = client.put(url, json={
            "content": "Versión vieja", "kind": "finding", "version": 1,
        })
        assert stale.status_code == 409
        advances = client.get(f"/api/notebooks/{project_id}").json()["advances"]
        assert [item["content"] for item in advances] == ["Validar turnos digitales en dos sedes"]

        assert client.delete(url).status_code == 200
        assert client.get(f"/api/notebooks/{project_id}").json()["advances"] == []
        assert client.delete(url).status_code == 404
        assert client.put(url, json={
            "content": "Ya retirado", "kind": "other", "version": 2,
        }).status_code == 404


def test_viewers_cannot_correct_or_retire_advances(tmp_path):
    client = sharing_client(tmp_path)
    with client:
        project_id, _ = shared_project(client, member_role="viewer")
        logout(client)
        login(client, "ana")
        advance = client.post(f"/api/projects/{project_id}/advances", json={
            "content": "Hallazgo de Ana", "kind": "finding",
        }).json()
        logout(client)
        login(client, "maria")
        url = f"/api/projects/{project_id}/advances/{advance['id']}"
        assert client.put(url, json={
            "content": "Cambio", "kind": "finding", "version": 1,
        }).status_code == 403
        assert client.delete(url).status_code == 403


def test_note_edit_conflict_returns_current_version(tmp_path):
    client = sharing_client(tmp_path)
    with client:
        project_id, _ = shared_project(client)
        note = client.post(f"/api/notebooks/{project_id}/notes", json={
            "title": "Idea", "text": "Primera versión",
        }).json()
        url = f"/api/notebooks/{project_id}/notes/{note['id']}"
        first = client.put(url, json={
            "title": "Idea", "text": "Cambio de María", "base_updated_at": note["updated_at"],
        })
        assert first.status_code == 200, first.text
        stale = client.put(url, json={
            "title": "Idea", "text": "Cambio de Ana", "base_updated_at": note["updated_at"],
        })
        assert stale.status_code == 409
        assert stale.json()["current"]["text"] == "Cambio de María"
        # Sin marca de version se mantiene el comportamiento anterior.
        assert client.put(url, json={"title": "Idea", "text": "Final"}).status_code == 200


def test_task_edit_conflict_returns_current_version(tmp_path):
    client = sharing_client(tmp_path)
    with client:
        project_id, _ = shared_project(client)
        task = client.post("/api/tasks", json={
            "title": "Prototipar", "due_at": "2026-10-01T12:00:00Z", "project_id": project_id,
        }).json()
        url = f"/api/tasks/{task['id']}"
        body = {"due_at": task["due_at"], "project_id": project_id,
                "base_updated_at": task["updated_at"]}
        assert client.put(url, json={**body, "title": "Prototipar v2"}).status_code == 200
        stale = client.put(url, json={**body, "title": "Otro cambio"})
        assert stale.status_code == 409
        current = stale.json()["current"]
        assert (current["title"], current["project_id"]) == ("Prototipar v2", project_id)
