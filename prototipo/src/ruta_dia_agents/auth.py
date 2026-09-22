from __future__ import annotations

import hashlib
import hmac
import secrets
import sqlite3
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from fastapi import HTTPException

SESSION_SECONDS = 12 * 60 * 60
COOKIE_NAME = "hilo_session"


@dataclass(frozen=True)
class User:
    id: str
    username: str
    display_name: str
    legacy: bool

    def public(self) -> dict[str, str]:
        return {"id": self.id, "username": self.username, "display_name": self.display_name}


class AuthStore:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY, username TEXT NOT NULL UNIQUE,
                    display_name TEXT NOT NULL, salt BLOB NOT NULL,
                    password_hash BLOB NOT NULL, legacy INTEGER NOT NULL,
                    created_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    token_hash BLOB PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id),
                    expires_at INTEGER NOT NULL
                );
                CREATE INDEX IF NOT EXISTS sessions_user ON sessions(user_id);
            """)

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=5)
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=5000")
        return db

    @staticmethod
    def _password(password: str, salt: bytes) -> bytes:
        return hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**15, r=8, p=3,
                              dklen=32, maxmem=64 * 1024 * 1024)

    def register(self, username: str, display_name: str, password: str) -> User:
        username = username.strip().lower()
        display_name = display_name.strip()
        salt = secrets.token_bytes(16)
        digest = self._password(password, salt)
        user_id = uuid.uuid4().hex
        with self._connect() as db:
            try:
                db.execute("BEGIN IMMEDIATE")
                legacy = not db.execute("SELECT 1 FROM users LIMIT 1").fetchone()
                db.execute(
                    "INSERT INTO users VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (user_id, username, display_name, salt, digest, int(legacy), int(time.time())),
                )
                db.commit()
            except sqlite3.IntegrityError as exc:
                raise HTTPException(409, "Ese usuario ya existe. Elige otro.") from exc
        return User(user_id, username, display_name, legacy)

    def authenticate(self, username: str, password: str) -> User | None:
        with self._connect() as db:
            row = db.execute(
                "SELECT id, username, display_name, salt, password_hash, legacy "
                "FROM users WHERE username=?", (username.strip().lower(),),
            ).fetchone()
        # Mantiene un coste parecido para usuarios inexistentes.
        salt = row[3] if row else b"\x00" * 16
        digest = self._password(password, salt)
        if row and hmac.compare_digest(digest, row[4]):
            return User(row[0], row[1], row[2], bool(row[5]))
        return None

    @staticmethod
    def _token_hash(token: str) -> bytes:
        return hashlib.sha256(token.encode("ascii")).digest()

    def create_session(self, user: User) -> str:
        token = secrets.token_urlsafe(32)
        with self._connect() as db:
            db.execute("DELETE FROM sessions WHERE expires_at <= ?", (int(time.time()),))
            db.execute("INSERT INTO sessions VALUES (?, ?, ?)",
                       (self._token_hash(token), user.id, int(time.time()) + SESSION_SECONDS))
        return token

    def current_user(self, token: str | None) -> User | None:
        if not token:
            return None
        try:
            digest = self._token_hash(token)
        except UnicodeEncodeError:
            return None
        with self._connect() as db:
            row = db.execute(
                "SELECT u.id, u.username, u.display_name, u.legacy FROM sessions s "
                "JOIN users u ON u.id=s.user_id WHERE s.token_hash=? AND s.expires_at>?",
                (digest, int(time.time())),
            ).fetchone()
        return User(row[0], row[1], row[2], bool(row[3])) if row else None

    def logout(self, token: str | None) -> None:
        if not token:
            return
        try:
            digest = self._token_hash(token)
        except UnicodeEncodeError:
            return
        with self._connect() as db:
            db.execute("DELETE FROM sessions WHERE token_hash=?", (digest,))

    def rename(self, user: User, display_name: str) -> User:
        display_name = display_name.strip()
        with self._connect() as db:
            db.execute("UPDATE users SET display_name=? WHERE id=?", (display_name, user.id))
        return User(user.id, user.username, display_name, user.legacy)

    def user(self, user_id: str) -> User | None:
        with self._connect() as db:
            row = db.execute(
                "SELECT id, username, display_name, legacy FROM users WHERE id=?", (user_id,)
            ).fetchone()
        return User(row[0], row[1], row[2], bool(row[3])) if row else None

    def storage_path(self, user_id: str, legacy_path: Path) -> Path:
        user = self.user(user_id)
        if not user:
            raise HTTPException(404, "La cuenta propietaria ya no existe.")
        return self.memory_path(user, legacy_path)

    def memory_path(self, user: User, legacy_path: Path) -> Path:
        if user.legacy:
            return legacy_path
        path = legacy_path.parent / "users" / user.id / legacy_path.name
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def checkpoint_path(self, user: User, legacy_path: Path) -> Path:
        if user.legacy:
            return legacy_path
        path = legacy_path.parent / "users" / user.id / legacy_path.name
        path.parent.mkdir(parents=True, exist_ok=True)
        return path
