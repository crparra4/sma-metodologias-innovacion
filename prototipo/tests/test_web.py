import json
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient
from test_langgraph_workflow import FakeRuntime

from ruta_dia_agents.config import Settings
from ruta_dia_agents.contracts import Verdict
from ruta_dia_agents.web import create_app


@pytest.fixture
def settings(tmp_path):
    return replace(
        Settings.from_env(),
        memory_path=tmp_path / "notebooks.sqlite3",
        checkpoint_path=tmp_path / "checkpoints.sqlite3",
        audit_path=tmp_path / "verifications.jsonl",
        base_url="http://127.0.0.1:18083/v1",
        api_key="test-secret-never-exposed",
    )


def app(settings, factory=None):
    return create_app(
        settings,
        runtime_factory=factory or (lambda _: FakeRuntime([Verdict.APPROVED])),
        model_probe=lambda _: True,
        require_auth=False,
    )


def test_tasks_persist_completion_and_survive_project_deletion(settings):
    body = {"title": "Revisar prototipo", "due_at": "2026-09-15T10:00:00-05:00",
            "priority": "high", "notebook_id": "Proyecto tareas"}
    with TestClient(app(settings)) as client:
        client.post("/api/notebooks", json={"notebook_id": "Proyecto tareas"})
        created = client.post("/api/tasks", json=body)
        assert created.status_code == 201
        task_id = created.json()["id"]
        assert created.json()["due_at"] == "2026-09-15T15:00:00+00:00"
        updated = client.put(f"/api/tasks/{task_id}", json={**body, "completed": True})
        assert updated.status_code == 200
    with TestClient(app(settings)) as client:
        assert client.get("/api/tasks").json()[0]["completed"] is True
        client.delete("/api/notebooks/Proyecto tareas")
        task = client.get("/api/tasks").json()[0]
        assert task["notebook_id"] is None
        assert client.delete(f"/api/tasks/{task_id}").status_code == 200
        assert client.get("/api/tasks").json() == []


@pytest.mark.parametrize("changes", [
    {"title": " "}, {"title": "a" * 201}, {"priority": "invalid"},
    {"due_at": "2026-02-30T10:00:00Z"}, {"due_at": "2026-09-15T10:00:00"},
])
def test_tasks_reject_invalid_data(settings, changes):
    with TestClient(app(settings)) as client:
        assert client.post("/api/tasks", json={"title": "Prueba",
            "due_at": "2026-09-15T10:00:00Z", **changes}).status_code == 422
        assert client.get("/api/tasks").json() == []


def test_calendar_entries_keep_kind_and_end_time(settings):
    with TestClient(app(settings)) as client:
        meeting = client.post("/api/tasks", json={
            "title": "Asesoria con el director", "kind": "reunion",
            "due_at": "2026-09-22T09:00:00-05:00", "ends_at": "2026-09-22T10:30:00-05:00",
        })
        assert meeting.status_code == 201
        assert (meeting.json()["kind"], meeting.json()["ends_at"]) == (
            "reunion", "2026-09-22T15:30:00+00:00")
        reminder = client.post("/api/tasks", json={
            "title": "Pagar matricula", "kind": "recordatorio", "due_at": "2026-09-23T08:00:00Z",
        }).json()
        assert (reminder["kind"], reminder["ends_at"]) == ("recordatorio", None)
        # Editar puede quitar la hora de fin.
        edited = client.put(f"/api/tasks/{meeting.json()['id']}", json={
            "title": "Asesoria con el director", "kind": "reunion",
            "due_at": "2026-09-22T14:00:00Z",
        }).json()
        assert edited["ends_at"] is None


@pytest.mark.parametrize("changes", [
    {"kind": "evento"},
    {"ends_at": "2026-09-15T09:00:00Z"},
    {"ends_at": "2026-09-15T10:00:00Z"},
    {"ends_at": "2026-09-15T11:00:00"},
])
def test_calendar_entries_reject_invalid_kind_or_end(settings, changes):
    with TestClient(app(settings)) as client:
        assert client.post("/api/tasks", json={"title": "Prueba",
            "due_at": "2026-09-15T10:00:00Z", **changes}).status_code == 422


def test_tasks_created_before_calendar_default_to_task_kind(settings):
    import sqlite3
    from datetime import UTC, datetime

    from ruta_dia_agents.memory import NotebookMemory

    NotebookMemory(settings.memory_path).close()
    with sqlite3.connect(settings.memory_path) as db:
        now = datetime.now(UTC).isoformat()
        db.execute("INSERT INTO tasks (id, title, due_at, priority, notebook_id, completed, "
                   "created_at, updated_at) VALUES ('vieja', 'Tarea previa', ?, 'medium', "
                   "NULL, 0, ?, ?)", (now, now, now))
    with TestClient(app(settings)) as client:
        task = client.get("/api/tasks").json()[0]
        assert (task["kind"], task["ends_at"]) == ("tarea", None)


