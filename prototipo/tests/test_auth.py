import os
import stat
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from ruta_dia_agents.auth import AttemptLimiter
from ruta_dia_agents.config import Settings
from ruta_dia_agents.contracts import ProjectState
from ruta_dia_agents.memory import NotebookMemory
from ruta_dia_agents.web import MAX_BODY_BYTES, create_app


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
            client.put("/api/auth/profile", json={"first_name": "Ana", "last_name": "P."})
            .json()["display_name"] == "Ana P."
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



def login(client, username, password="una-clave-local-segura"):
    return client.post("/api/auth/login", json={"username": username, "password": password})


def test_attempt_limiter_frees_the_slot_when_the_window_passes():
    now = [100.0]
    limiter = AttemptLimiter(2, window=60, clock=lambda: now[0])
    assert limiter.attempt("ana") == 0
    now[0] += 20
    assert limiter.attempt("ana") == 0
    assert limiter.attempt("ana") == 40
    # Un intento rechazado no alarga la espera ni afecta a otra clave.
    assert limiter.attempt("ana") == 40
    assert limiter.attempt("luis") == 0
    now[0] += 40
    assert limiter.attempt("ana") == 0
    limiter.forget("ana")
    assert limiter.attempt("ana") == 0
    now[0] += 61
    assert limiter.attempt("luis") == 0
    assert set(limiter._hits) == {"luis"}


def test_login_blocks_a_user_after_repeated_failures(tmp_path):
    client, _ = client_for(tmp_path)
    with client:
        assert register(client, "ana", "Ana").status_code == 201
        assert register(client, "luis", "Luis").status_code == 201
        assert client.post("/api/auth/logout").status_code == 200
        for _ in range(5):
            assert login(client, " ANA ", "equivocada").status_code == 401
        blocked = login(client, "ana")
        assert blocked.status_code == 429
        assert 1 <= int(blocked.headers["retry-after"]) <= 60
        assert "Demasiados intentos" in blocked.json()["detail"]
        # El bloqueo es de esa cuenta: las demás siguen entrando.
        assert login(client, "luis").status_code == 200


def test_successful_login_clears_the_failure_count(tmp_path):
    client, _ = client_for(tmp_path)
    with client:
        assert register(client, "ana", "Ana").status_code == 201
        for _ in range(3):
            assert login(client, "ana", "equivocada").status_code == 401
            assert login(client, "ana").status_code == 200
        assert login(client, "ana", "equivocada").status_code == 401


def test_access_attempts_share_a_quota_per_origin(tmp_path):
    client, _ = client_for(tmp_path)
    with client:
        # Usuarios distintos: el tope por cuenta no interviene.
        codes = [login(client, f"nadie{index}").status_code for index in range(21)]
        assert codes == [401] * 20 + [429]
        assert register(client, "ana", "Ana").status_code == 429
        assert client.get("/api/auth/me").status_code == 401


def test_oversized_login_fields_and_bodies_are_rejected(tmp_path):
    client, _ = client_for(tmp_path)
    with client:
        assert login(client, "ana", "x" * 129).status_code == 422
        big = b'{"username": "ana", "password": "' + b"x" * MAX_BODY_BYTES + b'"}'
        declared = client.post(
            "/api/auth/login", content=big, headers={"Content-Type": "application/json"}
        )
        assert declared.status_code == 413

        def pieces():
            for start in range(0, len(big), 64 * 1024):
                yield big[start:start + 64 * 1024]

        chunked = client.post(
            "/api/auth/login", content=pieces(), headers={"Content-Type": "application/json"}
        )
        assert "content-length" not in chunked.request.headers
        assert chunked.status_code == 413
        # Ninguno de los rechazos gastó un intento de acceso.
        assert register(client, "ana", "Ana").status_code == 201


@pytest.mark.skipif(os.name != "posix", reason="permisos POSIX")
def test_the_data_folder_is_private_to_the_account_running_hilo(tmp_path):
    data = tmp_path / "datos"
    (data / "users" / "abc").mkdir(parents=True)
    (data / "notebooks.sqlite3").write_bytes(b"")
    (data / "users" / "abc" / "notebooks.sqlite3").write_bytes(b"")
    for item in (data, data / "users", data / "users" / "abc"):
        item.chmod(0o775)
    client, _ = client_for(data)
    with client:
        assert register(client, "ana", "Ana").status_code == 201
    mode = lambda item: stat.S_IMODE(item.stat().st_mode)  # noqa: E731
    assert mode(data) == 0o700
    assert mode(data / "users") == 0o700
    assert mode(data / "notebooks.sqlite3") == 0o600
    assert mode(data / "users" / "abc" / "notebooks.sqlite3") == 0o600


def change_password(client, current, new, confirm=None):
    return client.put("/api/auth/password", json={
        "current_password": current, "new_password": new,
        "confirm_password": new if confirm is None else confirm,
    })


def test_account_details_show_when_the_account_was_created(tmp_path):
    client, _ = client_for(tmp_path)
    with client:
        assert client.get("/api/auth/account").status_code == 401
        assert register(client, "ana", "Ana Gómez").status_code == 201
        details = client.get("/api/auth/account").json()
        assert details["username"] == "ana" and details["display_name"] == "Ana Gómez"
        assert details["created_at"] > 0 and details["session_hours"] == 12


