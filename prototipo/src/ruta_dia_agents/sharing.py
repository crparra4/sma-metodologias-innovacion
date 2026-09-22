from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path

from fastapi import HTTPException


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
            """)

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
                raise HTTPException(403, "Tu permiso no permite editar este árbol.")
            row = db.execute(
                "SELECT version FROM project_problem_trees WHERE project_id=?",
                (project_id,),
            ).fetchone()
            current_version = row["version"] if row else 0
            if current_version != version:
                raise HTTPException(
                    409, "Otra persona modificó el árbol. Recarga la versión actual."
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
                raise HTTPException(403, "Solo el propietario puede compartir este proyecto.")
            target = db.execute(
                "SELECT id, username, display_name FROM users WHERE username=?",
                (username.strip().lower(),),
            ).fetchone()
            if not target:
                raise HTTPException(404, "No existe una cuenta con ese usuario.")
            if target["id"] == owner_id:
                raise HTTPException(409, "Ya eres la persona propietaria del proyecto.")
            if db.execute(
                "SELECT 1 FROM project_members WHERE project_id=? AND user_id=?",
                (project_id, target["id"]),
            ).fetchone():
                raise HTTPException(409, "Esa persona ya tiene acceso al proyecto.")
            invitation_id = uuid.uuid4().hex
            try:
                db.execute(
                    "INSERT INTO project_invitations VALUES (?, ?, ?, ?, ?, 'pending', ?, NULL)",
                    (invitation_id, project_id, owner_id, target["id"], role, int(time.time())),
                )
            except sqlite3.IntegrityError as exc:
                raise HTTPException(409, "Esa persona ya tiene una invitación pendiente.") from exc
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
                raise HTTPException(404, "La invitación ya no está disponible.")
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
                SELECT p.owner_user_id, u.username, u.display_name
                FROM shared_projects p JOIN users u ON u.id=p.owner_user_id
                LEFT JOIN project_members m ON m.project_id=p.id AND m.user_id=?
                WHERE p.id=? AND (p.owner_user_id=? OR m.user_id=?)
            """, (requester_id, project_id, requester_id, requester_id)).fetchone()
            if not project:
                raise HTTPException(403, "No tienes acceso a este proyecto.")
            members = db.execute("""
                SELECT m.user_id, m.role, u.username, u.display_name
                FROM project_members m JOIN users u ON u.id=m.user_id
                WHERE m.project_id=? ORDER BY m.joined_at
            """, (project_id,)).fetchall()
            pending = db.execute("""
                SELECT i.id, i.role, u.username, u.display_name
                FROM project_invitations i JOIN users u ON u.id=i.invited_user_id
                WHERE i.project_id=? AND i.status='pending'
                ORDER BY i.created_at, i.rowid
            """, (project_id,)).fetchall() if project["owner_user_id"] == requester_id else []
        return [{"user_id": project["owner_user_id"], "username": project["username"],
                 "display_name": project["display_name"], "role": "owner"},
                *[dict(row) for row in members],
                *[{**dict(row), "status": "pending"} for row in pending]]

    def change_member(self, project_id: str, owner_id: str, user_id: str, role: str | None) -> None:
        with self._connect() as db:
            if not db.execute(
                "SELECT 1 FROM shared_projects WHERE id=? AND owner_user_id=?",
                (project_id, owner_id),
            ).fetchone():
                raise HTTPException(403, "Solo el propietario puede administrar el acceso.")
            if role is None:
                if not db.execute(
                    "DELETE FROM project_members WHERE project_id=? AND user_id=?",
                    (project_id, user_id),
                ).rowcount:
                    raise HTTPException(404, "La persona ya no tiene acceso.")
            elif not db.execute(
                "UPDATE project_members SET role=? WHERE project_id=? AND user_id=?",
                (role, project_id, user_id),
            ).rowcount:
                raise HTTPException(404, "La persona no tiene acceso al proyecto.")

    def cancel_invitation(self, invitation_id: str, owner_id: str) -> None:
        with self._connect() as db:
            if not db.execute("""
                UPDATE project_invitations SET status='cancelled', responded_at=?
                WHERE id=? AND status='pending' AND project_id IN
                    (SELECT id FROM shared_projects WHERE owner_user_id=?)
            """, (int(time.time()), invitation_id, owner_id)).rowcount:
                raise HTTPException(404, "La invitación ya no está disponible.")

    def leave(self, project_id: str, user_id: str) -> None:
        with self._connect() as db:
            if not db.execute(
                "DELETE FROM project_members WHERE project_id=? AND user_id=?",
                (project_id, user_id),
            ).rowcount:
                raise HTTPException(404, "No formas parte de este proyecto.")

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
            raise HTTPException(404, "El avance ya no existe.")
        if not updated:
            raise HTTPException(409, "Otra persona corrigió este avance mientras lo editabas. "
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
                raise HTTPException(404, "El avance ya no existe.")

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
