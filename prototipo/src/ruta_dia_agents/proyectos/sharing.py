from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path

from ..compartido.errores import Conflicto, NoEncontrado, SinPermiso
from ..herramientas.empathy_map import empty_empathy_map
from ..herramientas.journey import empty_journey
from ..herramientas.pestel import empty_pestel
from ..herramientas.problem_tree import MAX_NODES, ProblemTreeUpdate
from ..herramientas.why_analysis import apply_turn, review_notice


class SharingStore:
    """Registro local de proyectos, miembros, invitaciones y avances comunes."""

    def __init__(self, path: Path):
        self.path = path
        with self._connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS shared_projects (
                    id TEXT PRIMARY KEY,
                    owner_user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    notebook_id TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    UNIQUE(owner_user_id, notebook_id)
                );
                CREATE TABLE IF NOT EXISTS project_members (
                    project_id TEXT NOT NULL REFERENCES shared_projects(id) ON DELETE CASCADE,
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    role TEXT NOT NULL CHECK(role IN ('viewer', 'editor')),
                    joined_at INTEGER NOT NULL,
                    PRIMARY KEY(project_id, user_id)
                );
                CREATE TABLE IF NOT EXISTS project_invitations (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL REFERENCES shared_projects(id) ON DELETE CASCADE,
                    invited_by TEXT NOT NULL REFERENCES users(id),
                    invited_user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    role TEXT NOT NULL CHECK(role IN ('viewer', 'editor')),
                    status TEXT NOT NULL CHECK(
                        status IN ('pending', 'accepted', 'rejected', 'cancelled')
                    ),
                    created_at INTEGER NOT NULL,
                    responded_at INTEGER
                );
                CREATE UNIQUE INDEX IF NOT EXISTS pending_project_invitation
                    ON project_invitations(project_id, invited_user_id) WHERE status='pending';
                CREATE TABLE IF NOT EXISTS project_advances (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL REFERENCES shared_projects(id) ON DELETE CASCADE,
                    content TEXT NOT NULL,
                    kind TEXT NOT NULL CHECK(
                        kind IN ('decision', 'finding', 'hypothesis', 'next_step', 'other')
                    ),
                    status TEXT NOT NULL DEFAULT 'confirmed' CHECK(
                        status IN ('proposed', 'confirmed', 'superseded')
                    ),
                    author_id TEXT NOT NULL REFERENCES users(id),
                    author_name TEXT NOT NULL,
                    version INTEGER NOT NULL DEFAULT 1,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS project_problem_trees (
                    project_id TEXT PRIMARY KEY REFERENCES shared_projects(id) ON DELETE CASCADE,
                    content TEXT NOT NULL,
                    version INTEGER NOT NULL DEFAULT 1,
                    updated_by TEXT NOT NULL REFERENCES users(id),
                    updated_at INTEGER NOT NULL
                );
                -- Último diagnóstico, ya en texto breve para el contexto del agente.
                -- tree_version indica a qué versión del árbol corresponde.
                -- Un análisis de 5 porqués por fila, ligado a la causa del árbol de la que parte.
                -- Solo uno puede estar en curso por proyecto: es el que recibe las respuestas.
                CREATE TABLE IF NOT EXISTS project_why_analyses (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL REFERENCES shared_projects(id) ON DELETE CASCADE,
                    cause_id TEXT NOT NULL,
                    cause_text TEXT NOT NULL,
                    problem_text TEXT NOT NULL,
                    steps_json TEXT NOT NULL DEFAULT '[]',
                    doubts_json TEXT NOT NULL DEFAULT '[]',
                    status TEXT NOT NULL DEFAULT 'en_curso',
                    started INTEGER NOT NULL DEFAULT 0,
                    reviewing INTEGER NOT NULL DEFAULT 0,
                    awaiting_plan INTEGER NOT NULL DEFAULT 0,
                    candidate TEXT NOT NULL DEFAULT '',
                    incorporated_node_id TEXT NOT NULL DEFAULT '',
                    created_by TEXT NOT NULL REFERENCES users(id),
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL
                );
                CREATE UNIQUE INDEX IF NOT EXISTS one_active_why_analysis
                    ON project_why_analyses(project_id) WHERE status = 'en_curso';
                -- Un PESTEL por proyecto, con la misma edición por versiones que el árbol.
                CREATE TABLE IF NOT EXISTS project_pestels (
                    project_id TEXT PRIMARY KEY REFERENCES shared_projects(id) ON DELETE CASCADE,
                    content TEXT NOT NULL,
                    version INTEGER NOT NULL DEFAULT 1,
                    updated_by TEXT NOT NULL REFERENCES users(id),
                    updated_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS project_empathy_maps (
                    project_id TEXT PRIMARY KEY REFERENCES shared_projects(id) ON DELETE CASCADE,
                    content TEXT NOT NULL,
                    version INTEGER NOT NULL DEFAULT 1,
                    updated_by TEXT NOT NULL REFERENCES users(id),
                    updated_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS project_journeys (
                    project_id TEXT PRIMARY KEY REFERENCES shared_projects(id) ON DELETE CASCADE,
                    content TEXT NOT NULL,
                    version INTEGER NOT NULL DEFAULT 1,
                    updated_by TEXT NOT NULL REFERENCES users(id),
                    updated_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS project_tree_diagnoses (
                    project_id TEXT PRIMARY KEY REFERENCES shared_projects(id) ON DELETE CASCADE,
                    tree_version INTEGER NOT NULL,
                    summary TEXT NOT NULL,
                    created_at INTEGER NOT NULL
                );
            """)
            # Qué notó el código en el último mensaje del análisis (why_analysis.apply_turn).
            why_columns = {
                row["name"] for row in db.execute("PRAGMA table_info(project_why_analyses)")
            }
            if "notice" not in why_columns:
                db.execute(
                    "ALTER TABLE project_why_analyses ADD COLUMN notice TEXT NOT NULL DEFAULT ''"
                )

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=5000")
        return db

    def ensure_project(self, owner_user_id: str, notebook_id: str) -> str:
        with self._connect() as db:
            row = db.execute(
                "SELECT id FROM shared_projects WHERE owner_user_id=? AND notebook_id=?",
                (owner_user_id, notebook_id),
            ).fetchone()
            if row:
                return row["id"]
            project_id = uuid.uuid4().hex
            db.execute(
                "INSERT INTO shared_projects VALUES (?, ?, ?, ?)",
                (project_id, owner_user_id, notebook_id, int(time.time())),
            )
            return project_id

    def delete_project(self, project_id: str) -> None:
        with self._connect() as db:
            db.execute("DELETE FROM shared_projects WHERE id=?", (project_id,))

    def problem_tree(self, project_id: str) -> dict:
        with self._connect() as db:
            row = db.execute(
                "SELECT content, version, updated_at FROM project_problem_trees WHERE project_id=?",
                (project_id,),
            ).fetchone()
        if not row:
            return {"problem": "", "problem_source": "", "causes": [], "effects": [],
                    "version": 0, "updated_at": None}
        return {**json.loads(row["content"]), "version": row["version"],
                "updated_at": row["updated_at"]}

    def save_tree_diagnosis(self, project_id: str, tree_version: int, summary: str) -> None:
        with self._connect() as db:
            db.execute("""
                INSERT INTO project_tree_diagnoses VALUES (?, ?, ?, ?)
                ON CONFLICT(project_id) DO UPDATE SET
                    tree_version=excluded.tree_version, summary=excluded.summary,
                    created_at=excluded.created_at
            """, (project_id, tree_version, summary, int(time.time())))

    def tree_diagnosis(self, project_id: str) -> dict | None:
        with self._connect() as db:
            row = db.execute(
                "SELECT tree_version, summary FROM project_tree_diagnoses WHERE project_id=?",
                (project_id,),
            ).fetchone()
        return dict(row) if row else None

    # ── Análisis de 5 porqués ────────────────────────────────────────────────
    @staticmethod
    def _why(row: sqlite3.Row) -> dict:
        return {
            "id": row["id"], "cause_id": row["cause_id"], "cause_text": row["cause_text"],
            "problem_text": row["problem_text"], "steps": json.loads(row["steps_json"]),
            "doubts": json.loads(row["doubts_json"]), "status": row["status"],
            "reviewing": bool(row["reviewing"]), "awaiting_plan": bool(row["awaiting_plan"]),
            # reviewing es 1 al pedir la revisión y suma uno por cada mensaje durante ella.
            "review_turns": max(0, row["reviewing"] - 1), "notice": row["notice"],
            "candidate": row["candidate"],
            "incorporated_node_id": row["incorporated_node_id"],
            "created_at": row["created_at"], "updated_at": row["updated_at"],
        }

    def why_analyses(self, project_id: str) -> list[dict]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT * FROM project_why_analyses WHERE project_id=? ORDER BY created_at DESC",
                (project_id,),
            ).fetchall()
        return [self._why(row) for row in rows]

    def _why_row(self, db: sqlite3.Connection, project_id: str, analysis_id: str) -> sqlite3.Row:
        row = db.execute(
            "SELECT * FROM project_why_analyses WHERE project_id=? AND id=?",
            (project_id, analysis_id),
        ).fetchone()
        if not row:
            raise NoEncontrado("El análisis no existe en este proyecto.")
        return row

    def active_why_analysis(self, project_id: str) -> dict | None:
        with self._connect() as db:
            row = db.execute(
                "SELECT * FROM project_why_analyses WHERE project_id=? AND status='en_curso'",
                (project_id,),
            ).fetchone()
        return self._why(row) if row else None

    def start_why_analysis(self, project_id: str, user_id: str, cause_id: str) -> dict:
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            active = db.execute(
                "SELECT cause_text FROM project_why_analyses "
                "WHERE project_id=? AND status='en_curso'", (project_id,),
            ).fetchone()
            if active:
                raise Conflicto(
                    f"Ya hay un análisis de 5 porqués en curso sobre «{active['cause_text']}». "
                    "Termínalo o descártalo antes de empezar otro."
                )
            row = db.execute(
                "SELECT content FROM project_problem_trees WHERE project_id=?", (project_id,),
            ).fetchone()
            tree = json.loads(row["content"]) if row else {}
            cause = next(
                (node for node in tree.get("causes", []) if node["id"] == cause_id), None,
            )
            if cause is None:
                raise NoEncontrado("Esa causa no está en el árbol guardado.")
            if cause.get("parent"):
                raise Conflicto(
                    "Los 5 porqués parten de una causa principal: una causa de fondo ya no "
                    "admite otra debajo."
                )
            now = int(time.time())
            analysis_id = uuid.uuid4().hex
            db.execute("""
                INSERT INTO project_why_analyses (
                    id, project_id, cause_id, cause_text, problem_text,
                    created_by, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (analysis_id, project_id, cause_id, cause["text"], tree.get("problem", ""),
                  user_id, now, now))
            return self._why(self._why_row(db, project_id, analysis_id))

    def record_why_turn(self, project_id: str, message: str) -> dict | None:
        """Registra el mensaje en el análisis en curso, antes de que responda el agente.

        El primer mensaje solo abre el análisis. Durante la revisión, lo que se escribe
        comenta la cadena y no es un paso nuevo. El resto lo decide why_analysis.apply_turn.
        """
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT * FROM project_why_analyses WHERE project_id=? AND status='en_curso'",
                (project_id,),
            ).fetchone()
            if not row:
                return None
            analysis = self._why(row)
            if not row["started"]:
                db.execute("UPDATE project_why_analyses SET started=1 WHERE id=?", (row["id"],))
            elif analysis["reviewing"]:
                db.execute(
                    "UPDATE project_why_analyses SET reviewing=reviewing+1, notice=?, "
                    "updated_at=? WHERE id=?",
                    (review_notice(message), int(time.time()), row["id"]),
                )
            else:
                turn = apply_turn(analysis, message)
                db.execute(
                    "UPDATE project_why_analyses SET steps_json=?, doubts_json=?, "
                    "awaiting_plan=?, notice=?, updated_at=? WHERE id=?",
                    (json.dumps(turn["steps"], ensure_ascii=False),
                     json.dumps(turn["doubts"], ensure_ascii=False),
                     int(turn["awaiting_plan"]), turn["notice"], int(time.time()), row["id"]),
                )
            return self._why(self._why_row(db, project_id, row["id"]))

    def update_why_analysis(self, project_id: str, analysis_id: str, changes: dict) -> dict:
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = self._why_row(db, project_id, analysis_id)
            if row["status"] != "en_curso":
                raise Conflicto("El análisis ya terminó; no se puede editar.")
            columns = {"steps": "steps_json", "doubts": "doubts_json"}
            texts = [step["text"] for step in json.loads(row["steps_json"])]
            if "steps" in changes and [step["text"] for step in changes["steps"]] != texts:
                # Quitar un paso cambia la última respuesta: el aviso anterior ya no aplica.
                db.execute("UPDATE project_why_analyses SET notice='' WHERE id=?", (analysis_id,))
            for key, value in changes.items():
                db.execute(
                    f"UPDATE project_why_analyses SET {columns[key]}=? WHERE id=?",
                    (json.dumps(value, ensure_ascii=False), analysis_id),
                )
            db.execute("UPDATE project_why_analyses SET updated_at=? WHERE id=?",
                       (int(time.time()), analysis_id))
            return self._why(self._why_row(db, project_id, analysis_id))

    def set_why_status(self, project_id: str, analysis_id: str, *, reviewing: bool | None = None,
                       status: str | None = None, candidate: str | None = None) -> dict:
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = self._why_row(db, project_id, analysis_id)
            if row["status"] != "en_curso":
                raise Conflicto("El análisis ya terminó.")
            if status == "cerrado" and not json.loads(row["steps_json"]):
                raise Conflicto("Registra al menos una respuesta antes de cerrar.")
            if reviewing is not None:
                db.execute("UPDATE project_why_analyses SET reviewing=?, notice='' WHERE id=?",
                           (int(reviewing), analysis_id))
            if candidate is not None:
                db.execute("UPDATE project_why_analyses SET candidate=? WHERE id=?",
                           (candidate, analysis_id))
            if status is not None:
                db.execute("UPDATE project_why_analyses SET status=? WHERE id=?",
                           (status, analysis_id))
            db.execute("UPDATE project_why_analyses SET updated_at=? WHERE id=?",
                       (int(time.time()), analysis_id))
            return self._why(self._why_row(db, project_id, analysis_id))

    def incorporate_why_analysis(self, project_id: str, analysis_id: str, user_id: str) -> dict:
        """Agrega la causa candidata como causa de fondo de la tarjeta de partida."""
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = self._why_row(db, project_id, analysis_id)
            if row["status"] != "cerrado":
                raise Conflicto("Cierra el análisis y elige la causa candidata primero.")
            if row["incorporated_node_id"]:
                raise Conflicto("Esta causa candidata ya está en el árbol.")
            tree_row = db.execute(
                "SELECT content, version FROM project_problem_trees WHERE project_id=?",
                (project_id,),
            ).fetchone()
            if not tree_row:
                raise NoEncontrado("El proyecto ya no tiene árbol guardado.")
            tree = json.loads(tree_row["content"])
            origin = next(
                (node for node in tree["causes"] if node["id"] == row["cause_id"]), None,
            )
            if origin is None:
                raise Conflicto("La causa de partida ya no está en el árbol.")
            if origin.get("parent"):
                raise Conflicto(
                    "La causa de partida ahora es una causa de fondo y no admite otra debajo."
                )
            if len(tree["causes"]) >= MAX_NODES:
                raise Conflicto("El árbol ya tiene el máximo de causas.")
            steps = json.loads(row["steps_json"])
            evidence = steps[-1]["evidence"] if steps and steps[-1]["evidence"] else ""
            node_id = f"w{uuid.uuid4().hex[:12]}"
            tree["causes"].append({
                "id": node_id, "text": row["candidate"][:240], "parent": row["cause_id"],
                "source": (f"{evidence} · " if evidence else "") + "Análisis de 5 porqués",
            })
            # Misma validación que al guardar el árbol desde el tablero.
            ProblemTreeUpdate(version=tree_row["version"], **tree)
            now = int(time.time())
            db.execute(
                "UPDATE project_problem_trees SET content=?, version=?, updated_by=?, updated_at=? "
                "WHERE project_id=?",
                (json.dumps(tree, ensure_ascii=False), tree_row["version"] + 1, user_id, now,
                 project_id),
            )
            db.execute(
                "UPDATE project_why_analyses SET incorporated_node_id=?, updated_at=? WHERE id=?",
                (node_id, now, analysis_id),
            )
            return {"node_id": node_id, "tree_version": tree_row["version"] + 1}

    def save_problem_tree(self, project_id: str, user_id: str, content: dict,
                          version: int) -> dict:
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            access = db.execute("""
                SELECT CASE WHEN p.owner_user_id=? THEN 'owner' ELSE m.role END AS role
                FROM shared_projects p
                LEFT JOIN project_members m ON m.project_id=p.id AND m.user_id=?
                WHERE p.id=? AND (p.owner_user_id=? OR m.user_id=?)
            """, (user_id, user_id, project_id, user_id, user_id)).fetchone()
            if not access or access["role"] not in {"owner", "editor"}:
                raise SinPermiso("Tu permiso no permite editar este árbol.")
            row = db.execute(
                "SELECT version FROM project_problem_trees WHERE project_id=?",
                (project_id,),
            ).fetchone()
            current_version = row["version"] if row else 0
            if current_version != version:
                raise Conflicto(
                    "Otra persona modificó el árbol. "
                    "Actualiza la página para ver la versión actual.",
                )
            now = int(time.time())
            payload = json.dumps(content, ensure_ascii=False)
            if row:
                db.execute("""
                    UPDATE project_problem_trees
                    SET content=?, version=?, updated_by=?, updated_at=? WHERE project_id=?
                """, (payload, version + 1, user_id, now, project_id))
            else:
                db.execute("INSERT INTO project_problem_trees VALUES (?, ?, 1, ?, ?)",
                           (project_id, payload, user_id, now))
        return {**content, "version": version + 1, "updated_at": now}

    # Tableros de una ficha (PESTEL, mapa de empatía): un documento por proyecto, guardado por
    # versiones para que dos personas no se pisen. El nombre de la tabla nunca viene de fuera.
    def _board(self, table: str, project_id: str, empty: dict) -> dict:
        with self._connect() as db:
            row = db.execute(
                f"SELECT content, version, updated_at FROM {table} WHERE project_id=?",
                (project_id,),
            ).fetchone()
        if not row:
            return empty
        return {**json.loads(row["content"]), "version": row["version"],
                "updated_at": row["updated_at"]}

    def _save_board(self, table: str, name: str, project_id: str, user_id: str,
                    content: dict, version: int) -> dict:
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            access = db.execute("""
                SELECT CASE WHEN p.owner_user_id=? THEN 'owner' ELSE m.role END AS role
                FROM shared_projects p
                LEFT JOIN project_members m ON m.project_id=p.id AND m.user_id=?
                WHERE p.id=? AND (p.owner_user_id=? OR m.user_id=?)
            """, (user_id, user_id, project_id, user_id, user_id)).fetchone()
            if not access or access["role"] not in {"owner", "editor"}:
                raise SinPermiso(f"Tu permiso no permite editar este {name}.")
            row = db.execute(
                f"SELECT version FROM {table} WHERE project_id=?", (project_id,),
            ).fetchone()
            if (row["version"] if row else 0) != version:
                raise Conflicto(
                    f"Otra persona modificó el {name}. "
                    "Actualiza la página para ver la versión actual.",
                )
            now = int(time.time())
            payload = json.dumps(content, ensure_ascii=False)
            if row:
                db.execute(
                    f"UPDATE {table} SET content=?, version=?, updated_by=?, updated_at=? "
                    "WHERE project_id=?", (payload, version + 1, user_id, now, project_id),
                )
            else:
                db.execute(f"INSERT INTO {table} VALUES (?, ?, 1, ?, ?)",
                           (project_id, payload, user_id, now))
        return {**content, "version": version + 1, "updated_at": now}

    def pestel(self, project_id: str) -> dict:
        return self._board("project_pestels", project_id, empty_pestel())

    def save_pestel(self, project_id: str, user_id: str, content: dict, version: int) -> dict:
        return self._save_board("project_pestels", "PESTEL", project_id, user_id, content,
                                version)

    def journey(self, project_id: str) -> dict:
        return self._board("project_journeys", project_id, empty_journey())

    def save_journey(self, project_id: str, user_id: str, content: dict, version: int) -> dict:
        return self._save_board("project_journeys", "recorrido", project_id, user_id, content,
                                version)

    def empathy_map(self, project_id: str) -> dict:
        return self._board("project_empathy_maps", project_id, empty_empathy_map())

    def save_empathy_map(self, project_id: str, user_id: str, content: dict,
                         version: int) -> dict:
        return self._save_board("project_empathy_maps", "mapa de empatía", project_id, user_id,
                                content, version)

    def accessible(self, user_id: str) -> list[dict]:
        with self._connect() as db:
            rows = db.execute("""
                SELECT p.id AS project_id, p.owner_user_id, p.notebook_id,
                       u.display_name AS owner_name, u.username AS owner_username,
                       CASE WHEN p.owner_user_id=? THEN 'owner' ELSE m.role END AS role
                FROM shared_projects p
                JOIN users u ON u.id=p.owner_user_id
                LEFT JOIN project_members m ON m.project_id=p.id AND m.user_id=?
                WHERE p.owner_user_id=? OR m.user_id=?
                ORDER BY p.created_at DESC
            """, (user_id, user_id, user_id, user_id)).fetchall()
        return [dict(row) for row in rows]

    def access(self, user_id: str, reference: str) -> dict | None:
        with self._connect() as db:
            row = db.execute("""
                SELECT p.id AS project_id, p.owner_user_id, p.notebook_id,
                       u.display_name AS owner_name, u.username AS owner_username,
                       CASE WHEN p.owner_user_id=? THEN 'owner' ELSE m.role END AS role
                FROM shared_projects p
                JOIN users u ON u.id=p.owner_user_id
                LEFT JOIN project_members m ON m.project_id=p.id AND m.user_id=?
                WHERE (p.id=? OR (p.owner_user_id=? AND p.notebook_id=?))
                  AND (p.owner_user_id=? OR m.user_id=?)
            """, (user_id, user_id, reference, user_id, reference, user_id, user_id)).fetchone()
        return dict(row) if row else None

    def invite(self, project_id: str, owner_id: str, username: str, role: str) -> dict:
        with self._connect() as db:
            project = db.execute(
                "SELECT 1 FROM shared_projects WHERE id=? AND owner_user_id=?",
                (project_id, owner_id),
            ).fetchone()
            if not project:
                raise SinPermiso("Solo el propietario puede compartir este proyecto.")
            target = db.execute(
                "SELECT id, username, display_name FROM users WHERE username=?",
                (username.strip().lower(),),
            ).fetchone()
            if not target:
                raise NoEncontrado("No existe una cuenta con ese usuario.")
            if target["id"] == owner_id:
                raise Conflicto("Ya eres la persona propietaria del proyecto.")
            if db.execute(
                "SELECT 1 FROM project_members WHERE project_id=? AND user_id=?",
                (project_id, target["id"]),
            ).fetchone():
                raise Conflicto("Esa persona ya tiene acceso al proyecto.")
            invitation_id = uuid.uuid4().hex
            try:
                db.execute(
                    "INSERT INTO project_invitations VALUES (?, ?, ?, ?, ?, 'pending', ?, NULL)",
                    (invitation_id, project_id, owner_id, target["id"], role, int(time.time())),
                )
            except sqlite3.IntegrityError as exc:
                raise Conflicto("Esa persona ya tiene una invitación pendiente.") from exc
            return {"id": invitation_id, "username": target["username"],
                    "display_name": target["display_name"], "role": role, "status": "pending"}

    def invitations(self, user_id: str) -> list[dict]:
        with self._connect() as db:
            rows = db.execute("""
                SELECT i.id, i.role, i.created_at, p.notebook_id, p.id AS project_id,
                       u.display_name AS owner_name, u.username AS owner_username
                FROM project_invitations i
                JOIN shared_projects p ON p.id=i.project_id
                JOIN users u ON u.id=p.owner_user_id
                WHERE i.invited_user_id=? AND i.status='pending'
                ORDER BY i.created_at DESC
            """, (user_id,)).fetchall()
        return [dict(row) for row in rows]

    def respond(self, invitation_id: str, user_id: str, accept: bool) -> None:
        now = int(time.time())
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            invitation = db.execute(
                "SELECT project_id, role FROM project_invitations "
                "WHERE id=? AND invited_user_id=? AND status='pending'",
                (invitation_id, user_id),
            ).fetchone()
            if not invitation:
                raise NoEncontrado("La invitación ya no está disponible.")
            status = "accepted" if accept else "rejected"
            db.execute(
                "UPDATE project_invitations SET status=?, responded_at=? WHERE id=?",
                (status, now, invitation_id),
            )
            if accept:
                db.execute(
                    "INSERT INTO project_members VALUES (?, ?, ?, ?) "
                    "ON CONFLICT(project_id,user_id) DO UPDATE SET role=excluded.role",
                    (invitation["project_id"], user_id, invitation["role"], now),
                )

    def members(self, project_id: str, requester_id: str) -> list[dict]:
        with self._connect() as db:
            project = db.execute("""
                SELECT p.owner_user_id, u.username, u.display_name,
                       CASE WHEN u.avatar IS NULL THEN 0 ELSE u.avatar_version END AS avatar
                FROM shared_projects p JOIN users u ON u.id=p.owner_user_id
                LEFT JOIN project_members m ON m.project_id=p.id AND m.user_id=?
                WHERE p.id=? AND (p.owner_user_id=? OR m.user_id=?)
            """, (requester_id, project_id, requester_id, requester_id)).fetchone()
            if not project:
                raise SinPermiso("No tienes acceso a este proyecto.")
            members = db.execute("""
                SELECT m.user_id, m.role, u.username, u.display_name,
                       CASE WHEN u.avatar IS NULL THEN 0 ELSE u.avatar_version END AS avatar
                FROM project_members m JOIN users u ON u.id=m.user_id
                WHERE m.project_id=? ORDER BY m.joined_at
            """, (project_id,)).fetchall()
            pending = db.execute("""
                SELECT i.id, i.role, u.username, u.display_name,
                       CASE WHEN u.avatar IS NULL THEN 0 ELSE u.avatar_version END AS avatar
                FROM project_invitations i JOIN users u ON u.id=i.invited_user_id
                WHERE i.project_id=? AND i.status='pending'
                ORDER BY i.created_at, i.rowid
            """, (project_id,)).fetchall() if project["owner_user_id"] == requester_id else []
        return [{"user_id": project["owner_user_id"], "username": project["username"],
                 "display_name": project["display_name"], "avatar": project["avatar"],
                 "role": "owner"},
                *[dict(row) for row in members],
                *[{**dict(row), "status": "pending"} for row in pending]]

    def shares_project(self, user_id: str, other_id: str) -> bool:
        """Si las dos cuentas coinciden en algún proyecto (dueño, miembro o invitación
        pendiente). Es lo que decide quién puede ver la foto de perfil de quién."""
        with self._connect() as db:
            return db.execute("""
                WITH people(project_id, user_id) AS (
                    SELECT id, owner_user_id FROM shared_projects
                    UNION SELECT project_id, user_id FROM project_members
                    UNION SELECT project_id, invited_user_id FROM project_invitations
                          WHERE status='pending'
                )
                SELECT 1 FROM people a JOIN people b ON a.project_id=b.project_id
                WHERE a.user_id=? AND b.user_id=? LIMIT 1
            """, (user_id, other_id)).fetchone() is not None

    def change_member(self, project_id: str, owner_id: str, user_id: str, role: str | None) -> None:
        with self._connect() as db:
            if not db.execute(
                "SELECT 1 FROM shared_projects WHERE id=? AND owner_user_id=?",
                (project_id, owner_id),
            ).fetchone():
                raise SinPermiso("Solo el propietario puede administrar el acceso.")
            if role is None:
                if not db.execute(
                    "DELETE FROM project_members WHERE project_id=? AND user_id=?",
                    (project_id, user_id),
                ).rowcount:
                    raise NoEncontrado("La persona ya no tiene acceso.")
            elif not db.execute(
                "UPDATE project_members SET role=? WHERE project_id=? AND user_id=?",
                (role, project_id, user_id),
            ).rowcount:
                raise NoEncontrado("La persona no tiene acceso al proyecto.")

    def cancel_invitation(self, invitation_id: str, owner_id: str) -> None:
        with self._connect() as db:
            if not db.execute("""
                UPDATE project_invitations SET status='cancelled', responded_at=?
                WHERE id=? AND status='pending' AND project_id IN
                    (SELECT id FROM shared_projects WHERE owner_user_id=?)
            """, (int(time.time()), invitation_id, owner_id)).rowcount:
                raise NoEncontrado("La invitación ya no está disponible.")

    def leave(self, project_id: str, user_id: str) -> None:
        with self._connect() as db:
            if not db.execute(
                "DELETE FROM project_members WHERE project_id=? AND user_id=?",
                (project_id, user_id),
            ).rowcount:
                raise NoEncontrado("No formas parte de este proyecto.")

    def advances(self, project_id: str) -> list[dict]:
        with self._connect() as db:
            return [dict(row) for row in db.execute(
                "SELECT * FROM project_advances WHERE project_id=? AND status!='superseded' "
                "ORDER BY created_at, id", (project_id,)
            )]

    def update_advance(self, project_id: str, advance_id: str, content: str, kind: str,
                       version: int) -> dict:
        """Corrige un avance vigente si nadie lo cambio desde la version indicada."""
        now = int(time.time())
        with self._connect() as db:
            updated = db.execute(
                "UPDATE project_advances SET content=?, kind=?, version=version+1, updated_at=? "
                "WHERE id=? AND project_id=? AND status!='superseded' AND version=?",
                (content, kind, now, advance_id, project_id, version),
            ).rowcount
            row = db.execute(
                "SELECT * FROM project_advances WHERE id=? AND project_id=? "
                "AND status!='superseded'", (advance_id, project_id),
            ).fetchone()
        if row is None:
            raise NoEncontrado("El avance ya no existe.")
        if not updated:
            raise Conflicto("Otra persona corrigió este avance mientras lo editabas. "
                                     "Revisa la versión actual antes de guardar.")
        return dict(row)

    def retire_advance(self, project_id: str, advance_id: str) -> None:
        """Retira un avance del contexto comun sin borrar su registro."""
        with self._connect() as db:
            if not db.execute(
                "UPDATE project_advances SET status='superseded', updated_at=? "
                "WHERE id=? AND project_id=? AND status!='superseded'",
                (int(time.time()), advance_id, project_id),
            ).rowcount:
                raise NoEncontrado("El avance ya no existe.")

    def add_advance(self, project_id: str, user_id: str, author_name: str,
                    content: str, kind: str) -> dict:
        now = int(time.time())
        advance_id = uuid.uuid4().hex
        with self._connect() as db:
            db.execute(
                "INSERT INTO project_advances VALUES (?, ?, ?, ?, 'confirmed', ?, ?, 1, ?, ?)",
                (advance_id, project_id, content, kind, user_id, author_name, now, now),
            )
            row = db.execute("SELECT * FROM project_advances WHERE id=?", (advance_id,)).fetchone()
        return dict(row)
