from __future__ import annotations

import asyncio
import hmac
import json
import logging
import os
import re
import sqlite3
import time
from contextlib import closing
from contextvars import ContextVar
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.checkpoint.sqlite import SqliteSaver
from openai import OpenAI
from pydantic import BaseModel, Field, field_validator
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .audit import JsonlVerificationRecorder
from .auth import (
    AVATAR_MAX_BYTES,
    COOKIE_NAME,
    SESSION_SECONDS,
    AttemptLimiter,
    AuthStore,
    User,
    avatar_type,
)
from .cliente_simulado import AVISO as AVISO_PRACTICA
from .cliente_simulado import responder as responder_cliente
from .cliente_simulado import retroalimentacion, revisar_pregunta
from .config import PROJECT_ROOT, Settings
from .contracts import NotebookColor, ProjectContext, ProjectState, TurnResult
from .empathy_map import EmpathyMapUpdate
from .empathy_map import context_lines as empathy_context
from .journey import JourneyUpdate
from .journey import context_lines as journey_context
from .journey_extract import NotesRequest, extraction_model, extraction_prompt, grounded_quotes
from .knowledge import KnowledgeCatalog
from .langgraph_workflow import LangGraphRutaDia
from .memory import EditConflict, NotebookMemory
from .notes import NoteRequest
from .pestel import PestelUpdate
from .pestel import context_lines as pestel_context
from .problem_tree import ProblemTreeUpdate
from .respaldo_claude import ModeloNoDisponible, Respaldo
from .sensitive import sensitive_topic
from .sharing import SharingStore
from .tasks import TaskRequest
from .tree_diagnosis import (
    TREE_TOOL_ID,
    grounded,
    review_prompt,
    rule_findings,
    summary_text,
)
from .turnos import ModelQueue, ProjectLocks
from .variantes import VARIANTES
from .why_analysis import TOOL_ID as WHY_TOOL_ID
from .why_analysis import WhyClose, WhyStart, WhyUpdate, context_text

logger = logging.getLogger(__name__)

# El cuerpo legítimo más grande es un tablero completo y no llega a esta cifra.
MAX_BODY_BYTES = 1024 * 1024
ACCESS_ATTEMPTS_PER_MINUTE = 20
LOGIN_ATTEMPTS_PER_MINUTE = 5
TOO_MANY_ATTEMPTS = "Demasiados intentos. Espera un minuto y vuelve a intentarlo."
# Direcciones con las que se entra desde este mismo computador. Cualquier otra llega por un
# túnel (scripts/abrir_tunel.sh) y para crear cuenta necesita el código de invitación.
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "testserver"}
REGISTRATION_CLOSED = "Desde internet solo se puede crear una cuenta con un código de invitación."
WRONG_INVITE_CODE = "El código de invitación no es correcto."
BODY_TOO_LARGE = "La solicitud es demasiado grande."
# Espera máxima en la fila del modelo. El chat avisa su lugar mientras tanto; las lecturas de
# notas y el diagnóstico del árbol responden sin esperar tanto porque la petición queda abierta
# (el túnel de Cloudflare corta a los 100 s sin respuesta).
MODEL_WAIT_CHAT = 300.0
MODEL_WAIT_SHORT = 45.0
QUEUE_HEARTBEAT = 20.0


def restrict_data_dir(path: Path) -> None:
    """En Linux la carpeta de datos quedaba legible para otros usuarios del equipo (775 y 644):
    cuentas, hashes, cuadernos y conversaciones. Se deja solo para la cuenta que corre Hilo.
    En Windows, `%LOCALAPPDATA%` ya es privada por permisos de NTFS."""
    if os.name != "posix":
        return
    try:
        path.chmod(0o700)
        for item in path.rglob("*"):
            item.chmod(0o700 if item.is_dir() else 0o600)
    except OSError as exc:  # una carpeta en un disco que no admite permisos (NTFS, FAT)
        logging.getLogger(__name__).warning("No se pudieron restringir los permisos: %s", exc)


class BodyLimitMiddleware:
    """Rechaza con 413 el cuerpo que pasa del tope, antes de leerlo completo o validarlo."""

    def __init__(self, app, max_bytes: int = MAX_BODY_BYTES):
        self.app, self.max_bytes = app, max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        declared = dict(scope["headers"]).get(b"content-length", b"")
        if declared.isdigit() and int(declared) > self.max_bytes:
            response = JSONResponse({"detail": BODY_TOO_LARGE}, 413, {"Connection": "close"})
            await response(scope, receive, send)
            return
        received = 0

        # Sin Content-Length (envío por trozos) solo se sabe el tamaño al ir leyendo.
        async def limited():
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    raise HTTPException(413, BODY_TOO_LARGE, {"Connection": "close"})
            return message

        await self.app(scope, limited, send)


class NotebookRequest(BaseModel):
    notebook_id: str = Field(min_length=1, max_length=120, pattern=r"\S")
    stage: int = Field(default=1, ge=1, le=10)

    @field_validator("notebook_id")
    @classmethod
    def valid_notebook_id(cls, value: str) -> str:
        value = value.strip()
        if any(character in "/\\" or ord(character) < 32 for character in value):
            raise ValueError("Usa un nombre de cuaderno sin barras ni saltos de línea.")
        return value


class ChatRequest(NotebookRequest):
    message: str = Field(min_length=1, max_length=6000, pattern=r"\S")
    project_id: str | None = Field(default=None, min_length=32, max_length=32)


class CreateNotebookRequest(NotebookRequest):
    context: ProjectContext = Field(default_factory=ProjectContext)
    color: NotebookColor = NotebookColor.BLUE

    @field_validator("context")
    @classmethod
    def initial_question(cls, value: ProjectContext) -> ProjectContext:
        if not value.question:
            raise ValueError("Describe el reto o pregunta de negocio para crear el proyecto.")
        return value


class PracticaRequest(BaseModel):
    persona: str = Field(min_length=10, max_length=600)


class PracticaMensaje(BaseModel):
    texto: str = Field(min_length=2, max_length=600)


class ProfileRequest(BaseModel):
    context: ProjectContext
    color: NotebookColor


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=40, pattern=r"^[A-Za-z0-9_.-]+$")
    display_name: str = Field(min_length=1, max_length=60)
    password: str = Field(min_length=10, max_length=128)
    confirm_password: str
    invite_code: str = Field(default="", max_length=64)


class LoginRequest(BaseModel):
    username: str = Field(max_length=40)
    password: str = Field(max_length=128)


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(max_length=128)
    new_password: str = Field(min_length=10, max_length=128)
    confirm_password: str = Field(max_length=128)


class AccountProfileRequest(BaseModel):
    first_name: str = Field(max_length=30)
    last_name: str = Field(default="", max_length=30)
    phone: str = Field(default="", max_length=25)
    email: str = Field(default="", max_length=120)


