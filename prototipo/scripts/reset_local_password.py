"""Restablece una contraseña de Hilo en la base local de esta computadora."""

from __future__ import annotations

import argparse
import getpass
import secrets
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from ruta_dia_agents.auth import AuthStore
from ruta_dia_agents.config import Settings


def reset_password(database: Path, username: str, password: str) -> Path:
    if not database.is_file():
        raise FileNotFoundError(f"No existe la base de cuentas: {database}")
    username = username.strip().lower()
    if not 10 <= len(password) <= 128:
        raise ValueError("La nueva contraseña debe tener entre 10 y 128 caracteres.")

    with sqlite3.connect(database, timeout=5) as connection:
        row = connection.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
        if row is None:
            raise ValueError(f"No existe el usuario {username!r} en {database}")

        backup_dir = database.parent / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        backup_path = backup_dir / f"auth-before-password-reset-{stamp}.sqlite3"
        with sqlite3.connect(backup_path) as backup:
            connection.backup(backup)

        salt = secrets.token_bytes(16)
        digest = AuthStore._password(password, salt)
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            "UPDATE users SET salt=?, password_hash=? WHERE id=?", (salt, digest, row[0])
        )
        connection.execute("DELETE FROM sessions WHERE user_id=?", (row[0],))
        connection.commit()
    return backup_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("username", help="Usuario de Hilo que recuperará el acceso")
    username = parser.parse_args().username.strip().lower()
    if not username:
        parser.error("Indica el usuario de Hilo.")

    database = Settings.from_env().memory_path.parent / "auth.sqlite3"
    print(f"Base de cuentas: {database}")
    password = getpass.getpass("Nueva contraseña (10 a 128 caracteres): ")
    confirmation = getpass.getpass("Repítela: ")
    if password != confirmation:
        parser.error("Las contraseñas no coinciden.")
    try:
        backup = reset_password(database, username, password)
    except (OSError, sqlite3.Error, ValueError) as exc:
        parser.error(str(exc))
    print(f"Contraseña restablecida para {username}. Inicia sesión de nuevo en Hilo.")
    print(f"Copia de seguridad de las cuentas: {backup}")


if __name__ == "__main__":
    main()
