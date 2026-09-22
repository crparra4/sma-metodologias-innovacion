import json
from dataclasses import replace

from fastapi.testclient import TestClient
from test_langgraph_workflow import FakeRuntime

from ruta_dia_agents.config import Settings
from ruta_dia_agents.contracts import Verdict
from ruta_dia_agents.web import create_app

PASSWORD = "una-clave-local-segura"


def sharing_client(tmp_path):
    settings = replace(
        Settings.from_env(),
        memory_path=tmp_path / "notebooks.sqlite3",
        checkpoint_path=tmp_path / "checkpoints.sqlite3",
        audit_path=tmp_path / "audit.jsonl",
        base_url="http://127.0.0.1:18083/v1",
    )
    app = create_app(
        settings,
        runtime_factory=lambda _: FakeRuntime([Verdict.APPROVED]),
        model_probe=lambda _: True,
    )
    return TestClient(app)


def register(client, username, display_name):
    response = client.post("/api/auth/register", json={
        "username": username,
        "display_name": display_name,
        "password": PASSWORD,
        "confirm_password": PASSWORD,
    })
    assert response.status_code == 201, response.text
    return response.json()


def login(client, username):
    response = client.post("/api/auth/login", json={
        "username": username, "password": PASSWORD,
    })
    assert response.status_code == 200, response.text
    return response.json()


def logout(client):
    assert client.post("/api/auth/logout").status_code == 200


def stream_events(response):
    return [json.loads(line[6:]) for line in response.text.splitlines()
            if line.startswith("data: ")]


def accept_first_invitation(client):
    invitations = client.get("/api/sharing/invitations").json()
    assert len(invitations) == 1
    response = client.post(
        f"/api/sharing/invitations/{invitations[0]['id']}/respond",
        json={"accept": True},
    )
    assert response.status_code == 200, response.text
    return invitations[0]


