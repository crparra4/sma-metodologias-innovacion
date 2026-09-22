from dataclasses import replace

from fastapi.testclient import TestClient

from ruta_dia_agents.config import Settings
from ruta_dia_agents.contracts import ProjectState
from ruta_dia_agents.memory import NotebookMemory
from ruta_dia_agents.web import create_app


def client_for(tmp_path):
    settings = replace(
        Settings.from_env(),
        memory_path=tmp_path / "notebooks.sqlite3",
        checkpoint_path=tmp_path / "checkpoints.sqlite3",
        audit_path=tmp_path / "audit.jsonl",
        base_url="http://127.0.0.1:18083/v1",
    )
    return TestClient(create_app(settings, model_probe=lambda _: True)), settings


def register(client, username, name):
    return client.post(
        "/api/auth/register",
        json={
            "username": username,
            "display_name": name,
            "password": "una-clave-local-segura",
            "confirm_password": "una-clave-local-segura",
        },
    )


def test_registration_login_logout_and_cookie_security(tmp_path):
    client, _ = client_for(tmp_path)
    with client:
        assert client.get("/api/notebooks").status_code == 401
        assert client.get("/api/auth/me").status_code == 401
        assert register(client, "ANA", "Ana Gómez").status_code == 201
        assert client.cookies.get("hilo_session")
        response = client.get("/api/auth/me")
        assert response.json()["username"] == "ana"
        assert register(client, "ana", "Otra").status_code == 409
        wrong = client.post("/api/auth/login", json={"username": "ana", "password": "equivocada"})
        assert wrong.status_code == 401
        assert (
            client.put("/api/auth/profile", json={"display_name": "Ana P."}).json()["display_name"]
            == "Ana P."
        )
        assert client.post("/api/auth/logout").status_code == 200
        assert client.get("/api/notebooks").status_code == 401
        login = client.post(
            "/api/auth/login", json={"username": "ANA", "password": "una-clave-local-segura"}
        )
        assert login.status_code == 200
        assert "httponly" in login.headers["set-cookie"].lower()
        assert "samesite=strict" in login.headers["set-cookie"].lower()
        assert client.get("/api/auth/me").json()["display_name"] == "Ana P."


def test_accounts_isolate_data_and_first_account_keeps_legacy_projects(tmp_path):
    client, settings = client_for(tmp_path)
    with NotebookMemory(settings.memory_path) as memory:
        memory.create(ProjectState(notebook_id="Proyecto anterior"))
    with client:
        assert register(client, "ana", "Ana").status_code == 201
        assert [item["notebook_id"] for item in client.get("/api/notebooks").json()] == [
            "Proyecto anterior"
        ]
        assert (
            client.post(
                "/api/notebooks",
                json={"notebook_id": "Privado de Ana", "context": {"question": "Un reto"}},
            ).status_code
            == 201
        )
        assert (
            client.post(
                "/api/notebooks/Privado%20de%20Ana/notes",
                json={"title": "Idea de Ana", "text": "Solo para Ana"},
            ).status_code
            == 201
        )
        assert (
            client.post(
                "/api/tasks",
                json={"title": "Pendiente de Ana", "due_at": "2026-09-15T10:00:00-05:00"},
            ).status_code
            == 201
        )
        assert client.post("/api/auth/logout").status_code == 200
        assert register(client, "luis", "Luis").status_code == 201
        assert client.get("/api/notebooks").json() == []
        assert client.get("/api/tasks").json() == []
        assert client.get("/api/notebooks/Privado%20de%20Ana").status_code == 404
        assert (
            client.post(
                "/api/notebooks",
                json={"notebook_id": "Privado de Luis", "context": {"question": "Otro reto"}},
            ).status_code
            == 201
        )
        assert client.post("/api/auth/logout").status_code == 200
        assert (
            client.post(
                "/api/auth/login", json={"username": "ana", "password": "una-clave-local-segura"}
            ).status_code
            == 200
        )
        names = {item["notebook_id"] for item in client.get("/api/notebooks").json()}
        assert names == {"Proyecto anterior", "Privado de Ana"}
        assert client.get("/api/tasks").json()[0]["title"] == "Pendiente de Ana"
        assert (
            client.get("/api/notebooks/Privado%20de%20Ana").json()["notes"][0]["title"]
            == "Idea de Ana"
        )
        assert client.get("/api/notebooks/Privado%20de%20Luis").status_code == 404


def test_registration_validation_and_cross_origin_block(tmp_path):
    client, _ = client_for(tmp_path)
    with client:
        mismatch = client.post(
            "/api/auth/register",
            json={
                "username": "ana",
                "display_name": "Ana",
                "password": "clave-larga-123",
                "confirm_password": "otra-clave-123",
            },
        )
        assert mismatch.status_code == 400
        cross = client.post(
            "/api/auth/register",
            headers={"Origin": "http://otro.local"},
            json={
                "username": "ana",
                "display_name": "Ana",
                "password": "clave-larga-123",
                "confirm_password": "clave-larga-123",
            },
        )
        assert cross.status_code == 403


def test_notes_record_their_author(tmp_path):
    client, settings = client_for(tmp_path)
    with client:
        assert register(client, "ana", "Ana Gómez").status_code == 201
        stage = {"notebook_id": "Movilidad", "stage": 1, "context": {"question": "Reto"}}
        assert client.post("/api/notebooks", json=stage).status_code == 201
        note = {"title": "Idea", "text": "Cambiar horarios", "color": "yellow", "category": "idea"}

        created = client.post("/api/notebooks/Movilidad/notes", json=note).json()
        me = client.get("/api/auth/me").json()
        assert (created["author_id"], created["author_name"]) == (me["id"], "Ana Gómez")

        # Editar conserva al autor original.
        edited = client.put(
            f"/api/notebooks/Movilidad/notes/{created['id']}", json={**note, "title": "Otra"},
        ).json()
        assert (edited["title"], edited["author_id"]) == ("Otra", me["id"])

        # El autor no se puede suplantar desde el cuerpo de la peticion.
        forged = client.post(
            "/api/notebooks/Movilidad/notes", json={**note, "author_id": "otra-cuenta"},
        )
        assert forged.status_code == 422


def test_existing_notes_are_claimed_by_the_storage_owner(tmp_path):
    client, settings = client_for(tmp_path)
    with client:
        assert register(client, "ana", "Ana Gómez").status_code == 201
        stage = {"notebook_id": "Previo", "stage": 1, "context": {"question": "Reto"}}
        assert client.post("/api/notebooks", json=stage).status_code == 201
        # Nota escrita antes de que existiera el autor.
        from ruta_dia_agents.notes import NoteRequest
        with NotebookMemory(settings.memory_path) as memory:
            old = memory.save_note("Previo", NoteRequest(title="Vieja", text="Sin autor"))
        assert old["author_id"] == ""

        notes = client.get("/api/notebooks/Previo").json()["notes"]
        me = client.get("/api/auth/me").json()
        assert [(n["title"], n["author_id"]) for n in notes] == [("Vieja", me["id"])]

