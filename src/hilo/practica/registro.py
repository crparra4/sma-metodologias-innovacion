"""Registro de las prácticas de entrevista con el cliente simulado.

Las prácticas van aparte de los turnos, la ficha y los campos verificados del proyecto, porque lo
simulado nunca es evidencia. Comparten el archivo de la memoria del proyecto para que borrar el
proyecto borre sus prácticas (clave foránea con `ON DELETE CASCADE`), pero el esquema y las
consultas son de este contexto: la memoria de proyectos no sabe que existen.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from uuid import uuid4

ESQUEMA = """
CREATE TABLE IF NOT EXISTS practicas (
    id TEXT PRIMARY KEY,
    notebook_id TEXT NOT NULL,
    persona TEXT NOT NULL,
    participant_id TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    FOREIGN KEY (notebook_id) REFERENCES notebooks(notebook_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS practica_turnos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    practica_id TEXT NOT NULL,
    rol TEXT NOT NULL CHECK (rol IN ('entrevistador', 'cliente')),
    texto TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (practica_id) REFERENCES practicas(id) ON DELETE CASCADE
);
"""


class RegistroPracticas:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection
        connection.executescript(ESQUEMA)

    def crear(self, notebook_id: str, persona: str, participant_id: str = "") -> dict:
        practica = {"id": str(uuid4()), "notebook_id": notebook_id, "persona": persona,
                    "created_at": datetime.now(UTC).isoformat(), "turnos": []}
        with self.connection:
            self.connection.execute(
                "INSERT INTO practicas (id, notebook_id, persona, participant_id, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (practica["id"], notebook_id, persona, participant_id, practica["created_at"]),
            )
        return practica

    def obtener(self, notebook_id: str, practica_id: str, participant_id: str = "") -> dict | None:
        """Una práctica de quien la creó; la de otra persona del proyecto no se ve."""
        row = self.connection.execute(
            "SELECT * FROM practicas WHERE id = ? AND notebook_id = ? AND participant_id = ?",
            (practica_id, notebook_id, participant_id),
        ).fetchone()
        if row is None:
            return None
        turnos = self.connection.execute(
            "SELECT rol, texto, created_at FROM practica_turnos WHERE practica_id = ? ORDER BY id",
            (practica_id,),
        ).fetchall()
        return {"id": row["id"], "notebook_id": row["notebook_id"], "persona": row["persona"],
                "created_at": row["created_at"], "turnos": [dict(t) for t in turnos]}

    def listar(self, notebook_id: str, participant_id: str = "") -> list[dict]:
        """Las prácticas de esta persona en el proyecto, la más reciente primero."""
        rows = self.connection.execute(
            "SELECT id, persona, created_at FROM practicas "
            "WHERE notebook_id = ? AND participant_id = ? ORDER BY created_at DESC",
            (notebook_id, participant_id),
        ).fetchall()
        return [dict(row) for row in rows]

    def agregar_turnos(self, practica_id: str, pregunta: str, respuesta: str) -> None:
        now = datetime.now(UTC).isoformat()
        with self.connection:
            self.connection.executemany(
                "INSERT INTO practica_turnos (practica_id, rol, texto, created_at) "
                "VALUES (?, ?, ?, ?)",
                [(practica_id, "entrevistador", pregunta, now),
                 (practica_id, "cliente", respuesta, now)],
            )