def test_tasks_unknown_project_and_origin(settings):
    with TestClient(app(settings)) as client:
        body = {"title": "Prueba", "due_at": "2026-09-15T10:00:00Z"}
        assert client.post("/api/tasks", json={**body, "notebook_id": "Ausente"}).status_code == 404
        assert client.post("/api/tasks", json=body,
                           headers={"origin": "http://otro"}).status_code == 403
        assert client.put("/api/tasks/ausente", json=body).status_code == 404


def events(response):
    return [
        json.loads(line.removeprefix("data: "))
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]


def test_notes_persist_are_isolated_and_do_not_become_verified_memory(settings):
    body = {"title": "Menos pasos", "text": "Probar una reserva con dos campos.",
            "color": "pink", "category": "prototipo", "source_text": "Fragmento del chat"}
    with TestClient(app(settings)) as client:
        for name in ["Uno", "Dos"]:
            assert client.post("/api/notebooks", json={"notebook_id": name}).status_code == 201
        created = client.post("/api/notebooks/Uno/notes", json=body)
        assert created.status_code == 201
        note_id = created.json()["id"]
        assert client.get("/api/notebooks/Dos").json()["notes"] == []
        assert client.put(f"/api/notebooks/Dos/notes/{note_id}", json=body).status_code == 404
        assert client.delete(f"/api/notebooks/Dos/notes/{note_id}").status_code == 404
        updated = client.put(f"/api/notebooks/Uno/notes/{note_id}", json={
            **body, "title": "Nuevo título", "color": "blue", "source_text": "No reemplazar origen",
        })
        assert updated.json()["source_text"] == body["source_text"]
    with TestClient(app(settings)) as client:
        data = client.get("/api/notebooks/Uno").json()
        assert data["notes"][0]["title"] == "Nuevo título"
        assert data["notes"][0]["color"] == "blue"
        assert data["state"]["validated_fields"] == {}
        assert data["turns"] == []
        assert client.delete(f"/api/notebooks/Uno/notes/{note_id}").status_code == 200
        assert client.get("/api/notebooks/Uno").json()["notes"] == []
        assert client.post("/api/notebooks/Uno/notes", json=body).status_code == 201
        assert client.delete("/api/notebooks/Uno").status_code == 200
        assert client.post("/api/notebooks", json={"notebook_id": "Uno"}).status_code == 201
        assert client.get("/api/notebooks/Uno").json()["notes"] == []


@pytest.mark.parametrize("changes", [
    {"title": "   "}, {"text": "\n "}, {"color": "invalid"}, {"category": "invalid"},
    {"title": "a" * 101}, {"text": "a" * 3001}, {"source_text": "a" * 3001},
])
def test_note_validation(settings, changes):
    with TestClient(app(settings)) as client:
        client.post("/api/notebooks", json={"notebook_id": "Uno"})
        assert client.post("/api/notebooks/Uno/notes", json={
            "title": "Idea", "text": "Texto", **changes,
        }).status_code == 422
        assert client.get("/api/notebooks/Uno").json()["notes"] == []


def test_notes_require_existing_notebook_and_same_origin(settings):
    with TestClient(app(settings)) as client:
        body = {"title": "Idea", "text": "Texto"}
        assert client.post("/api/notebooks/Inexistente/notes", json=body).status_code == 404
        assert client.post("/api/notebooks/Uno/notes", json=body,
                           headers={"origin": "http://otro-host"}).status_code == 403


def test_stream_uses_real_graph_events_and_restores_memory_after_reopening(settings):
    with TestClient(app(settings)) as client:
        response = client.post("/api/chat", json={"notebook_id": "tesis", "message": "PESTEL"})
        received = events(response)
        started_nodes = [e["node"] for e in received if e.get("status") == "started"]
        assert started_nodes == ["orchestrate", "guide", "verify", "finalize"]
        assert received[-1]["type"] == "result"
        assert received[-1]["result"]["verification"]["verdict"] == "approved"
        assert not any("candidate" in e for e in received)

    with TestClient(app(settings)) as client:
        notebook = client.get("/api/notebooks/tesis").json()
        assert notebook["state"]["active_tool"] == "pestel"
        assert len(notebook["turns"]) == 2
        assert notebook["turns"][-1]["metadata"]["verification"]["verdict"] == "approved"
        client.post("/api/notebooks", json={"notebook_id": "otro"})
        assert client.get("/api/notebooks/otro").json()["turns"] == []
        assert client.delete("/api/notebooks/tesis").status_code == 200
        assert client.get("/api/notebooks/tesis").status_code == 404