def test_changing_the_password_keeps_this_session_and_closes_the_others(tmp_path):
    client, settings = client_for(tmp_path)
    with client:
        assert register(client, "ana", "Ana").status_code == 201
        other = TestClient(client.app)
        assert login(other, "ana").status_code == 200
        assert change_password(client, "equivocada-1", "otra-clave-segura").status_code == 400
        mismatch = change_password(client, "una-clave-local-segura", "otra-clave-segura", "x" * 12)
        assert mismatch.status_code == 400
        same = change_password(client, "una-clave-local-segura", "una-clave-local-segura")
        assert same.status_code == 400
        assert change_password(client, "una-clave-local-segura", "corta").status_code == 422
        ok = change_password(client, "una-clave-local-segura", "otra-clave-segura")
        assert ok.status_code == 200
        assert client.get("/api/auth/me").status_code == 200
        assert other.get("/api/auth/me").status_code == 401
        assert login(other, "ana").status_code == 401
        assert login(other, "ana", "otra-clave-segura").status_code == 200


def test_guessing_the_current_password_is_limited(tmp_path):
    client, _ = client_for(tmp_path)
    with client:
        assert register(client, "ana", "Ana").status_code == 201
        for index in range(5):
            wrong = change_password(client, f"equivocada-{index}", "otra-clave-segura")
            assert wrong.status_code == 400
        blocked = change_password(client, "una-clave-local-segura", "otra-clave-segura")
        assert blocked.status_code == 429



def put_profile(client, **fields):
    return client.put("/api/auth/profile", json={"first_name": "Ana", **fields})


def test_profile_splits_name_and_keeps_phone_and_email(tmp_path):
    client, _ = client_for(tmp_path)
    with client:
        assert register(client, "ana", "Ana María Gómez").status_code == 201
        # Antes de dividirlo, el nombre completo de la cuenta se muestra como nombre.
        before = client.get("/api/auth/profile").json()
        assert (before["first_name"], before["last_name"]) == ("Ana María Gómez", "")
        saved = put_profile(client, first_name="  Ana  María ", last_name="Gómez",
                            phone="+57 300 123 4567", email="Ana@Correo.CO")
        assert saved.status_code == 200
        assert saved.json()["display_name"] == "Ana María Gómez"
        profile = client.get("/api/auth/profile").json()
        assert profile["first_name"] == "Ana María" and profile["last_name"] == "Gómez"
        assert profile["phone"] == "+57 300 123 4567" and profile["email"] == "ana@correo.co"
        assert client.get("/api/auth/me").json()["display_name"] == "Ana María Gómez"


@pytest.mark.parametrize("fields, message", [
    ({"first_name": "   "}, "Escribe tu nombre."),
    ({"phone": "300-abc-1234"}, "teléfono"),
    ({"phone": "12345"}, "teléfono"),
    ({"email": "ana@correo"}, "correo"),
    ({"email": "ana correo.co"}, "correo"),
])
def test_profile_rejects_invalid_fields_with_a_readable_message(tmp_path, fields, message):
    client, _ = client_for(tmp_path)
    with client:
        assert register(client, "ana", "Ana").status_code == 201
        response = put_profile(client, **fields)
        assert response.status_code == 400 and message in response.json()["detail"]
        assert client.get("/api/auth/me").json()["display_name"] == "Ana"


def test_an_account_database_from_before_the_profile_fields_still_opens(tmp_path):
    import sqlite3
    with sqlite3.connect(tmp_path / "auth.sqlite3") as db:
        db.execute("""CREATE TABLE users (id TEXT PRIMARY KEY, username TEXT NOT NULL UNIQUE,
            display_name TEXT NOT NULL, salt BLOB NOT NULL, password_hash BLOB NOT NULL,
            legacy INTEGER NOT NULL, created_at INTEGER NOT NULL)""")
    client, _ = client_for(tmp_path)
    with client:
        assert register(client, "ana", "Ana").status_code == 201
        assert client.get("/api/auth/me").json()["avatar"] == 0


PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
WEBP = b"RIFF\x10\x00\x00\x00WEBPVP8 " + b"\x00" * 64


def test_profile_photo_upload_replace_and_remove(tmp_path):
    client, _ = client_for(tmp_path)
    with client:
        assert register(client, "ana", "Ana").status_code == 201
        me = client.get("/api/auth/me").json()
        assert me["avatar"] == 0
        assert client.get(f"/api/users/{me['id']}/avatar").status_code == 404
        first = client.put("/api/auth/avatar", content=PNG,
                           headers={"Content-Type": "image/png"}).json()
        assert first["avatar"] == 1
        image = client.get(f"/api/users/{me['id']}/avatar?v=1")
        assert image.status_code == 200 and image.content == PNG
        assert image.headers["content-type"] == "image/png"
        assert image.headers["x-content-type-options"] == "nosniff"
        # El tipo sale de los bytes, no de la cabecera que mande el navegador.
        second = client.put("/api/auth/avatar", content=WEBP,
                            headers={"Content-Type": "image/png"}).json()
        assert second["avatar"] == 2
        assert client.get(f"/api/users/{me['id']}/avatar").headers["content-type"] == "image/webp"
        assert client.delete("/api/auth/avatar").json()["avatar"] == 0
        assert client.get(f"/api/users/{me['id']}/avatar").status_code == 404
        assert client.get("/api/auth/me").json()["avatar"] == 0


def test_profile_photo_rejects_other_files_and_big_ones(tmp_path):
    client, _ = client_for(tmp_path)
    with client:
        assert register(client, "ana", "Ana").status_code == 201
        svg = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
        for content in (svg, b"GIF89a" + b"\x00" * 20, b""):
            response = client.put("/api/auth/avatar", content=content)
            assert response.status_code == 400
        big = client.put("/api/auth/avatar", content=PNG + b"\x00" * (512 * 1024))
        assert big.status_code == 413
        assert client.get("/api/auth/me").json()["avatar"] == 0