def profile_fields(body: AccountProfileRequest) -> tuple[str, str, str, str]:
    """Limpia y revisa el perfil. Los mensajes van tal cual a la pantalla."""
    first, last, phone, email = (" ".join(value.split()) for value in
                                 (body.first_name, body.last_name, body.phone, body.email))
    if not first:
        raise HTTPException(400, "Escribe tu nombre.")
    digits = sum(char.isdigit() for char in phone)
    if phone and (not re.fullmatch(r"\+?[0-9 ()-]+", phone) or not 7 <= digits <= 15):
        raise HTTPException(
            400, "Escribe el teléfono con números (de 7 a 15); puede empezar con +.")
    if email and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s.]+", email):
        raise HTTPException(400, "Ese correo no parece válido: revisa la @ y el dominio.")
    return first, last, phone, email.lower()


class InvitationRequest(BaseModel):
    username: str = Field(min_length=3, max_length=40, pattern=r"^[A-Za-z0-9_.-]+$")
    role: Literal["viewer", "editor"]


class InvitationResponse(BaseModel):
    accept: bool


class MemberRoleRequest(BaseModel):
    role: Literal["viewer", "editor"]


class AdvanceRequest(BaseModel):
    content: str = Field(min_length=1, max_length=2000, pattern=r"\S")
    kind: Literal["decision", "finding", "hypothesis", "next_step", "other"] = "other"


class AdvanceUpdateRequest(AdvanceRequest):
    version: int = Field(ge=1)


def conflict_response(what: str, current: dict, pronoun: str = "lo") -> JSONResponse:
    return JSONResponse({
        "detail": f"Otra persona modificó {what} mientras {pronoun} editabas. "
                  "Se cargó la versión actual; revisa antes de guardar de nuevo.",
        "current": current,
    }, status_code=409)


def model_available(settings: Settings) -> bool:
    try:
        with OpenAI(
            base_url=settings.base_url,
            api_key=settings.api_key or "local",
            timeout=3,
            max_retries=0,
        ) as client:
            return any(model.id == settings.model for model in client.models.list().data)
    except Exception:
        return False


def _checkpointer(connection: sqlite3.Connection) -> SqliteSaver:
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA busy_timeout = 5000")
    return SqliteSaver(connection, serde=JsonPlusSerializer(allowed_msgpack_modules=[]))


AGENTES = {"orchestrator": "Orquestador", "methodologist": "Metodólogo",
           "verifier": "Verificador", "interpreter": "Intérprete"}
SONDA_SEGUNDOS = 15  # cada cuánto se vuelve a preguntar si el modelo local responde


def consumo_por_agente(calls: list[dict]) -> list[dict]:
    """Tokens que leyó y escribió cada agente en el turno (los pasos en código no gastan)."""
    total: dict[str, dict] = {}
    for call in calls:
        uso = call.get("usage") or {}
        fila = total.setdefault(call["role"], {
            "agente": AGENTES.get(call["role"], call["role"]),
            "llamadas": 0, "leidos": 0, "escritos": 0, "modelo": call.get("modelo", ""),
        })
        fila["llamadas"] += 1
        fila["leidos"] += uso.get("prompt_tokens") or 0
        fila["escritos"] += uso.get("completion_tokens") or 0
    return list(total.values())


def origen_del_turno(calls: list[dict]) -> str:
    """Quién respondió el turno: el modelo local, el respaldo con Claude o ninguno."""
    if not calls:
        return "ninguno"
    return "claude" if any(c.get("modelo", "").startswith("claude") for c in calls) else "local"


class SondaModelo:
    """Pregunta si el modelo local responde, como mucho una vez cada `SONDA_SEGUNDOS`."""

    def __init__(self, probe, settings: Settings):
        self.probe, self.settings = probe, settings
        self._hasta, self._valor = 0.0, False

    def local(self) -> bool:
        ahora = time.monotonic()
        if ahora >= self._hasta:
            self._valor = bool(self.probe(self.settings))
            self._hasta = ahora + SONDA_SEGUNDOS
        return self._valor


def _close_runtime(runtime) -> None:
    client = getattr(runtime, "client", None)
    if client is not None:
        client.close()


