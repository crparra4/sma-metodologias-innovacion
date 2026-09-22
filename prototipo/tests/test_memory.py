import sqlite3
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from langgraph.checkpoint.sqlite import SqliteSaver

from ruta_dia_agents.contracts import (
    HandoffContract,
    NotebookColor,
    ProjectContext,
    ProjectState,
    Severity,
    TemplateUpdate,
    TurnResult,
    Verdict,
    VerificationResult,
)
from ruta_dia_agents.memory import NotebookMemory


def result(message="Siguiente pregunta"):
    return TurnResult(
        message=message,
        handoff=HandoffContract(
            intent="analizar",
            phase="Descubrimiento",
            stage=1,
            expertise="novel",
            recommendations=[{"tool_id": "pestel", "reason": "Pertinente"}],
            active_tool="pestel",
            context_summary="Prueba",
        ),
        verification=VerificationResult(
            verdict=Verdict.APPROVED,
            severity=Severity.NONE,
            source_tool_id="pestel",
        ),
        attempts=1,
        accepted_updates=[TemplateUpdate(field="factor", value="inflación")],
    )


def test_notebook_survives_reopening_and_loads_validated_fields(tmp_path):
    path = tmp_path / "notebooks.sqlite3"
    initial = ProjectState(notebook_id="tesis")

    with NotebookMemory(path) as memory:
        memory.save_exchange("La inflación afecta el proyecto", result(), initial)

    with NotebookMemory(path) as memory:
        restored = memory.load(initial)

    assert restored.active_tool == "pestel"
    assert restored.validated_fields == {"pestel": {"factor": "inflación"}}
    assert restored.recent_turns == [
        "Usuario: La inflación afecta el proyecto",
        "Asistente: Siguiente pregunta",
    ]


def test_memory_keeps_only_eight_recent_items_in_prompt_state(tmp_path):
    state = ProjectState(notebook_id="limite")
    with NotebookMemory(tmp_path / "notebooks.sqlite3") as memory:
        for index in range(5):
            state = memory.save_exchange(f"mensaje {index}", result(f"respuesta {index}"), state)

    assert len(state.recent_turns) == 8
    assert state.recent_turns[0] == "Usuario: mensaje 1"


def test_delete_removes_domain_memory_and_langgraph_checkpoint(tmp_path):
    memory_path = tmp_path / "notebooks.sqlite3"
    checkpoint_path = tmp_path / "checkpoints.sqlite3"
    with NotebookMemory(memory_path) as memory:
        memory.save_exchange("dato", result(), ProjectState(notebook_id="borrar"))
        assert memory.delete("borrar") is True
        assert memory.load(ProjectState(notebook_id="borrar")).recent_turns == []

    connection = sqlite3.connect(checkpoint_path, check_same_thread=False)
    saver = SqliteSaver(connection)
    saver.delete_thread("borrar")
    connection.close()


def test_migrates_old_notebooks_and_preserves_context_across_exchanges(tmp_path):
    path = tmp_path / "old.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.executescript("""
            CREATE TABLE notebooks (
                notebook_id TEXT PRIMARY KEY, phase TEXT NOT NULL, stage INTEGER NOT NULL,
                role TEXT NOT NULL, active_tool TEXT NOT NULL, completed_tools_json TEXT NOT NULL,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            INSERT INTO notebooks VALUES ('viejo', 'Descubrimiento', 1, '', '', '[]', 'hoy', 'hoy');
        """)
    with NotebookMemory(path) as memory:
        old = memory.load(ProjectState(notebook_id="viejo"))
        assert old.color == NotebookColor.BLUE
        assert old.context.question == ""
        context = ProjectContext(question="Reducir las llegadas tarde", hypothesis="El bus influye")
        updated = memory.update_profile("viejo", context, NotebookColor.YELLOW)
        assert updated.validated_fields == {}
        memory.save_exchange("Comencemos", result(), updated)
    with NotebookMemory(path) as memory:
        restored = memory.load(ProjectState(notebook_id="viejo"))
        assert restored.context == context
        assert restored.color == NotebookColor.YELLOW
        assert len(memory.history("viejo")) == 2
        assert "hypothesis" not in restored.validated_fields.get("pestel", {})
        assert memory.update_profile("inexistente", context, NotebookColor.GRAY) is None


def test_schema_migrations_are_safe_when_requests_open_memory_in_parallel(tmp_path):
    path = tmp_path / "parallel.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute(
            """
            CREATE TABLE tasks (
                id TEXT PRIMARY KEY, title TEXT NOT NULL, due_at TEXT NOT NULL,
                priority TEXT NOT NULL, notebook_id TEXT, completed INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            )
            """
        )

    workers = 8
    barrier = Barrier(workers)

    def open_memory(_):
        barrier.wait()
        with NotebookMemory(path) as memory:
            return {row["name"] for row in memory.connection.execute("PRAGMA table_info(tasks)")}

    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(open_memory, range(workers)))

    assert all({"kind", "ends_at"} <= columns for columns in results)
