from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from .contracts import NotebookColor, ProjectContext, ProjectState, TurnResult
from .notes import NoteRequest
from .tasks import TaskRequest


class EditConflict(Exception):
    """El registro cambio despues de que la persona empezo a editarlo."""

    def __init__(self, current: dict):
        super().__init__("El registro cambió mientras se editaba.")
        self.current = current


class NotebookMemory:
    """Memoria durable de negocio, independiente de los checkpoints de LangGraph."""

    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.connection = sqlite3.connect(path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA journal_mode = WAL")
        self.connection.execute("PRAGMA busy_timeout = 5000")
        self.connection.execute("PRAGMA foreign_keys = ON")
        self._setup()

    def _setup(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS notebooks (
                notebook_id TEXT PRIMARY KEY,
                phase TEXT NOT NULL,
                stage INTEGER NOT NULL,
                role TEXT NOT NULL,
                active_tool TEXT NOT NULL,
                completed_tools_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS turns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                notebook_id TEXT NOT NULL,
                role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                metadata_json TEXT,
                FOREIGN KEY (notebook_id) REFERENCES notebooks(notebook_id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_turns_notebook
                ON turns(notebook_id, id DESC);

            CREATE TABLE IF NOT EXISTS notes (
                id TEXT PRIMARY KEY,
                notebook_id TEXT NOT NULL,
                title TEXT NOT NULL,
                text TEXT NOT NULL,
                color TEXT NOT NULL,
                category TEXT NOT NULL,
                source_text TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (notebook_id) REFERENCES notebooks(notebook_id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_notes_notebook ON notes(notebook_id, created_at DESC);

            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                due_at TEXT NOT NULL,
                priority TEXT NOT NULL,
                notebook_id TEXT,
                completed INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (notebook_id) REFERENCES notebooks(notebook_id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS validated_fields (
                notebook_id TEXT NOT NULL,
                tool_id TEXT NOT NULL,
                field TEXT NOT NULL,
                value_json TEXT NOT NULL,
                source_turn_id INTEGER NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (notebook_id, tool_id, field),
                FOREIGN KEY (notebook_id) REFERENCES notebooks(notebook_id) ON DELETE CASCADE,
                FOREIGN KEY (source_turn_id) REFERENCES turns(id) ON DELETE CASCADE
            );
            """
        )
        # La interfaz carga tareas y proyectos en paralelo. Serializar la inspeccion y
        # las migraciones evita que dos conexiones vean la misma columna ausente e
        # intenten agregarla al mismo tiempo.
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            columns = {
                row["name"] for row in self.connection.execute("PRAGMA table_info(turns)")
            }
            if "metadata_json" not in columns:
                self.connection.execute("ALTER TABLE turns ADD COLUMN metadata_json TEXT")
            notebook_columns = {
                row["name"] for row in self.connection.execute("PRAGMA table_info(notebooks)")
            }
            for name, declaration in [
                ("context_json", "TEXT NOT NULL DEFAULT '{}'"),
                ("color", "TEXT NOT NULL DEFAULT 'blue'"),
            ]:
                if name not in notebook_columns:
                    self.connection.execute(
                        f"ALTER TABLE notebooks ADD COLUMN {name} {declaration}"
                    )
            task_columns = {
                row["name"] for row in self.connection.execute("PRAGMA table_info(tasks)")
            }
            # Tipo y hora de fin del calendario. Las tareas previas quedan como tipo tarea
            # y sin hora de fin, que es exactamente lo que eran.
            for name, declaration in [
                ("kind", "TEXT NOT NULL DEFAULT 'tarea'"),
                ("ends_at", "TEXT"),
            ]:
                if name not in task_columns:
                    self.connection.execute(
                        f"ALTER TABLE tasks ADD COLUMN {name} {declaration}"
                    )
            note_columns = {
                row["name"] for row in self.connection.execute("PRAGMA table_info(notes)")
            }
            # Autor de cada post-it: lo necesita un proyecto compartido. Las notas previas
            # quedan vacias hasta que la cuenta duena del almacenamiento las reclama.
            for name in ("author_id", "author_name"):
                if name not in note_columns:
                    self.connection.execute(
                        f"ALTER TABLE notes ADD COLUMN {name} TEXT NOT NULL DEFAULT ''"
                    )
            turn_columns = {
                row["name"] for row in self.connection.execute("PRAGMA table_info(turns)")
            }
            if "participant_id" not in turn_columns:
                self.connection.execute(
                    "ALTER TABLE turns ADD COLUMN participant_id TEXT NOT NULL DEFAULT ''"
                )
            task_columns = {
                row["name"] for row in self.connection.execute("PRAGMA table_info(tasks)")
            }
            for name in ("author_id", "author_name"):
                if name not in task_columns:
                    self.connection.execute(
                        f"ALTER TABLE tasks ADD COLUMN {name} TEXT NOT NULL DEFAULT ''"
                    )
        except Exception:
            self.connection.rollback()
            raise
        else:
            self.connection.commit()

    def create(self, state: ProjectState) -> ProjectState:
        now = datetime.now(UTC).isoformat()
        with self.connection:
            self.connection.execute(
                """
                INSERT OR IGNORE INTO notebooks (
                    notebook_id, phase, stage, role, active_tool,
                    completed_tools_json, created_at, updated_at, context_json, color
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    state.notebook_id, state.phase, state.stage, state.role, state.active_tool,
                    json.dumps(state.completed_tools), now, now,
                    state.context.model_dump_json(), state.color.value,
                ),
            )
        return self.load(state)

    def list_notebooks(self) -> list[dict]:
        rows = self.connection.execute(
            """
            SELECT n.notebook_id, n.stage, n.phase, n.active_tool, n.updated_at, n.color,
                (SELECT COUNT(*) FROM turns t WHERE t.notebook_id = n.notebook_id) AS turn_count,
                (SELECT content FROM turns t WHERE t.notebook_id = n.notebook_id
                 AND t.role = 'user' ORDER BY id LIMIT 1) AS preview
            FROM notebooks n ORDER BY n.updated_at DESC
            """
        ).fetchall()
        return [dict(row) for row in rows]

    def history(self, notebook_id: str, limit: int = 200,
                participant_id: str | None = None) -> list[dict]:
        participant_filter = " AND participant_id = ?" if participant_id is not None else ""
        parameters = ((notebook_id, participant_id, limit) if participant_id is not None
                      else (notebook_id, limit))
        rows = self.connection.execute(
            f"""
            SELECT id, role, content, created_at, metadata_json FROM turns
            WHERE notebook_id = ?{participant_filter} ORDER BY id DESC LIMIT ?
            """,
            parameters,
        ).fetchall()
        return [
            {
                "id": row["id"], "role": row["role"], "content": row["content"],
                "created_at": row["created_at"],
                "metadata": json.loads(row["metadata_json"]) if row["metadata_json"] else None,
            }
            for row in reversed(rows)
        ]

    def list_notes(self, notebook_id: str) -> list[dict]:
        return [dict(row) for row in self.connection.execute(
            "SELECT * FROM notes WHERE notebook_id = ? ORDER BY created_at DESC, id DESC",
            (notebook_id,),
        )]

    def save_note(
        self, notebook_id: str, note: NoteRequest, note_id: str | None = None,
        author: tuple[str, str] | None = None,
    ) -> dict | None:
        """Crea o edita un post-it. El autor se fija al crearlo y editar no lo cambia."""
        now = datetime.now(UTC).isoformat()
        with self.connection:
            if note_id:
                # La comparacion de version va dentro del mismo UPDATE: es atomica.
                version_check = " AND updated_at=?" if note.base_updated_at else ""
                cursor = self.connection.execute(
                    "UPDATE notes SET title=?, text=?, color=?, category=?, updated_at=? "
                    f"WHERE id=? AND notebook_id=?{version_check}",
                    (note.title, note.text, note.color, note.category, now, note_id, notebook_id,
                     *([note.base_updated_at] if note.base_updated_at else [])),
                )
                if not cursor.rowcount:
                    current = self.connection.execute(
                        "SELECT * FROM notes WHERE id=? AND notebook_id=?", (note_id, notebook_id)
                    ).fetchone()
                    if current is not None:
                        raise EditConflict(dict(current))
                    return None
            else:
                note_id = str(uuid4())
                author_id, author_name = author or ("", "")
                self.connection.execute(
                    "INSERT INTO notes (id, notebook_id, title, text, color, category, "
                    "source_text, created_at, updated_at, author_id, author_name) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (note_id, notebook_id, note.title, note.text, note.color, note.category,
                     note.source_text, now, now, author_id, author_name),
                )
        row = self.connection.execute("SELECT * FROM notes WHERE id=?", (note_id,)).fetchone()
        return dict(row)

    def claim_unattributed_notes(self, author_id: str, author_name: str) -> int:
        """Asigna las notas sin autor a la cuenta duena de este almacenamiento.

        Cada cuenta tiene su propia base, asi que una nota sin autor solo pudo
        escribirla su propietaria antes de que existiera el campo.
        """
        with self.connection:
            return self.connection.execute(
                "UPDATE notes SET author_id=?, author_name=? WHERE author_id=''",
                (author_id, author_name),
            ).rowcount

    def claim_unattributed_turns(self, participant_id: str) -> int:
        with self.connection:
            return self.connection.execute(
                "UPDATE turns SET participant_id=? WHERE participant_id=''", (participant_id,)
            ).rowcount

    def delete_note(self, notebook_id: str, note_id: str) -> bool:
        with self.connection:
            return bool(self.connection.execute(
                "DELETE FROM notes WHERE notebook_id=? AND id=?", (notebook_id, note_id),
            ).rowcount)

    def list_tasks(self) -> list[dict]:
        return [{**dict(row), "completed": bool(row["completed"])} for row in
                self.connection.execute("SELECT * FROM tasks ORDER BY completed, due_at, id")]

    def save_task(self, task: TaskRequest, task_id: str | None = None,
                  author: tuple[str, str] | None = None) -> dict | None:
        now = datetime.now(UTC).isoformat()
        fields = (task.title, task.due_at.isoformat(), task.priority,
                  task.notebook_id, int(task.completed), task.kind,
                  task.ends_at.isoformat() if task.ends_at else None)
        with self.connection:
            if task_id:
                version_check = " AND updated_at=?" if task.base_updated_at else ""
                result = self.connection.execute(
                    "UPDATE tasks SET title=?, due_at=?, priority=?, notebook_id=?, completed=?, "
                    f"kind=?, ends_at=?, updated_at=? WHERE id=?{version_check}",
                    (*fields, now, task_id,
                     *([task.base_updated_at] if task.base_updated_at else [])),
                )
                if not result.rowcount:
                    current = next((item for item in self.list_tasks() if item["id"] == task_id),
                                   None)
                    if current is not None:
                        raise EditConflict(current)
                    return None
            else:
                task_id = str(uuid4())
                author_id, author_name = author or ("", "")
                self.connection.execute(
                    "INSERT INTO tasks (id, title, due_at, priority, notebook_id, completed, "
                    "kind, ends_at, created_at, updated_at, author_id, author_name) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (task_id, *fields, now, now, author_id, author_name),
                )
        return next(task for task in self.list_tasks() if task["id"] == task_id)

    def delete_task(self, task_id: str) -> bool:
        with self.connection:
            result = self.connection.execute("DELETE FROM tasks WHERE id=?", (task_id,))
            return bool(result.rowcount)

    def load(self, default: ProjectState, participant_id: str | None = None,
             shared_context: list[str] | None = None) -> ProjectState:
        row = self.connection.execute(
            "SELECT * FROM notebooks WHERE notebook_id = ?", (default.notebook_id,)
        ).fetchone()
        if row is None:
            return default

        participant_filter = " AND participant_id = ?" if participant_id is not None else ""
        parameters = ((default.notebook_id, participant_id, 8)
                      if participant_id is not None else (default.notebook_id, 8))
        recent = self.connection.execute(
            f"""
            SELECT role, content FROM turns
            WHERE notebook_id = ?{participant_filter} ORDER BY id DESC LIMIT ?
            """,
            parameters,
        ).fetchall()
        fields = self.connection.execute(
            """
            SELECT tool_id, field, value_json FROM validated_fields
            WHERE notebook_id = ? ORDER BY tool_id, field
            """,
            (default.notebook_id,),
        ).fetchall()
        validated: dict[str, dict] = {}
        for item in fields:
            validated.setdefault(item["tool_id"], {})[item["field"]] = json.loads(
                item["value_json"]
            )
        labels = {"user": "Usuario", "assistant": "Asistente"}
        return ProjectState(
            notebook_id=row["notebook_id"],
            phase=row["phase"],
            stage=row["stage"],
            role=row["role"],
            active_tool=row["active_tool"],
            completed_tools=json.loads(row["completed_tools_json"]),
            recent_turns=[
                f"{labels[item['role']]}: {item['content']}" for item in reversed(recent)
            ],
            shared_context=shared_context or [],
            validated_fields=validated,
            context=ProjectContext.model_validate_json(row["context_json"]),
            color=row["color"],
        )

    def update_profile(
        self, notebook_id: str, context: ProjectContext, color: NotebookColor
    ) -> ProjectState | None:
        with self.connection:
            cursor = self.connection.execute(
                "UPDATE notebooks SET context_json = ?, color = ?, updated_at = ? "
                "WHERE notebook_id = ?",
                (
                    context.model_dump_json(), color.value,
                    datetime.now(UTC).isoformat(), notebook_id,
                ),
            )
        return self.load(ProjectState(notebook_id=notebook_id)) if cursor.rowcount else None

    def save_exchange(
        self, message: str, result: TurnResult, previous: ProjectState,
        participant_id: str = "",
    ) -> ProjectState:
        now = datetime.now(UTC).isoformat()
        next_state = previous.model_copy(
            update={
                "phase": result.handoff.phase,
                "stage": result.handoff.stage,
                "active_tool": result.handoff.active_tool,
                "recent_turns": [
                    *previous.recent_turns,
                    f"Usuario: {message}",
                    f"Asistente: {result.message}",
                ][-8:],
            }
        )
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO notebooks (
                    notebook_id, phase, stage, role, active_tool,
                    completed_tools_json, created_at, updated_at, context_json, color
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(notebook_id) DO UPDATE SET
                    phase = excluded.phase,
                    stage = excluded.stage,
                    role = excluded.role,
                    active_tool = excluded.active_tool,
                    completed_tools_json = excluded.completed_tools_json,
                    updated_at = excluded.updated_at
                """,
                (
                    next_state.notebook_id,
                    next_state.phase,
                    next_state.stage,
                    next_state.role,
                    next_state.active_tool,
                    json.dumps(next_state.completed_tools, ensure_ascii=False),
                    now,
                    now,
                    next_state.context.model_dump_json(),
                    next_state.color.value,
                ),
            )
            user_cursor = self.connection.execute(
                "INSERT INTO turns (notebook_id, role, content, created_at, participant_id) "
                "VALUES (?, ?, ?, ?, ?)",
                (next_state.notebook_id, "user", message, now, participant_id),
            )
            self.connection.execute(
                """
                INSERT INTO turns (
                    notebook_id, role, content, created_at, metadata_json, participant_id
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    next_state.notebook_id, "assistant", result.message, now,
                    result.model_dump_json(), participant_id,
                ),
            )
            for update in result.accepted_updates:
                self.connection.execute(
                    """
                    INSERT INTO validated_fields (
                        notebook_id, tool_id, field, value_json, source_turn_id, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(notebook_id, tool_id, field) DO UPDATE SET
                        value_json = excluded.value_json,
                        source_turn_id = excluded.source_turn_id,
                        updated_at = excluded.updated_at
                    """,
                    (
                        next_state.notebook_id,
                        result.handoff.active_tool,
                        update.field,
                        json.dumps(update.value, ensure_ascii=False),
                        user_cursor.lastrowid,
                        now,
                    ),
                )
        return self.load(next_state, participant_id, previous.shared_context)

    def save_private_exchange(
        self, message: str, result: TurnResult, previous: ProjectState, participant_id: str
    ) -> ProjectState:
        """Guarda el chat del lector sin cambiar etapa ni memoria común del proyecto."""
        now = datetime.now(UTC).isoformat()
        with self.connection:
            self.connection.execute(
                "INSERT INTO turns (notebook_id, role, content, created_at, participant_id) "
                "VALUES (?, 'user', ?, ?, ?)",
                (previous.notebook_id, message, now, participant_id),
            )
            self.connection.execute(
                "INSERT INTO turns (notebook_id, role, content, created_at, "
                "metadata_json, participant_id) "
                "VALUES (?, 'assistant', ?, ?, ?, ?)",
                (
                    previous.notebook_id, result.message, now,
                    result.model_dump_json(), participant_id,
                ),
            )
        return self.load(previous, participant_id, previous.shared_context)

    def delete(self, notebook_id: str) -> bool:
        with self.connection:
            cursor = self.connection.execute(
                "DELETE FROM notebooks WHERE notebook_id = ?", (notebook_id,)
            )
        return cursor.rowcount > 0

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> NotebookMemory:
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()