def create_app(
    settings: Settings | None = None,
    runtime_factory=None,
    model_probe=model_available,
    frontend_path: Path | None = None,
    require_auth: bool = True,
) -> FastAPI:
    settings = settings or Settings.from_env()
    if runtime_factory is None:
        if settings.variant not in VARIANTES:
            raise ValueError(
                f"RUTA_DIA_VARIANTE debe ser una de {', '.join(VARIANTES)}; "
                f"llegó «{settings.variant}»."
            )
        runtime_factory = VARIANTES[settings.variant]
    endpoint = urlparse(settings.base_url or "")
    if endpoint.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("La interfaz requiere RUTA_DIA_BASE_URL apuntando al modelo local.")
    # Respaldo: si el modelo local no responde, Claude atiende el turno (hasta el tope de gasto).
    respaldo = Respaldo(settings) if settings.respaldo_claude else None
    sonda = SondaModelo(model_probe, settings)

    def nuevo_runtime():
        """Runtime del turno: el modelo local si responde; si no, el respaldo con Claude."""
        if respaldo is None or sonda.local():
            return runtime_factory(settings)
        if not respaldo.disponible():
            raise ModeloNoDisponible("Se alcanzó el tope de gasto del respaldo con Claude.")
        return respaldo.runtime(runtime_factory, settings)

    catalog = KnowledgeCatalog(settings.route_path)
    catalog.require_valid()
    settings.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    restrict_data_dir(settings.memory_path.parent)
    app = FastAPI(title="Ruta DIA local", docs_url=None, redoc_url=None)
    # El túnel agrega su dominio (p. ej. `*.trycloudflare.com`); sin él solo se entra en local.
    public_hosts = [host.strip() for host in os.getenv("HILO_HOSTS_PUBLICOS", "").split(",")
                    if host.strip()]
    invite_code = os.getenv("HILO_CODIGO_INVITACION", "").strip()
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=[*LOCAL_HOSTS, *public_hosts])
    app.add_middleware(BodyLimitMiddleware)
    # Varias personas a la vez: el modelo atiende `parallel` respuestas juntas y pone las demás
    # en fila; cada proyecto genera una sola respuesta a la vez.
    model_queue = ModelQueue(settings.parallel)
    project_locks = ProjectLocks()
    app.state.jobs = set()
    auth = AuthStore(settings.memory_path.parent / "auth.sqlite3")
    sharing = SharingStore(settings.memory_path.parent / "auth.sqlite3")
    # Registro e inicio de sesión cuestan un hash cada uno: comparten el cupo por origen.
    access_attempts = AttemptLimiter(ACCESS_ATTEMPTS_PER_MINUTE)
    login_attempts = AttemptLimiter(LOGIN_ATTEMPTS_PER_MINUTE)
    current_account: ContextVar[User | None] = ContextVar("hilo_account", default=None)

    def memory_path() -> Path:
        user = current_account.get()
        return auth.memory_path(user, settings.memory_path) if user else settings.memory_path

    def checkpoint_path() -> Path:
        user = current_account.get()
        return (
            auth.checkpoint_path(user, settings.checkpoint_path)
            if user else settings.checkpoint_path
        )

    def audit_path() -> Path:
        user = current_account.get()
        if not user or user.legacy:
            return settings.audit_path
        path = settings.memory_path.parent / "users" / user.id / "verifications.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def current_user() -> User | None:
        return current_account.get()

    def sync_owned_projects(user: User) -> None:
        with NotebookMemory(auth.memory_path(user, settings.memory_path)) as memory:
            memory.claim_unattributed_notes(user.id, user.display_name)
            memory.claim_unattributed_turns(user.id)
            for notebook in memory.list_notebooks():
                sharing.ensure_project(user.id, notebook["notebook_id"])

    def project_access(reference: str) -> dict:
        user = current_user()
        if not user:
            return {"project_id": reference, "owner_user_id": "", "notebook_id": reference,
                    "owner_name": "Local", "owner_username": "local", "role": "owner"}
        sync_owned_projects(user)
        access = sharing.access(user.id, reference)
        if not access:
            raise HTTPException(404, "El proyecto no existe o ya no tienes acceso.")
        return access

    def project_memory_path(access: dict) -> Path:
        if not access["owner_user_id"]:
            return settings.memory_path
        return auth.storage_path(access["owner_user_id"], settings.memory_path)

    @staticmethod
    def require_edit(access: dict) -> None:
        if access["role"] not in {"owner", "editor"}:
            raise HTTPException(403, "Tu permiso permite ver, pero no modificar este proyecto.")

    @staticmethod
    def require_owner(access: dict) -> None:
        if access["role"] != "owner":
            raise HTTPException(403, "Solo el propietario puede realizar esta acción.")

    def shared_context(access: dict, memory: NotebookMemory) -> list[str]:
        if not access["owner_user_id"]:
            return []
        items = [
            f"Avance {item['kind']} ({item['author_name']}): {item['content']}"
            for item in sharing.advances(access["project_id"])
        ]
        items.extend(
            f"Post-it {note['category']} ({note['author_name'] or 'autor anterior'}): "
            f"{note['title']}: {note['text']}"
            for note in memory.list_notes(access["notebook_id"])
        )
        tree = sharing.problem_tree(access["project_id"])
        if tree["problem"]:
            summary = [f"Árbol de problemas (borrador del equipo, no verificado): "
                       f"problema central: {tree['problem']}"]
            for singular, plural, key in (
                ("Causa propuesta", "causas", "causes"),
                ("Efecto propuesto", "efectos", "effects"),
            ):
                nodes = tree[key]
                texts = {node["id"]: node["text"] for node in nodes}
                shown = nodes[:8]
                for node in shown:
                    source = (
                        f"; origen declarado: {node['source']}"
                        if node["source"] else "; sin fuente"
                    )
                    above = texts.get(node.get("parent") or "")
                    label = f"{singular} de fondo, detalla «{above}»" if above else singular
                    summary.append(f"{label}: {node['text']}{source}")
                if len(nodes) > len(shown):
                    summary.append(
                        f"El árbol tiene {len(nodes)} {plural} en total; "
                        f"aquí se resumen las primeras {len(shown)}"
                    )
            block = ""
            for part in summary:
                candidate = f"{block}. {part}" if block else part
                if len(candidate) > 3500:
                    break
                block = candidate
            items.append(block)
            # Solo si sigue vigente: un diagnóstico de otra versión del árbol confundiría al agente.
            diagnosis = sharing.tree_diagnosis(access["project_id"])
            if diagnosis and diagnosis["tree_version"] == tree["version"]:
                items.append(diagnosis["summary"])
        pestel = pestel_context(sharing.pestel(access["project_id"]))
        if pestel:
            items.append(". ".join(pestel)[:3500])
        empathy = empathy_context(sharing.empathy_map(access["project_id"]))
        if empathy:
            items.append(". ".join(empathy)[:3500])
        journey = journey_context(sharing.journey(access["project_id"]))
        if journey:
            items.append(". ".join(journey)[:3500])
        analysis = sharing.active_why_analysis(access["project_id"])
        if analysis:
            items.append(context_text(analysis))
        return items[-40:]

    @app.middleware("http")
    async def same_origin(request: Request, call_next):
        origin = request.headers.get("origin")
        if (
            request.method in {"POST", "DELETE", "PUT", "PATCH"}
            and ((origin and urlparse(origin).netloc != request.url.netloc)
                 or request.headers.get("sec-fetch-site") == "cross-site")
        ):
            return JSONResponse({"detail": "Origen de la solicitud no permitido."}, 403)
        user = auth.current_user(request.cookies.get(COOKIE_NAME)) if require_auth else None
        protected_api = (
            request.url.path.startswith("/api/")
            and request.url.path != "/api/status"
            and not request.url.path.startswith("/api/auth/")
        )
        if require_auth and protected_api and not user:
            return JSONResponse({"detail": "Inicia sesión para continuar."}, 401)
        request.state.user = user
        token = current_account.set(user)
        try:
            return await call_next(request)
        finally:
            current_account.reset(token)

    def throttle(limiter: AttemptLimiter, key: str) -> None:
        wait = limiter.attempt(key)
        if wait:
            raise HTTPException(429, TOO_MANY_ATTEMPTS, {"Retry-After": str(wait)})

    def origin_key(request: Request) -> str:
        return request.client.host if request.client else "local"

    def remote(request: Request) -> bool:
        return (request.url.hostname or "") not in LOCAL_HOSTS

    @app.get("/api/auth/registration")
    def registration(request: Request):
        # La pantalla de acceso pregunta si debe pedir el código antes de mostrar el formulario.
        outside = remote(request)
        return {"invite_code": outside and bool(invite_code), "closed": outside and not invite_code}

    @app.post("/api/auth/register", status_code=201)
    def register(body: RegisterRequest, request: Request):
        if body.password != body.confirm_password:
            raise HTTPException(400, "Las contraseñas no coinciden.")
        throttle(access_attempts, origin_key(request))
        if remote(request):
            if not invite_code:
                raise HTTPException(403, REGISTRATION_CLOSED)
            if not hmac.compare_digest(body.invite_code.strip().upper().encode(),
                                       invite_code.upper().encode()):
                raise HTTPException(403, WRONG_INVITE_CODE)
        user = auth.register(body.username, body.display_name, body.password)
        auth.logout(request.cookies.get(COOKIE_NAME))
        response = JSONResponse(user.public(), status_code=201)
        response.set_cookie(COOKIE_NAME, auth.create_session(user), httponly=True,
                            samesite="strict", secure=request.url.scheme == "https", path="/")
        return response

    @app.post("/api/auth/login")
    def login(body: LoginRequest, request: Request):
        username = body.username.strip().lower()
        throttle(access_attempts, origin_key(request))
        throttle(login_attempts, username)
        user = auth.authenticate(username, body.password)
        if not user:
            raise HTTPException(401, "Usuario o contraseña incorrectos.")
        login_attempts.forget(username)
        auth.logout(request.cookies.get(COOKIE_NAME))
        response = JSONResponse(user.public())
        response.set_cookie(COOKIE_NAME, auth.create_session(user), httponly=True,
                            samesite="strict", secure=request.url.scheme == "https", path="/")
        return response

    @app.get("/api/auth/me")
    def me(request: Request):
        if not request.state.user:
            raise HTTPException(401, "Inicia sesión para continuar.")
        return request.state.user.public()

    @app.get("/api/auth/account")
    def account_details(request: Request):
        user = request.state.user
        if not user:
            raise HTTPException(401, "Inicia sesión para continuar.")
        return {**user.public(), "created_at": auth.created_at(user),
                "session_hours": SESSION_SECONDS // 3600}

    @app.put("/api/auth/password")
    def change_password(body: PasswordChangeRequest, request: Request):
        user = request.state.user
        if not user:
            raise HTTPException(401, "Inicia sesión para continuar.")
        if body.new_password != body.confirm_password:
            raise HTTPException(400, "Las contraseñas nuevas no coinciden.")
        if body.new_password == body.current_password:
            raise HTTPException(400, "Elige una contraseña distinta a la actual.")
        # Comparte el cupo del inicio de sesión: si no, esta ruta serviría para adivinar
        # la contraseña de una sesión abierta sin límite.
        throttle(login_attempts, user.username)
        if not auth.change_password(user, body.current_password, body.new_password,
                                    request.cookies.get(COOKIE_NAME)):
            raise HTTPException(400, "La contraseña actual no es correcta.")
        login_attempts.forget(user.username)
        return {"ok": True}

    @app.get("/api/auth/profile")
    def account_profile(request: Request):
        if not request.state.user:
            raise HTTPException(401, "Inicia sesión para continuar.")
        return {**request.state.user.public(), **auth.profile(request.state.user)}

    @app.put("/api/auth/profile")
    def update_account_profile(body: AccountProfileRequest, request: Request):
        if not request.state.user:
            raise HTTPException(401, "Inicia sesión para continuar.")
        user = auth.update_profile(request.state.user, *profile_fields(body))
        return {**user.public(), **auth.profile(user)}

    @app.put("/api/auth/avatar")
    async def upload_avatar(request: Request):
        if not request.state.user:
            raise HTTPException(401, "Inicia sesión para continuar.")
        data = await request.body()
        if len(data) > AVATAR_MAX_BYTES:
            raise HTTPException(413, "La foto pesa demasiado. Prueba con otra.")
        kind = avatar_type(data)
        if not kind:
            raise HTTPException(400, "La foto debe ser JPG, PNG o WebP.")
        return auth.set_avatar(request.state.user, data, kind).public()

    @app.delete("/api/auth/avatar")
    def delete_avatar(request: Request):
        if not request.state.user:
            raise HTTPException(401, "Inicia sesión para continuar.")
        return auth.clear_avatar(request.state.user).public()

    @app.get("/api/users/{user_id}/avatar")
    def user_avatar(user_id: str, request: Request):
        # Solo la propia cuenta y quienes comparten un proyecto con ella ven la foto.
        user = request.state.user
        if not user or (user.id != user_id and not sharing.shares_project(user.id, user_id)):
            raise HTTPException(404, "No hay foto.")
        image = auth.avatar_image(user_id)
        if not image:
            raise HTTPException(404, "No hay foto.")
        # La URL lleva la versión (?v=), así que puede guardarse en caché sin quedar vieja.
        return Response(image[0], media_type=image[1], headers={
            "Cache-Control": "private, max-age=31536000, immutable",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'",
        })

    @app.post("/api/auth/logout")
    def logout(request: Request):
        auth.logout(request.cookies.get(COOKIE_NAME))
        response = JSONResponse({"ok": True})
        response.delete_cookie(COOKIE_NAME, path="/")
        return response

    @app.get("/api/status")
    def status(project: str | None = None):
        return {
            "app_id": "ruta-dia-local",
            "model": settings.model,
            "available": sonda.local() or bool(respaldo and respaldo.disponible()),
            "modelo": ("local" if sonda.local() else
                       "claude" if respaldo and respaldo.disponible() else None),
            # Ocupado es por proyecto: otra persona en otro proyecto no bloquea a nadie.
            "busy": project_locks.busy(project) if project else project_locks.any_busy(),
            "queue": model_queue.snapshot(),
            "runtime": "LangGraph",
            "variant": settings.variant,
            "memory": "SQLite local",
        }

    @app.get("/api/tasks")
    def list_tasks():
        user = current_user()
        if not user:
            with NotebookMemory(memory_path()) as memory:
                return memory.list_tasks()
        sync_owned_projects(user)
        results: list[dict] = []
        with NotebookMemory(auth.memory_path(user, settings.memory_path)) as personal:
            results.extend(task for task in personal.list_tasks() if not task["notebook_id"])
        for access in sharing.accessible(user.id):
            with NotebookMemory(project_memory_path(access)) as memory:
                for task in memory.list_tasks():
                    if task["notebook_id"] == access["notebook_id"]:
                        results.append({**task, "project_id": access["project_id"],
                                        "project_role": access["role"]})
        return sorted(results, key=lambda item: (item["completed"], item["due_at"], item["id"]))

    def persist_task(body, task_id=None):
        user = current_user()
        access = None
        target_path = memory_path()
        request_body = body
        if user and (body.project_id or body.notebook_id):
            access = project_access(body.project_id or body.notebook_id)
            require_edit(access)
            target_path = project_memory_path(access)
            request_body = body.model_copy(update={
                "notebook_id": access["notebook_id"], "project_id": None,
            })
        with NotebookMemory(target_path) as memory:
            if task_id and access:
                existing = next(
                    (item for item in memory.list_tasks() if item["id"] == task_id), None
                )
                if not existing or existing["notebook_id"] != access["notebook_id"]:
                    raise HTTPException(404, "La tarea no existe en este proyecto.")
            try:
                task = memory.save_task(
                    request_body, task_id,
                    author=(user.id, user.display_name) if user and task_id is None else None,
                )
            except EditConflict as conflict:
                current = conflict.current
                return conflict_response("esta entrada", pronoun="la", current=(
                    {**current, "project_id": access["project_id"], "project_role": access["role"]}
                    if access else current))
            except sqlite3.IntegrityError as exc:
                raise HTTPException(404, "El proyecto de la tarea ya no existe.") from exc
            if task is None:
                raise HTTPException(404, "La tarea no existe.")
            return ({**task, "project_id": access["project_id"], "project_role": access["role"]}
                    if access else task)

    @app.post("/api/tasks", status_code=201)
    def create_task(body: TaskRequest):
        return persist_task(body)

    @app.put("/api/tasks/{task_id}")
    def update_task(task_id: str, body: TaskRequest):
        user = current_user()
        if not user:
            return persist_task(body, task_id)
        if body.project_id or body.notebook_id:
            return persist_task(body, task_id)
        with NotebookMemory(auth.memory_path(user, settings.memory_path)) as memory:
            if any(
                task["id"] == task_id and not task["notebook_id"]
                for task in memory.list_tasks()
            ):
                return persist_task(body, task_id)
        for access in sharing.accessible(user.id):
            with NotebookMemory(project_memory_path(access)) as memory:
                task = next((item for item in memory.list_tasks() if item["id"] == task_id
                             and item["notebook_id"] == access["notebook_id"]), None)
            if task:
                update = {
                    "project_id": access["project_id"],
                    "notebook_id": access["notebook_id"],
                }
                return persist_task(body.model_copy(update=update), task_id)
        raise HTTPException(404, "La tarea no existe.")

    @app.delete("/api/tasks/{task_id}")
    def delete_task(task_id: str):
        user = current_user()
        candidates = ([None] if not user else [None, *sharing.accessible(user.id)])
        for access in candidates:
            path = (memory_path() if access is None else project_memory_path(access))
            with NotebookMemory(path) as memory:
                task = next((item for item in memory.list_tasks() if item["id"] == task_id), None)
                if not task or (
                    access is not None and task["notebook_id"] != access["notebook_id"]
                ):
                    continue
                if access is not None:
                    require_edit(access)
                elif user and task["notebook_id"]:
                    continue
                memory.delete_task(task_id)
                return {"deleted": task_id}
        raise HTTPException(404, "La tarea no existe.")

    @app.get("/api/catalog")
    def get_catalog():
        runtime = runtime_factory(settings)
        try:
            graph = LangGraphRutaDia(catalog, runtime).graph.get_graph()
            return {
                "stages": [stage.model_dump() for stage in catalog.route.stages],
                "tools": [tool.model_dump() for tool in catalog.route.tools],
                "graph": {
                    "nodes": list(graph.nodes),
                    "edges": [
                        {"source": edge.source, "target": edge.target,
                         "conditional": edge.conditional}
                        for edge in graph.edges
                    ],
                },
            }
        finally:
            _close_runtime(runtime)

    @app.get("/api/tools/{tool_id}")
    def tool_card(tool_id: str):
        try:
            tool = catalog.tool(tool_id)
            return {"id": tool_id, "name": tool.name, "content": catalog.tool_card(tool_id)}
        except KeyError as exc:
            raise HTTPException(404, "La ficha no existe.") from exc

    @app.get("/api/notebooks")
    def list_notebooks():
        user = current_user()
        if not user:
            with NotebookMemory(memory_path()) as memory:
                return memory.list_notebooks()
        sync_owned_projects(user)
        results = []
        for access in sharing.accessible(user.id):
            with NotebookMemory(project_memory_path(access)) as memory:
                notebook = next((item for item in memory.list_notebooks()
                                 if item["notebook_id"] == access["notebook_id"]), None)
                if not notebook:
                    continue
                private_turns = memory.history(access["notebook_id"], participant_id=user.id)
                preview = next(
                    (turn["content"] for turn in private_turns if turn["role"] == "user"),
                    None,
                )
                members = sharing.members(access["project_id"], user.id)
                # La carpeta muestra al propietario y a las personas invitadas cuando
                # hay alguien más. Las invitaciones pendientes solo las ve el dueño.
                collaborators = members if len(members) > 1 else []
                results.append({**notebook, **access, "turn_count": len(private_turns),
                                "preview": preview, "shared": access["role"] != "owner",
                                "collaborators": collaborators})
        return results

    @app.post("/api/notebooks", status_code=201)
    def create_notebook(body: CreateNotebookRequest):
        stage = catalog.stage(body.stage)
        with NotebookMemory(memory_path()) as memory:
            if body.notebook_id in {item["notebook_id"] for item in memory.list_notebooks()}:
                raise HTTPException(409, "Ya existe un proyecto con ese nombre. Elige otro nombre.")
            state = memory.create(ProjectState(
                notebook_id=body.notebook_id.strip(), stage=stage.id, phase=stage.phase,
                context=body.context, color=body.color,
            ))
            result = state.model_dump(mode="json")
        user = current_user()
        if user:
            result["project_id"] = sharing.ensure_project(user.id, state.notebook_id)
            result["access"] = {"role": "owner", "project_id": result["project_id"]}
        return result

    @app.put("/api/notebooks/{notebook_id}/profile")
    def update_profile(notebook_id: str, body: ProfileRequest):
        access = project_access(notebook_id)
        require_owner(access)
        if not project_locks.acquire(access["project_id"]):
            raise HTTPException(
                409, "Espera a que termine la respuesta antes de editar el proyecto."
            )
        try:
            with NotebookMemory(project_memory_path(access)) as memory:
                state = memory.update_profile(access["notebook_id"], body.context, body.color)
                if state is None:
                    raise HTTPException(404, "El cuaderno no existe.")
                return state.model_dump(mode="json")
        finally:
            project_locks.release(access["project_id"])

    @app.get("/api/notebooks/{notebook_id}")
    def get_notebook(notebook_id: str, request: Request):
        access = project_access(notebook_id)
        with NotebookMemory(project_memory_path(access)) as memory:
            if access["notebook_id"] not in {
                item["notebook_id"] for item in memory.list_notebooks()
            }:
                raise HTTPException(404, "El cuaderno no existe.")
            user = request.state.user
            if user and access["role"] == "owner":
                memory.claim_unattributed_notes(user.id, user.display_name)
                memory.claim_unattributed_turns(user.id)
            advances = sharing.advances(access["project_id"]) if user else []
            return {
                "state": memory.load(
                    ProjectState(notebook_id=access["notebook_id"]),
                    participant_id=user.id if user else None,
                    shared_context=shared_context(access, memory),
                ).model_dump(mode="json"),
                "turns": memory.history(access["notebook_id"],
                                        participant_id=user.id if user else None),
                "notes": memory.list_notes(access["notebook_id"]),
                "advances": advances,
                "access": access,
            }

    def require_notebook(memory, notebook_id):
        if notebook_id not in {item["notebook_id"] for item in memory.list_notebooks()}:
            raise HTTPException(404, "El cuaderno no existe.")

    @app.post("/api/notebooks/{notebook_id}/notes", status_code=201)
    def create_note(notebook_id: str, body: NoteRequest, request: Request):
        # El autor sale de la sesion, nunca del cuerpo de la peticion.
        user = request.state.user
        access = project_access(notebook_id)
        require_edit(access)
        with NotebookMemory(project_memory_path(access)) as memory:
            require_notebook(memory, access["notebook_id"])
            return memory.save_note(
                access["notebook_id"], body,
                author=(user.id, user.display_name) if user else None
            )

    @app.put("/api/notebooks/{notebook_id}/notes/{note_id}")
    def update_note(notebook_id: str, note_id: str, body: NoteRequest):
        access = project_access(notebook_id)
        require_edit(access)
        with NotebookMemory(project_memory_path(access)) as memory:
            try:
                note = memory.save_note(access["notebook_id"], body, note_id)
            except EditConflict as conflict:
                return conflict_response("este post-it", conflict.current)
            if note is None:
                raise HTTPException(404, "El post-it no existe en este cuaderno.")
            return note

    @app.delete("/api/notebooks/{notebook_id}/notes/{note_id}")
    def delete_note(notebook_id: str, note_id: str):
        access = project_access(notebook_id)
        require_edit(access)
        with NotebookMemory(project_memory_path(access)) as memory:
            if not memory.delete_note(access["notebook_id"], note_id):
                raise HTTPException(404, "El post-it no existe en este cuaderno.")
            return {"deleted": note_id}

    @app.delete("/api/notebooks/{notebook_id}")
    def delete_notebook(notebook_id: str):
        access = project_access(notebook_id)
        require_owner(access)
        if not project_locks.acquire(access["project_id"]):
            raise HTTPException(409, "Espera a que termine la respuesta antes de eliminar memoria.")
        try:
            with NotebookMemory(project_memory_path(access)) as memory:
                memory.delete(access["notebook_id"])
            with closing(sqlite3.connect(
                checkpoint_path(), check_same_thread=False
            )) as connection:
                _checkpointer(connection).delete_thread(access["project_id"])
            if access["owner_user_id"]:
                sharing.delete_project(access["project_id"])
            return {"deleted": access["notebook_id"]}
        finally:
            project_locks.release(access["project_id"])

    @app.get("/api/sharing/invitations")
    def list_invitations(request: Request):
        return sharing.invitations(request.state.user.id)

    @app.post("/api/sharing/invitations/{invitation_id}/respond")
    def respond_invitation(invitation_id: str, body: InvitationResponse, request: Request):
        sharing.respond(invitation_id, request.state.user.id, body.accept)
        return {"status": "accepted" if body.accept else "rejected"}

    @app.get("/api/projects/{project_id}/members")
    def list_project_members(project_id: str, request: Request):
        project_access(project_id)
        return sharing.members(project_id, request.state.user.id)

    @app.get("/api/projects/{project_id}/problem-tree")
    def get_problem_tree(project_id: str):
        access = project_access(project_id)
        return sharing.problem_tree(access["project_id"])

    @app.put("/api/projects/{project_id}/problem-tree")
    def save_problem_tree(project_id: str, body: ProblemTreeUpdate, request: Request):
        access = project_access(project_id)
        require_edit(access)
        user = request.state.user
        if not user:
            raise HTTPException(401, "Inicia sesión para guardar el árbol.")
        return sharing.save_problem_tree(
            access["project_id"], user.id,
            body.model_dump(exclude={"version"}), body.version,
        )

    @app.get("/api/projects/{project_id}/pestel")
    def get_pestel(project_id: str):
        access = project_access(project_id)
        return sharing.pestel(access["project_id"])

    @app.put("/api/projects/{project_id}/pestel")
    def save_pestel(project_id: str, body: PestelUpdate, request: Request):
        access = project_access(project_id)
        require_edit(access)
        user = request.state.user
        if not user:
            raise HTTPException(401, "Inicia sesión para guardar el PESTEL.")
        return sharing.save_pestel(
            access["project_id"], user.id,
            body.model_dump(exclude={"version"}), body.version,
        )

    @app.get("/api/projects/{project_id}/journey")
    def get_journey(project_id: str):
        access = project_access(project_id)
        return sharing.journey(access["project_id"])

    @app.put("/api/projects/{project_id}/journey")
    def save_journey(project_id: str, body: JourneyUpdate, request: Request):
        access = project_access(project_id)
        require_edit(access)
        user = request.state.user
        if not user:
            raise HTTPException(401, "Inicia sesión para guardar el recorrido.")
        return sharing.save_journey(
            access["project_id"], user.id,
            body.model_dump(exclude={"version"}), body.version,
        )

    @app.post("/api/projects/{project_id}/journey/extract")
    def extract_journey_notes(project_id: str, body: NotesRequest):
        """Propone post-its a partir de notas pegadas. No guarda nada: devuelve solo frases
        que están literales en el texto, para que la persona acepte una por una."""
        access = project_access(project_id)
        require_edit(access)
        journey = sharing.journey(access["project_id"])
        if not journey["stages"]:
            raise HTTPException(409, "Agrega primero las etapas del recorrido.")
        proposals: list[dict] = []
        discarded = 0
        started = time.perf_counter()
        if not model_queue.acquire(timeout=MODEL_WAIT_SHORT):
            model_status = "ocupado"
        else:
            try:
                extract = getattr(nuevo_runtime(), "extract_journey", None)
                if extract is None:
                    model_status = "no_disponible"
                else:
                    output = extract(
                        extraction_prompt(body.text, journey),
                        extraction_model(len(journey["stages"])),
                    )
                    proposals, discarded = grounded_quotes(output, body.text, journey)
                    model_status = "ok"
            except Exception:
                logger.exception("Fallo al leer notas para el recorrido")
                model_status = "no_disponible"
            finally:
                model_queue.release()
        return {
            "proposals": proposals,
            "model_status": model_status,
            "discarded": discarded,
            "elapsed_ms": round((time.perf_counter() - started) * 1000),
        }

    # ---------------------------------------------------- práctica con el cliente simulado

    def _practica(access: dict, practica_id: str, request: Request, memory) -> dict:
        user = request.state.user
        practica = memory.practica(access["notebook_id"], practica_id, user.id if user else "")
        if practica is None:
            raise HTTPException(404, "La práctica no existe.")
        return practica

    @app.post("/api/projects/{project_id}/practicas", status_code=201)
    def crear_practica(project_id: str, body: PracticaRequest, request: Request):
        access = project_access(project_id)
        require_edit(access)
        user = request.state.user
        with NotebookMemory(project_memory_path(access)) as memory:
            require_notebook(memory, access["notebook_id"])
            practica = memory.crear_practica(
                access["notebook_id"], body.persona.strip(), user.id if user else "")
        return {**practica, "aviso": AVISO_PRACTICA}

    @app.get("/api/projects/{project_id}/practicas")
    def listar_practicas(project_id: str, request: Request):
        """Para retomar la práctica desde otro navegador: la vista abre la más reciente."""
        access = project_access(project_id)
        user = request.state.user
        with NotebookMemory(project_memory_path(access)) as memory:
            return memory.practicas(access["notebook_id"], user.id if user else "")

    @app.get("/api/projects/{project_id}/practicas/{practica_id}")
    def ver_practica(project_id: str, practica_id: str, request: Request):
        access = project_access(project_id)
        with NotebookMemory(project_memory_path(access)) as memory:
            practica = _practica(access, practica_id, request, memory)
        preguntas = [t["texto"] for t in practica["turnos"] if t["rol"] == "entrevistador"]
        return {**practica, "retro": retroalimentacion(preguntas), "aviso": AVISO_PRACTICA}

    @app.post("/api/projects/{project_id}/practicas/{practica_id}/mensajes")
    def hablar_con_cliente(project_id: str, practica_id: str, body: PracticaMensaje,
                           request: Request):
        access = project_access(project_id)
        require_edit(access)
        with NotebookMemory(project_memory_path(access)) as memory:
            practica = _practica(access, practica_id, request, memory)
            reto = memory.load(ProjectState(notebook_id=access["notebook_id"])).context.question
        if not model_queue.acquire(timeout=MODEL_WAIT_SHORT):
            raise HTTPException(503, "Hilo está atendiendo a muchas personas; intenta de nuevo.")
        runtime = None
        try:
            runtime = nuevo_runtime()
            argumentos = (practica["persona"], reto, practica["turnos"], body.texto.strip())
            if hasattr(runtime, "responder_cliente"):  # respaldo con Claude
                respuesta = runtime.responder_cliente(*argumentos)
            else:
                respuesta = responder_cliente(runtime.client, settings.model, *argumentos)
        except Exception:
            logger.exception("Fallo del cliente simulado")
            raise HTTPException(503, "El cliente simulado no pudo responder.") from None
        finally:
            if runtime is not None:
                _close_runtime(runtime)
            model_queue.release()
        with NotebookMemory(project_memory_path(access)) as memory:
            memory.agregar_turnos_practica(practica_id, body.texto.strip(), respuesta)
        reglas = revisar_pregunta(body.texto)
        return {
            "respuesta": respuesta,
            "revision": {
                "bien": [r.nombre for r in reglas if r.buena],
                "evitar": [{"nombre": r.nombre, "cita": r.cita} for r in reglas if not r.buena],
            },
            "aviso": AVISO_PRACTICA,
        }

    @app.get("/api/projects/{project_id}/empathy-map")
    def get_empathy_map(project_id: str):
        access = project_access(project_id)
        return sharing.empathy_map(access["project_id"])

    @app.put("/api/projects/{project_id}/empathy-map")
    def save_empathy_map(project_id: str, body: EmpathyMapUpdate, request: Request):
        access = project_access(project_id)
        require_edit(access)
        user = request.state.user
        if not user:
            raise HTTPException(401, "Inicia sesión para guardar el mapa de empatía.")
        return sharing.save_empathy_map(
            access["project_id"], user.id,
            body.model_dump(exclude={"version"}), body.version,
        )

    @app.post("/api/projects/{project_id}/problem-tree/diagnosis")
    def diagnose_problem_tree(project_id: str):
        """Diagnostica la versión guardada. Las reglas siempre responden; la revisión
        de contenido depende del modelo y, si no está, se degrada sin fallar."""
        access = project_access(project_id)
        tree = sharing.problem_tree(access["project_id"])
        if not tree["problem"]:
            raise HTTPException(409, "Guarda el árbol antes de diagnosticarlo.")
        findings = rule_findings(tree)
        discarded = 0
        started = time.perf_counter()
        if not model_queue.acquire(timeout=MODEL_WAIT_SHORT):
            model_status = "ocupado"
        else:
            try:
                review = getattr(nuevo_runtime(), "review_tree", None)
                if review is None:
                    model_status = "no_disponible"
                else:
                    prompt = review_prompt(tree, catalog.tool_card(TREE_TOOL_ID))
                    content, discarded = grounded(review(prompt), tree)
                    findings.extend(content)
                    model_status = "ok"
            except Exception:
                logger.exception("Fallo en el diagnóstico de contenido del árbol")
                model_status = "no_disponible"
            finally:
                model_queue.release()
        sharing.save_tree_diagnosis(
            access["project_id"], tree["version"],
            summary_text(findings, tree, tree["version"], model_status),
        )
        return {
            "version": tree["version"],
            "findings": [finding.model_dump() for finding in findings],
            "model_status": model_status,
            "discarded": discarded,
            "elapsed_ms": round((time.perf_counter() - started) * 1000),
        }

    def why_access(project_id: str, request: Request) -> dict:
        access = project_access(project_id)
        require_edit(access)
        if not request.state.user:
            raise HTTPException(401, "Inicia sesión para trabajar el análisis.")
        if project_locks.busy(access["project_id"]):
            raise HTTPException(409, "Espera a que Hilo termine de responder.")
        return access

    @app.get("/api/projects/{project_id}/why-analyses")
    def list_why_analyses(project_id: str):
        return sharing.why_analyses(project_access(project_id)["project_id"])

    @app.post("/api/projects/{project_id}/why-analyses", status_code=201)
    def start_why_analysis(project_id: str, body: WhyStart, request: Request):
        access = why_access(project_id, request)
        return sharing.start_why_analysis(
            access["project_id"], request.state.user.id, body.cause_id,
        )

    @app.patch("/api/projects/{project_id}/why-analyses/{analysis_id}")
    def update_why_analysis(project_id: str, analysis_id: str, body: WhyUpdate,
                            request: Request):
        access = why_access(project_id, request)
        changes = body.model_dump(exclude_none=True)
        return sharing.update_why_analysis(access["project_id"], analysis_id, changes)

    @app.post("/api/projects/{project_id}/why-analyses/{analysis_id}/review")
    def review_why_analysis(project_id: str, analysis_id: str, request: Request):
        access = why_access(project_id, request)
        return sharing.set_why_status(access["project_id"], analysis_id, reviewing=True)

    @app.post("/api/projects/{project_id}/why-analyses/{analysis_id}/resume")
    def resume_why_analysis(project_id: str, analysis_id: str, request: Request):
        access = why_access(project_id, request)
        return sharing.set_why_status(access["project_id"], analysis_id, reviewing=False)

    @app.post("/api/projects/{project_id}/why-analyses/{analysis_id}/close")
    def close_why_analysis(project_id: str, analysis_id: str, body: WhyClose,
                           request: Request):
        access = why_access(project_id, request)
        return sharing.set_why_status(
            access["project_id"], analysis_id, status="cerrado", candidate=body.candidate,
        )

    @app.post("/api/projects/{project_id}/why-analyses/{analysis_id}/discard")
    def discard_why_analysis(project_id: str, analysis_id: str, request: Request):
        access = why_access(project_id, request)
        return sharing.set_why_status(access["project_id"], analysis_id, status="descartado")

    @app.post("/api/projects/{project_id}/why-analyses/{analysis_id}/incorporate")
    def incorporate_why_analysis(project_id: str, analysis_id: str, request: Request):
        access = why_access(project_id, request)
        return sharing.incorporate_why_analysis(
            access["project_id"], analysis_id, request.state.user.id,
        )

    @app.post("/api/projects/{project_id}/invitations", status_code=201)
    def invite_to_project(project_id: str, body: InvitationRequest, request: Request):
        access = project_access(project_id)
        require_owner(access)
        return sharing.invite(project_id, request.state.user.id, body.username, body.role)

    @app.delete("/api/sharing/invitations/{invitation_id}")
    def cancel_project_invitation(invitation_id: str, request: Request):
        sharing.cancel_invitation(invitation_id, request.state.user.id)
        return {"cancelled": invitation_id}

    @app.put("/api/projects/{project_id}/members/{user_id}")
    def change_project_member(project_id: str, user_id: str, body: MemberRoleRequest,
                              request: Request):
        sharing.change_member(project_id, request.state.user.id, user_id, body.role)
        return {"user_id": user_id, "role": body.role}

    @app.delete("/api/projects/{project_id}/members/{user_id}")
    def remove_project_member(project_id: str, user_id: str, request: Request):
        sharing.change_member(project_id, request.state.user.id, user_id, None)
        return {"removed": user_id}

    @app.post("/api/projects/{project_id}/leave")
    def leave_project(project_id: str, request: Request):
        access = project_access(project_id)
        if access["role"] == "owner":
            raise HTTPException(409, "La persona propietaria no puede abandonar su proyecto.")
        sharing.leave(project_id, request.state.user.id)
        return {"left": project_id}

    @app.post("/api/projects/{project_id}/advances", status_code=201)
    def save_project_advance(project_id: str, body: AdvanceRequest, request: Request):
        access = project_access(project_id)
        require_edit(access)
        return sharing.add_advance(
            project_id, request.state.user.id, request.state.user.display_name,
            body.content, body.kind,
        )

    @app.put("/api/projects/{project_id}/advances/{advance_id}")
    def correct_project_advance(project_id: str, advance_id: str, body: AdvanceUpdateRequest):
        access = project_access(project_id)
        require_edit(access)
        return sharing.update_advance(access["project_id"], advance_id, body.content,
                                      body.kind, body.version)

    @app.delete("/api/projects/{project_id}/advances/{advance_id}")
    def retire_project_advance(project_id: str, advance_id: str):
        access = project_access(project_id)
        require_edit(access)
        sharing.retire_advance(access["project_id"], advance_id)
        return {"retired": advance_id}

    @app.post("/api/chat")
    async def chat(body: ChatRequest, request: Request):
        access = project_access(body.project_id or body.notebook_id)
        user = request.state.user
        project_id = access["project_id"]
        if not project_locks.acquire(project_id):
            raise HTTPException(
                409, "Hilo está respondiendo en este proyecto. Espera y vuelve a enviar."
            )
        queue: asyncio.Queue = asyncio.Queue()
        loop = asyncio.get_running_loop()
        resolved_checkpoint_path = (
            auth.checkpoint_path(user, settings.checkpoint_path)
            if user else settings.checkpoint_path
        )
        if not user or user.legacy:
            resolved_audit_path = settings.audit_path
        else:
            resolved_audit_path = (
                settings.memory_path.parent / "users" / user.id / "verifications.jsonl"
            )
            resolved_audit_path.parent.mkdir(parents=True, exist_ok=True)

        def emit(event):
            loop.call_soon_threadsafe(queue.put_nowait, event)

        def generate():
            runtime = None
            started = time.monotonic()
            admitted = False
            try:
                # Si el modelo está lleno, la persona ve su lugar en la fila mientras espera.
                admitted = model_queue.acquire(
                    timeout=MODEL_WAIT_CHAT,
                    on_wait=lambda ahead: emit({"type": "queue", "ahead": ahead}),
                    heartbeat=QUEUE_HEARTBEAT,
                )
                if not admitted:
                    emit({"type": "error", "message": (
                        "Hay muchas personas usando Hilo en este momento. "
                        "Vuelve a enviar el mensaje en un momento."
                    )})
                    return
                with NotebookMemory(project_memory_path(access)) as memory, closing(sqlite3.connect(
                    resolved_checkpoint_path, check_same_thread=False
                )) as connection:
                    stage = catalog.stage(body.stage)
                    if user:
                        require_notebook(memory, access["notebook_id"])
                    elif access["notebook_id"] not in {
                        item["notebook_id"] for item in memory.list_notebooks()
                    }:
                        memory.create(ProjectState(
                            notebook_id=access["notebook_id"],
                            stage=stage.id,
                            phase=stage.phase,
                        ))
                    # La respuesta ya es el paso de la cadena: se registra antes de que el
                    # agente responda, para que pregunte por lo último dicho.
                    analysis = None
                    if access["owner_user_id"]:
                        # Un mensaje sensible no es un paso de la cadena: no se registra.
                        analysis = (
                            sharing.active_why_analysis(access["project_id"])
                            if access["role"] == "viewer" or sensitive_topic(body.message)
                            else sharing.record_why_turn(
                                access["project_id"], body.message.strip(),
                            )
                        )
                    state = memory.load(
                        ProjectState(notebook_id=access["notebook_id"],
                                     stage=stage.id, phase=stage.phase),
                        participant_id=user.id if user else None,
                        shared_context=shared_context(access, memory),
                    )
                    if analysis:
                        # La cadena (en el contexto compartido) es la fuente de verdad del
                        # análisis. El historial reciente solo le daba al modelo preguntas
                        # anteriores para copiar; se reconstruye desde la base al guardar.
                        state = state.model_copy(
                            update={"locked_tool": WHY_TOOL_ID, "recent_turns": []},
                        )
                    runtime = nuevo_runtime()
                    workflow = LangGraphRutaDia(
                        catalog, runtime, JsonlVerificationRecorder(resolved_audit_path),
                        checkpointer=_checkpointer(connection),
                    )
                    emit({"type": "session", "state": state.model_dump(mode="json")})
                    for event in workflow.stream_turn(
                        body.message.strip(), state,
                        thread_id=access["project_id"] if user else state.notebook_id,
                    ):
                        if event["type"] == "result":
                            event["result"]["modelo"] = origen_del_turno(
                                getattr(runtime, "calls", []))
                            result = TurnResult.model_validate(event["result"])
                            # Una respuesta puede tardar; el permiso se revisa de nuevo antes
                            # de guardar para respetar una revocacion o un cambio de rol.
                            role = access["role"]
                            if user:
                                current_access = sharing.access(user.id, access["project_id"])
                                if current_access is None:
                                    emit({"type": "error", "message": (
                                        "Tu acceso a este proyecto se retiró mientras Hilo "
                                        "respondía. La respuesta no se guardó."
                                    )})
                                    break
                                role = current_access["role"]
                            if role == "viewer":
                                next_state = memory.save_private_exchange(
                                    body.message.strip(), result, state, user.id
                                )
                            else:
                                next_state = memory.save_exchange(
                                    body.message.strip(), result, state, user.id if user else ""
                                )
                            event["state"] = next_state.model_dump(mode="json")
                            event["elapsed_ms"] = round((time.monotonic() - started) * 1000)
                            event["consumo"] = consumo_por_agente(getattr(runtime, "calls", []))
                        emit(event)
            except ModeloNoDisponible:
                logger.warning("Turno sin modelo: el local no responde y el respaldo se agotó")
                emit({"type": "error", "message": (
                    "El modelo de Hilo no está disponible en este momento. "
                    "Intenta de nuevo más tarde."
                )})
            except Exception:
                logger.exception("Fallo en un turno de la interfaz local")
                emit({
                    "type": "error",
                    "message": (
                        "No se pudo completar la respuesta. Comprueba que Qwen esté iniciado "
                        "y vuelve a enviar el mensaje."
                    ),
                })
            finally:
                try:
                    if runtime is not None:
                        _close_runtime(runtime)
                finally:
                    if admitted:
                        model_queue.release()
                    project_locks.release(project_id)
                    emit(None)

        # El trabajo continúa y guarda su resultado aunque el navegador se cierre o recargue.
        job = asyncio.create_task(asyncio.to_thread(generate))
        app.state.jobs.add(job)
        job.add_done_callback(app.state.jobs.discard)

        async def events():
            while True:
                event = await queue.get()
                if event is None:
                    return
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

        return StreamingResponse(
            events(), media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    dist = frontend_path or PROJECT_ROOT / "frontend" / "dist"
    if dist.is_dir():
        app.mount("/", StaticFiles(directory=dist, html=True), name="interface")
    else:
        @app.get("/")
        def missing_frontend():
            return JSONResponse(
                {"detail": "Construye la interfaz: pnpm --dir frontend build"}, 503
            )
    return app


def run_server(port: int = 8787) -> None:
    import uvicorn

    uvicorn.run(create_app(), host="127.0.0.1", port=port)
