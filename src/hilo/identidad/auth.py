from __future__ import annotations

import hashlib
import hmac
import math
import secrets
import sqlite3
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass
from pathlib import Path

from ..compartido.errores import Conflicto, NoEncontrado

SESSION_SECONDS = 12 * 60 * 60
COOKIE_NAME = "hilo_session"
# Cada hash reserva decenas de MB: sin este tope, muchos accesos a la vez agotan la memoria.
_HASHING = threading.BoundedSemaphore(2)


class AttemptLimiter:
    """Ventana deslizante en memoria: `limit` intentos por clave cada `window` segundos."""

    def __init__(self, limit: int, window: float = 60.0, clock=time.monotonic):
        self.limit, self.window, self.clock = limit, window, clock
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def attempt(self, key: str) -> int:
        """Anota el intento y devuelve 0; si ya no cabe, los segundos que faltan."""
        now = self.clock()
        expired = now - self.window
        with self._lock:
            for name in [name for name, hits in self._hits.items() if hits[-1] <= expired]:
                del self._hits[name]
            hits = self._hits.get(key)
            if hits is None:
                self._hits[key] = deque([now])
                return 0
            while hits[0] <= expired:
                hits.popleft()
            if len(hits) >= self.limit:
                return max(1, math.ceil(hits[0] + self.window - now))
            hits.append(now)
            return 0

    def forget(self, key: str) -> None:
        with self._lock:
            self._hits.pop(key, None)


# La foto se reduce en el navegador a 320 px; este tope deja margen de sobra.
AVATAR_MAX_BYTES = 512 * 1024
_AVATAR_TYPES = ((b"\xff\xd8\xff", "image/jpeg"), (b"\x89PNG\r\n\x1a\n", "image/png"))


def avatar_type(data: bytes) -> str | None:
    """Tipo de imagen según sus primeros bytes; no se confía en lo que diga el navegador."""
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return next((kind for magic, kind in _AVATAR_TYPES if data.startswith(magic)), None)


@dataclass(frozen=True)
class User:
    id: str
    username: str
    display_name: str
    legacy: bool
    # Versión de la foto de perfil; 0 si no tiene. Sirve para que el navegador no muestre
    # una foto vieja guardada en caché.
    avatar: int = 0

    def public(self) -> dict[str, str | int]:
        return {"id": self.id, "username": self.username, "display_name": self.display_name,
                "avatar": self.avatar}