def test_second_turn_does_not_receive_the_previous_turn_verdict(settings):
    feedback = []

    class Runtime(FakeRuntime):
        def guide(self, *args, **kwargs):
            feedback.append(kwargs.get("retry_feedback"))
            return super().guide(*args, **kwargs)

    with TestClient(app(settings, lambda _: Runtime([Verdict.APPROVED]))) as client:
        for message in ["PESTEL", "Otra observación"]:
            assert events(client.post(
                "/api/chat", json={"notebook_id": "tesis", "message": message}
            ))[-1]["type"] == "result"
    assert feedback == [None, None]


def test_busy_model_rejects_a_second_generation_and_releases_the_lock(settings):
    entered = threading.Event()
    release = threading.Event()

    class SlowRuntime(FakeRuntime):
        def orchestrate(self, *args):
            entered.set()
            assert release.wait(timeout=5)
            return super().orchestrate(*args)

    with TestClient(app(settings, lambda _: SlowRuntime([Verdict.APPROVED]))) as client:
        with ThreadPoolExecutor(max_workers=1) as executor:
            first = executor.submit(
                client.post, "/api/chat", json={"notebook_id": "a", "message": "PESTEL"}
            )
            try:
                assert entered.wait(timeout=5)
                second = client.post(
                    "/api/chat", json={"notebook_id": "b", "message": "PESTEL"}
                )
                assert second.status_code == 409
                assert client.put("/api/notebooks/a/profile", json={
                    "context": {"question": "Nuevo reto"}, "color": "green",
                }).status_code == 409
            finally:
                release.set()
            assert events(first.result(timeout=5))[-1]["type"] == "result"
        assert client.get("/api/status").json()["busy"] is False


def test_errors_and_status_do_not_expose_api_keys(settings):
    class BrokenRuntime(FakeRuntime):
        def orchestrate(self, *args):
            raise RuntimeError("test-secret-never-exposed")

    with TestClient(app(settings, lambda _: BrokenRuntime([]))) as client:
        response = client.post("/api/chat", json={"notebook_id": "a", "message": "PESTEL"})
        assert events(response)[-1]["type"] == "error"
        assert settings.api_key not in response.text
        assert settings.api_key not in client.get("/api/status").text
        assert client.get("/api/status").json()["busy"] is False
        assert client.get("/api/notebooks/a").json()["turns"] == []


def test_rejects_cross_origin_changes_and_blank_messages(settings):
    with TestClient(app(settings)) as client:
        assert client.post(
            "/api/notebooks", json={"notebook_id": "a"},
            headers={"Origin": "https://untrusted.example"},
        ).status_code == 403
        assert client.post(
            "/api/chat", json={"notebook_id": "a", "message": "   "}
        ).status_code == 422
        assert client.post(
            "/api/notebooks", json={"notebook_id": "proyecto/otro"}
        ).status_code == 422
        assert client.get("/api/tools/inexistente").status_code == 404


def test_initial_context_and_color_reach_graph_and_profile_edits_survive_reopening(settings):
    received_states = []

    class ContextRuntime(FakeRuntime):
        def orchestrate(self, message, state, route_index):
            received_states.append(state)
            return super().orchestrate(message, state, route_index)

    context = {"question": "Reducir las llegadas tarde", "hypothesis": "El bus influye"}
    with TestClient(app(settings, lambda _: ContextRuntime([Verdict.APPROVED]))) as client:
        created = client.post("/api/notebooks", json={
            "notebook_id": "color", "context": context, "color": "yellow",
        })
        assert created.status_code == 201
        assert created.json()["validated_fields"] == {}
        assert client.post("/api/notebooks", json={"notebook_id": "color"}).status_code == 409
        assert events(client.post("/api/chat", json={
            "notebook_id": "color", "message": "PESTEL",
        }))[-1]["type"] == "result"
        edited = client.put("/api/notebooks/color/profile", json={
            "context": {**context, "objective": "Mejorar la asistencia"}, "color": "purple",
        })
        assert edited.status_code == 200
        assert len(client.get("/api/notebooks/color").json()["turns"]) == 2
        assert client.get("/api/notebooks").json()[0]["color"] == "purple"
        assert client.put("/api/notebooks/no-existe/profile", json={
            "context": context, "color": "gray",
        }).status_code == 404
    assert received_states[0].context.question == context["question"]
    assert received_states[0].color == "yellow"
    assert received_states[0].validated_fields == {}
    with TestClient(app(settings)) as client:
        restored = client.get("/api/notebooks/color").json()["state"]
        assert restored["color"] == "purple"
        assert restored["context"]["hypothesis"] == context["hypothesis"]


@pytest.mark.parametrize("body", [
    {"context": {"question": "   "}},
    {"context": {"question": "Reto"}, "color": "pink"},
    {"context": {"question": "Reto", "objective": "x" * 1501}},
])
def test_initial_profile_rejects_invalid_values(settings, body):
    with TestClient(app(settings)) as client:
        assert client.post("/api/notebooks", json={"notebook_id": "a", **body}).status_code == 422