def test_shared_project_permissions_content_and_private_chats(tmp_path):
    client = sharing_client(tmp_path)
    with client:
        owner = register(client, "ana", "Ana")
        created = client.post("/api/notebooks", json={
            "notebook_id": "Movilidad", "context": {"question": "Reducir esperas"},
        })
        assert created.status_code == 201
        project_id = created.json()["project_id"]
        assert client.get("/api/notebooks").json()[0]["collaborators"] == []
        assert client.post(f"/api/notebooks/{project_id}/notes", json={
            "title": "Hallazgo inicial", "text": "Las filas son largas",
        }).status_code == 201
        owner_chat = stream_events(client.post("/api/chat", json={
            "notebook_id": "Movilidad", "project_id": project_id,
            "message": "Analicemos las filas",
        }))
        assert owner_chat[-1]["type"] == "result"

        logout(client)
        viewer = register(client, "luis", "Luis")
        assert client.get("/api/notebooks").json() == []
        logout(client)
        editor = register(client, "maria", "María")
        logout(client)

        login(client, "ana")
        for username, role in (("luis", "viewer"), ("maria", "editor")):
            response = client.post(f"/api/projects/{project_id}/invitations", json={
                "username": username, "role": role,
            })
            assert response.status_code == 201, response.text
        assert [(person["username"], person.get("status")) for person in
                client.get("/api/notebooks").json()[0]["collaborators"]] == [
            ("ana", None), ("luis", "pending"), ("maria", "pending"),
        ]
        logout(client)

        login(client, "luis")
        invitation = accept_first_invitation(client)
        assert invitation["role"] == "viewer"
        notebooks = client.get("/api/notebooks").json()
        assert [(item["project_id"], item["role"]) for item in notebooks] == [
            (project_id, "viewer")
        ]
        assert [(person["user_id"], person["role"])
                for person in notebooks[0]["collaborators"]] == [
            (owner["id"], "owner"), (viewer["id"], "viewer"),
        ]
        shared = client.get(f"/api/notebooks/{project_id}").json()
        assert shared["state"]["context"]["question"] == "Reducir esperas"
        assert shared["notes"][0]["title"] == "Hallazgo inicial"
        assert shared["turns"] == []  # el chat de Ana no se comparte
        assert client.post(f"/api/notebooks/{project_id}/notes", json={
            "title": "No", "text": "Sin permiso",
        }).status_code == 403
        assert client.post("/api/tasks", json={
            "title": "No editable", "due_at": "2026-10-01T12:00:00Z",
            "project_id": project_id,
        }).status_code == 403
        viewer_chat = stream_events(client.post("/api/chat", json={
            "notebook_id": "Movilidad", "project_id": project_id,
            "message": "Mi análisis privado",
        }))
        assert viewer_chat[-1]["type"] == "result"
        assert len(client.get(f"/api/notebooks/{project_id}").json()["turns"]) == 2
        logout(client)

        login(client, "maria")
        accept_first_invitation(client)
        assert {(person["user_id"], person["role"])
                for person in client.get("/api/notebooks").json()[0]["collaborators"]} == {
            (owner["id"], "owner"), (viewer["id"], "viewer"),
            (editor["id"], "editor"),
        }
        note = client.post(f"/api/notebooks/{project_id}/notes", json={
            "title": "Aporte de edición", "text": "Probar turnos digitales",
        })
        assert note.status_code == 201
        assert (note.json()["author_id"], note.json()["author_name"]) == (
            editor["id"], "María"
        )
        task = client.post("/api/tasks", json={
            "title": "Prototipar turnos", "due_at": "2026-10-01T12:00:00Z",
            "project_id": project_id,
        })
        assert task.status_code == 201
        advance = client.post(f"/api/projects/{project_id}/advances", json={
            "content": "Se priorizó validar un sistema de turnos.", "kind": "decision",
        })
        assert advance.status_code == 201
        editor_chat = stream_events(client.post("/api/chat", json={
            "notebook_id": "Movilidad", "project_id": project_id,
            "message": "Tengo un nuevo avance privado",
        }))
        assert editor_chat[-1]["type"] == "result"
        assert len(client.get(f"/api/notebooks/{project_id}").json()["turns"]) == 2
        logout(client)

        login(client, "ana")
        owner_view = client.get(f"/api/notebooks/{project_id}").json()
        assert len(owner_view["turns"]) == 2  # solo permanece el chat de Ana
        assert {item["title"] for item in owner_view["notes"]} == {
            "Hallazgo inicial", "Aporte de edición"
        }
        assert owner_view["advances"][0]["author_name"] == "María"
        shared_tasks = [item for item in client.get("/api/tasks").json()
                        if item.get("project_id") == project_id]
        assert shared_tasks[0]["author_name"] == "María"
        members = client.get(f"/api/projects/{project_id}/members").json()
        assert {(item["user_id"], item["role"]) for item in members} == {
            (owner["id"], "owner"), (viewer["id"], "viewer"),
            (editor["id"], "editor"),
        }
        assert {person["user_id"] for person in
                client.get("/api/notebooks").json()[0]["collaborators"]} == {
            owner["id"], viewer["id"], editor["id"],
        }


def test_owner_can_change_revoke_and_cancel_access(tmp_path):
    client = sharing_client(tmp_path)
    with client:
        register(client, "owner", "Propietaria")
        project_id = client.post("/api/notebooks", json={"notebook_id": "Proyecto"}).json()[
            "project_id"
        ]
        logout(client)
        member = register(client, "member", "Integrante")
        logout(client)
        register(client, "pending", "Pendiente")
        logout(client)

        login(client, "owner")
        invitation = client.post(f"/api/projects/{project_id}/invitations", json={
            "username": "member", "role": "editor",
        }).json()
        pending = client.post(f"/api/projects/{project_id}/invitations", json={
            "username": "pending", "role": "viewer",
        }).json()
        assert client.delete(f"/api/sharing/invitations/{pending['id']}").status_code == 200
        logout(client)

        login(client, "member")
        assert client.post(
            f"/api/sharing/invitations/{invitation['id']}/respond", json={"accept": True}
        ).status_code == 200
        logout(client)

        login(client, "owner")
        assert client.put(f"/api/projects/{project_id}/members/{member['id']}", json={
            "role": "viewer",
        }).status_code == 200
        logout(client)

        login(client, "member")
        assert client.post(f"/api/notebooks/{project_id}/notes", json={
            "title": "Bloqueado", "text": "Ya no puede editar",
        }).status_code == 403
        logout(client)

        login(client, "owner")
        assert client.delete(
            f"/api/projects/{project_id}/members/{member['id']}"
        ).status_code == 200
        logout(client)
        login(client, "member")
        assert client.get(f"/api/notebooks/{project_id}").status_code == 404