# Columnas que se agregaron después: una base creada antes no las tiene.
_PROFILE_COLUMNS = {
    "first_name": "TEXT NOT NULL DEFAULT ''", "last_name": "TEXT NOT NULL DEFAULT ''",
    "phone": "TEXT NOT NULL DEFAULT ''", "email": "TEXT NOT NULL DEFAULT ''",
    "avatar": "BLOB", "avatar_type": "TEXT", "avatar_version": "INTEGER NOT NULL DEFAULT 0",
}
_AVATAR = "CASE WHEN u.avatar IS NULL THEN 0 ELSE u.avatar_version END"


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
            present = {row[1] for row in db.execute("PRAGMA table_info(users)")}
            for column, kind in _PROFILE_COLUMNS.items():
                if column not in present:
                    db.execute(f"ALTER TABLE users ADD COLUMN {column} {kind}")

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=5)
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=5000")
        return db

    @staticmethod
    def _password(password: str, salt: bytes) -> bytes:
        with _HASHING:
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
                    "INSERT INTO users (id, username, display_name, salt, password_hash, legacy, "
                    "created_at, first_name) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (user_id, username, display_name, salt, digest, int(legacy), int(time.time()),
                     display_name),
                )
                db.commit()
            except sqlite3.IntegrityError as exc:
                raise Conflicto("Ese usuario ya existe. Elige otro.") from exc
        return User(user_id, username, display_name, legacy)

    def authenticate(self, username: str, password: str) -> User | None:
        with self._connect() as db:
            row = db.execute(
                f"SELECT u.id, u.username, u.display_name, u.salt, u.password_hash, u.legacy, "
                f"{_AVATAR} FROM users u WHERE u.username=?", (username.strip().lower(),),
            ).fetchone()
        # Mantiene un coste parecido para usuarios inexistentes.
        salt = row[3] if row else b"\x00" * 16
        digest = self._password(password, salt)
        if row and hmac.compare_digest(digest, row[4]):
            return User(row[0], row[1], row[2], bool(row[5]), row[6])
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
                f"SELECT u.id, u.username, u.display_name, u.legacy, {_AVATAR} FROM sessions s "
                "JOIN users u ON u.id=s.user_id WHERE s.token_hash=? AND s.expires_at>?",
                (digest, int(time.time())),
            ).fetchone()
        return User(row[0], row[1], row[2], bool(row[3]), row[4]) if row else None

    def logout(self, token: str | None) -> None:
        if not token:
            return
        try:
            digest = self._token_hash(token)
        except UnicodeEncodeError:
            return
        with self._connect() as db:
            db.execute("DELETE FROM sessions WHERE token_hash=?", (digest,))

    def created_at(self, user: User) -> int:
        with self._connect() as db:
            row = db.execute("SELECT created_at FROM users WHERE id=?", (user.id,)).fetchone()
        return int(row[0]) if row else 0

    def change_password(self, user: User, current: str, new: str, keep_token: str | None) -> bool:
        """Cambia la contraseña si `current` es la vigente. Cierra las demás sesiones de la
        cuenta y conserva la de quien hizo el cambio."""
        if not self.authenticate(user.username, current):
            return False
        salt = secrets.token_bytes(16)
        digest = self._password(new, salt)
        try:
            keep = self._token_hash(keep_token) if keep_token else b""
        except UnicodeEncodeError:
            keep = b""
        with self._connect() as db:
            db.execute("UPDATE users SET salt=?, password_hash=? WHERE id=?",
                       (salt, digest, user.id))
            db.execute("DELETE FROM sessions WHERE user_id=? AND token_hash<>?", (user.id, keep))
        return True

    def profile(self, user: User) -> dict[str, str]:
        """Nombre, apellido, teléfono y correo. Una cuenta creada antes de separar los campos
        tiene todo en `display_name`: se muestra como nombre hasta que la persona lo divida."""
        with self._connect() as db:
            row = db.execute(
                "SELECT first_name, last_name, phone, email, display_name FROM users WHERE id=?",
                (user.id,),
            ).fetchone()
        if not row:
            return {"first_name": "", "last_name": "", "phone": "", "email": ""}
        first = row[0] if row[0] or row[1] else row[4]
        return {"first_name": first, "last_name": row[1], "phone": row[2], "email": row[3]}

    def update_profile(self, user: User, first_name: str, last_name: str, phone: str,
                       email: str) -> User:
        """Guarda los campos y recompone el nombre visible, que es el que ven los demás."""
        display_name = f"{first_name} {last_name}".strip()
        with self._connect() as db:
            db.execute(
                "UPDATE users SET first_name=?, last_name=?, phone=?, email=?, display_name=? "
                "WHERE id=?", (first_name, last_name, phone, email, display_name, user.id),
            )
        return User(user.id, user.username, display_name, user.legacy, user.avatar)

    def set_avatar(self, user: User, data: bytes, kind: str) -> User:
        with self._connect() as db:
            db.execute("UPDATE users SET avatar=?, avatar_type=?, avatar_version=avatar_version+1 "
                       "WHERE id=?", (data, kind, user.id))
            version = db.execute("SELECT avatar_version FROM users WHERE id=?",
                                 (user.id,)).fetchone()[0]
        return User(user.id, user.username, user.display_name, user.legacy, version)

    def clear_avatar(self, user: User) -> User:
        # La versión no vuelve a 0: si la persona sube otra foto, la URL cambia igual.
        with self._connect() as db:
            db.execute("UPDATE users SET avatar=NULL, avatar_type=NULL WHERE id=?", (user.id,))
        return User(user.id, user.username, user.display_name, user.legacy, 0)

    def avatar_image(self, user_id: str) -> tuple[bytes, str] | None:
        with self._connect() as db:
            row = db.execute(
                "SELECT avatar, avatar_type FROM users WHERE id=? AND avatar IS NOT NULL",
                (user_id,),
            ).fetchone()
        return (bytes(row[0]), row[1]) if row else None

    def user(self, user_id: str) -> User | None:
        with self._connect() as db:
            row = db.execute(
                f"SELECT u.id, u.username, u.display_name, u.legacy, {_AVATAR} FROM users u "
                "WHERE u.id=?", (user_id,)
            ).fetchone()
        return User(row[0], row[1], row[2], bool(row[3]), row[4]) if row else None

    def storage_path(self, user_id: str, legacy_path: Path) -> Path:
        user = self.user(user_id)
        if not user:
            raise NoEncontrado("La cuenta propietaria ya no existe.")
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
