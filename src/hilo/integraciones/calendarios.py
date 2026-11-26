"""Calendarios de Google y Microsoft conectados con la cuenta de cada persona (OAuth 2.0).

Hilo solo lee: muestra los eventos en su vista de calendario, sin guardarlos ni pasarlos al
modelo. El flujo es el de código de autorización con PKCE y cliente confidencial:

1. `iniciar()` crea un `state` de un solo uso, ligado a la cuenta y al navegador (cookie), y
   devuelve la dirección de consentimiento de Google o Microsoft.
2. El proveedor vuelve a `/calendarios/{proveedor}/vuelta` con `code` y `state`; `completar()`
   cambia el código por tokens y guarda el de renovación cifrado.
3. `eventos()` pide los del rango visible y renueva el token de acceso cuando vence.

Los tokens se cifran con Fernet. La clave sale de `HILO_CLAVE_CALENDARIOS` o, si no está, de un
archivo en la carpeta de datos que solo puede leer la cuenta que corre Hilo.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import sqlite3
import time
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode

import httpx
from cryptography.fernet import Fernet, InvalidToken

from ..compartido.errores import ErrorDeDominio

ESTADO_SEGUNDOS = 10 * 60
RANGO_MAXIMO = timedelta(days=100)
# Margen para renovar el token de acceso antes de que venza a mitad de una petición.
MARGEN_TOKEN = 60


class ErrorCalendario(ErrorDeDominio):
    def __init__(self, mensaje: str, estado: int = 400):
        super().__init__(mensaje)
        self.estado = estado


class ReconexionNecesaria(ErrorCalendario):
    """El proveedor ya no acepta el token de renovación: la persona debe conectar otra vez."""

    def __init__(self, nombre: str):
        super().__init__(f"{nombre} pidió volver a conectar la cuenta.", 409)


@dataclass(frozen=True)
class Proveedor:
    id: str
    nombre: str
    autorizacion: str
    token: str
    alcance: str
    # Permiso sin el cual la conexión no sirve: Google deja desmarcarlo en la pantalla.
    alcance_requerido: str
    client_id: str = ""
    client_secret: str = ""
    extra: dict[str, str] = field(default_factory=dict)
    revocar: str | None = None

    @property
    def configurado(self) -> bool:
        return bool(self.client_id and self.client_secret)


def proveedores_desde_entorno(entorno: dict[str, str] | None = None) -> dict[str, Proveedor]:
    entorno = os.environ if entorno is None else entorno
    tenant = entorno.get("HILO_MICROSOFT_TENANT", "").strip() or "common"
    google_calendar = "https://www.googleapis.com/auth/calendar.events.readonly"
    graph_calendar = "https://graph.microsoft.com/Calendars.Read"
    return {
        "google": Proveedor(
            id="google", nombre="Google Calendar",
            autorizacion="https://accounts.google.com/o/oauth2/v2/auth",
            token="https://oauth2.googleapis.com/token",
            alcance=f"openid email {google_calendar}", alcance_requerido=google_calendar,
            client_id=entorno.get("HILO_GOOGLE_CLIENT_ID", "").strip(),
            client_secret=entorno.get("HILO_GOOGLE_CLIENT_SECRET", "").strip(),
            # offline + consent: sin ellos Google no entrega token de renovación la 2.ª vez.
            extra={"access_type": "offline", "prompt": "consent",
                   "include_granted_scopes": "true"},
            revocar="https://oauth2.googleapis.com/revoke",
        ),
        "microsoft": Proveedor(
            id="microsoft", nombre="Outlook",
            autorizacion=f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize",
            token=f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
            alcance=f"openid email offline_access {graph_calendar}",
            alcance_requerido="Calendars.Read",
            client_id=entorno.get("HILO_MICROSOFT_CLIENT_ID", "").strip(),
            client_secret=entorno.get("HILO_MICROSOFT_CLIENT_SECRET", "").strip(),
            extra={"prompt": "select_account"},
        ),
    }


def _hash(valor: str) -> bytes:
    return hashlib.sha256(valor.encode("ascii", "replace")).digest()


def _pkce() -> tuple[str, str]:
    verificador = secrets.token_urlsafe(64)
    reto = base64.urlsafe_b64encode(hashlib.sha256(verificador.encode()).digest())
    return verificador, reto.rstrip(b"=").decode()


def _cuenta_del_id_token(id_token: str | None) -> str:
    """Correo de la cuenta. El id_token llega directo del proveedor por TLS en el mismo
    intercambio, así que basta leerlo (OpenID Connect Core, 3.1.3.7)."""
    if not id_token or id_token.count(".") != 2:
        return ""
    cuerpo = id_token.split(".")[1]
    try:
        datos = json.loads(base64.urlsafe_b64decode(cuerpo + "=" * (-len(cuerpo) % 4)))
    except (ValueError, json.JSONDecodeError):
        return ""
    return str(datos.get("email") or datos.get("preferred_username") or "")[:200]


def clave_de_cifrado(carpeta: Path, entorno: dict[str, str] | None = None) -> bytes:
    entorno = os.environ if entorno is None else entorno
    if entorno.get("HILO_CLAVE_CALENDARIOS", "").strip():
        return entorno["HILO_CLAVE_CALENDARIOS"].strip().encode()
    archivo = carpeta / "calendarios.key"
    if not archivo.exists():
        carpeta.mkdir(parents=True, exist_ok=True)
        archivo.write_bytes(Fernet.generate_key())
        if os.name == "posix":
            archivo.chmod(0o600)
    return archivo.read_bytes().strip()


class CalendariosExternos:
    def __init__(self, base: Path, cifrado: bytes, proveedores: dict[str, Proveedor],
                 transporte: httpx.BaseTransport | None = None, reloj=time.time):
        self.base, self.proveedores, self.reloj = base, proveedores, reloj
        self._fernet = Fernet(cifrado)
        self._http = httpx.Client(transport=transporte, timeout=15.0,
                                  headers={"User-Agent": "Hilo/1.0"})
        with self._conectar() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS calendar_connections (
                    user_id TEXT NOT NULL, provider TEXT NOT NULL, account TEXT NOT NULL,
                    refresh_token BLOB NOT NULL, access_token BLOB, expires_at INTEGER,
                    created_at INTEGER NOT NULL, PRIMARY KEY (user_id, provider)
                );
                CREATE TABLE IF NOT EXISTS calendar_oauth_states (
                    state_hash BLOB PRIMARY KEY, browser_hash BLOB NOT NULL,
                    user_id TEXT NOT NULL, provider TEXT NOT NULL, verifier TEXT NOT NULL,
                    expires_at INTEGER NOT NULL
                );
            """)

    def _conectar(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.base, timeout=5)
        db.execute("PRAGMA busy_timeout=5000")
        return db

    def proveedor(self, proveedor_id: str) -> Proveedor:
        proveedor = self.proveedores.get(proveedor_id)
        if not proveedor:
            raise ErrorCalendario("Ese calendario no existe.", 404)
        if not proveedor.configurado:
            raise ErrorCalendario(f"{proveedor.nombre} todavía no está configurado en este "
                                  "servidor.", 503)
        return proveedor

    # --- Estado de cada cuenta ---------------------------------------------------------

    def estado(self, user_id: str) -> list[dict]:
        with self._conectar() as db:
            filas = dict(db.execute(
                "SELECT provider, account FROM calendar_connections WHERE user_id=?",
                (user_id,)).fetchall())
        return [{"id": p.id, "nombre": p.nombre, "configurado": p.configurado,
                 "conectado": p.id in filas, "cuenta": filas.get(p.id) or None}
                for p in self.proveedores.values()]

    def conectados(self, user_id: str) -> list[str]:
        return [item["id"] for item in self.estado(user_id) if item["conectado"]]

    # --- Conexión --------------------------------------------------------------------

    def iniciar(self, user_id: str, proveedor_id: str, redirect_uri: str) -> tuple[str, str]:
        """Dirección de consentimiento y el valor para la cookie que liga el navegador."""
        proveedor = self.proveedor(proveedor_id)
        state, navegador = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        verificador, reto = _pkce()
        ahora = int(self.reloj())
        with self._conectar() as db:
            db.execute("DELETE FROM calendar_oauth_states WHERE expires_at<=?", (ahora,))
            db.execute("INSERT INTO calendar_oauth_states VALUES (?, ?, ?, ?, ?, ?)",
                       (_hash(state), _hash(navegador), user_id, proveedor.id, verificador,
                        ahora + ESTADO_SEGUNDOS))
        parametros = {
            "client_id": proveedor.client_id, "response_type": "code",
            "redirect_uri": redirect_uri, "scope": proveedor.alcance, "state": state,
            "code_challenge": reto, "code_challenge_method": "S256", **proveedor.extra,
        }
        return f"{proveedor.autorizacion}?{urlencode(parametros)}", navegador

    def completar(self, proveedor_id: str, state: str, navegador: str | None, code: str,
                  redirect_uri: str) -> str:
        """Cambia el código por tokens. Devuelve el id de la cuenta de Hilo conectada."""
        proveedor = self.proveedor(proveedor_id)
        with self._conectar() as db:
            fila = db.execute(
                "SELECT browser_hash, user_id, provider, verifier, expires_at "
                "FROM calendar_oauth_states WHERE state_hash=?", (_hash(state),)).fetchone()
            # Un solo uso, salga bien o mal.
            db.execute("DELETE FROM calendar_oauth_states WHERE state_hash=?", (_hash(state),))
        # La cookie evita que alguien termine en su navegador un flujo iniciado por otra cuenta
        # (y así conecte su calendario a la cuenta de Hilo de un tercero, o al revés).
        if (not fila or fila[2] != proveedor.id or fila[4] <= self.reloj() or not navegador
                or not secrets.compare_digest(fila[0], _hash(navegador))):
            raise ErrorCalendario("La conexión venció o no empezó en este navegador. "
                                  "Inténtalo de nuevo desde Ajustes.")
        respuesta = self._pedir_token(proveedor, {
            "grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri,
            "code_verifier": fila[3],
        })
        concedido = respuesta.get("scope", proveedor.alcance)
        if proveedor.alcance_requerido not in concedido:
            raise ErrorCalendario(f"Para conectar {proveedor.nombre} hay que dejar marcado el "
                                  "permiso de ver los eventos del calendario.")
        if not respuesta.get("refresh_token"):
            raise ErrorCalendario(f"{proveedor.nombre} no entregó permiso permanente. "
                                  "Quita el acceso a Hilo en tu cuenta y conéctala de nuevo.")
        ahora = int(self.reloj())
        with self._conectar() as db:
            db.execute(
                "INSERT INTO calendar_connections VALUES (?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(user_id, provider) DO UPDATE SET account=excluded.account, "
                "refresh_token=excluded.refresh_token, access_token=excluded.access_token, "
                "expires_at=excluded.expires_at, created_at=excluded.created_at",
                (fila[1], proveedor.id, _cuenta_del_id_token(respuesta.get("id_token")),
                 self._cifrar(respuesta["refresh_token"]),
                 self._cifrar(respuesta["access_token"]),
                 ahora + int(respuesta.get("expires_in", 3600)), ahora))
        return fila[1]

    def desconectar(self, user_id: str, proveedor_id: str) -> None:
        proveedor = self.proveedores.get(proveedor_id)
        if not proveedor:
            raise ErrorCalendario("Ese calendario no existe.", 404)
        with self._conectar() as db:
            fila = db.execute("SELECT refresh_token FROM calendar_connections "
                              "WHERE user_id=? AND provider=?", (user_id, proveedor_id)).fetchone()
            db.execute("DELETE FROM calendar_connections WHERE user_id=? AND provider=?",
                       (user_id, proveedor_id))
        # Google permite anular el permiso desde aquí; en Microsoft lo quita la persona en su
        # cuenta. Si falla, la conexión igual queda borrada de Hilo.
        if fila and proveedor.revocar:
            with suppress(httpx.HTTPError, ErrorCalendario):
                self._http.post(proveedor.revocar, data={"token": self._descifrar(fila[0])})

    # --- Eventos ---------------------------------------------------------------------

    def eventos(self, user_id: str, desde: datetime, hasta: datetime) -> dict:
        if hasta <= desde or hasta - desde > RANGO_MAXIMO:
            raise ErrorCalendario("El rango de fechas no es válido.")
        eventos, errores = [], []
        for proveedor_id in self.conectados(user_id):
            proveedor = self.proveedores[proveedor_id]
            try:
                token = self._token_de_acceso(user_id, proveedor)
                leer = self._eventos_google if proveedor_id == "google" else self._eventos_graph
                eventos.extend(leer(token, desde, hasta))
            except ErrorCalendario as error:
                errores.append({"proveedor": proveedor_id, "mensaje": error.mensaje,
                                "reconectar": isinstance(error, ReconexionNecesaria)})
            except httpx.HTTPError:
                errores.append({"proveedor": proveedor_id, "reconectar": False,
                                "mensaje": f"No se pudo leer {proveedor.nombre}. "
                                           "Se intentará de nuevo."})
        eventos.sort(key=lambda item: item["inicio"])
        return {"eventos": eventos, "errores": errores}

    def _token_de_acceso(self, user_id: str, proveedor: Proveedor) -> str:
        with self._conectar() as db:
            fila = db.execute(
                "SELECT refresh_token, access_token, expires_at FROM calendar_connections "
                "WHERE user_id=? AND provider=?", (user_id, proveedor.id)).fetchone()
        if not fila:
            raise ReconexionNecesaria(proveedor.nombre)
        if fila[1] and fila[2] and fila[2] - MARGEN_TOKEN > self.reloj():
            return self._descifrar(fila[1])
        try:
            respuesta = self._pedir_token(proveedor, {
                "grant_type": "refresh_token", "refresh_token": self._descifrar(fila[0]),
            })
        except ReconexionNecesaria:
            # El permiso se revocó o venció (en Google, cada 7 días si la app está en prueba).
            with self._conectar() as db:
                db.execute("DELETE FROM calendar_connections WHERE user_id=? AND provider=?",
                           (user_id, proveedor.id))
            raise
        with self._conectar() as db:
            # Microsoft rota el token de renovación en cada uso; Google lo mantiene.
            db.execute(
                "UPDATE calendar_connections SET access_token=?, expires_at=?, "
                "refresh_token=COALESCE(?, refresh_token) WHERE user_id=? AND provider=?",
                (self._cifrar(respuesta["access_token"]),
                 int(self.reloj()) + int(respuesta.get("expires_in", 3600)),
                 self._cifrar(respuesta["refresh_token"]) if respuesta.get("refresh_token")
                 else None, user_id, proveedor.id))
        return respuesta["access_token"]

    def _pedir_token(self, proveedor: Proveedor, datos: dict[str, str]) -> dict:
        respuesta = self._http.post(proveedor.token, data={
            **datos, "client_id": proveedor.client_id, "client_secret": proveedor.client_secret,
        }, headers={"Accept": "application/json"})
        cuerpo = respuesta.json() if respuesta.content else {}
        if respuesta.status_code == 400 and cuerpo.get("error") == "invalid_grant":
            raise ReconexionNecesaria(proveedor.nombre)
        if respuesta.status_code != 200 or "access_token" not in cuerpo:
            raise ErrorCalendario(f"{proveedor.nombre} rechazó la conexión "
                                  f"({cuerpo.get('error', respuesta.status_code)}).", 502)
        return cuerpo

    def _leer(self, url: str, token: str, parametros: dict, cabeceras: dict | None = None,
              nombre: str = "") -> dict:
        respuesta = self._http.get(url, params=parametros, headers={
            "Authorization": f"Bearer {token}", **(cabeceras or {})})
        if respuesta.status_code == 401:
            raise ReconexionNecesaria(nombre)
        if respuesta.status_code != 200:
            raise ErrorCalendario(f"{nombre} respondió con un error "
                                  f"({respuesta.status_code}).", 502)
        return respuesta.json()

    def _eventos_google(self, token: str, desde: datetime, hasta: datetime) -> list[dict]:
        salida, pagina = [], None
        for _ in range(4):  # hasta 1000 eventos en el rango
            datos = self._leer(
                "https://www.googleapis.com/calendar/v3/calendars/primary/events", token,
                {"timeMin": _rfc3339(desde), "timeMax": _rfc3339(hasta), "singleEvents": "true",
                 "orderBy": "startTime", "maxResults": 250,
                 **({"pageToken": pagina} if pagina else {})},
                nombre="Google Calendar")
            for item in datos.get("items", []):
                if item.get("status") == "cancelled":
                    continue
                todo_el_dia = "date" in item.get("start", {})
                inicio = item["start"].get("date") or _utc_iso(item["start"].get("dateTime"))
                fin = item.get("end", {}).get("date") or _utc_iso(
                    item.get("end", {}).get("dateTime"))
                salida.append(_evento("google", item.get("id", ""), item.get("summary"),
                                      inicio, fin, todo_el_dia, item.get("htmlLink")))
            pagina = datos.get("nextPageToken")
            if not pagina:
                break
        return salida

    def _eventos_graph(self, token: str, desde: datetime, hasta: datetime) -> list[dict]:
        salida = []
        url, parametros = "https://graph.microsoft.com/v1.0/me/calendarView", {
            "startDateTime": _rfc3339(desde), "endDateTime": _rfc3339(hasta), "$top": 250,
            "$orderby": "start/dateTime",
            "$select": "id,subject,start,end,isAllDay,isCancelled,webLink",
        }
        for _ in range(4):
            datos = self._leer(url, token, parametros, {"Prefer": 'outlook.timezone="UTC"'},
                               nombre="Outlook")
            for item in datos.get("value", []):
                if item.get("isCancelled"):
                    continue
                todo_el_dia = bool(item.get("isAllDay"))
                inicio, fin = item["start"]["dateTime"], item["end"]["dateTime"]
                if todo_el_dia:
                    inicio, fin = inicio[:10], fin[:10]
                else:
                    inicio, fin = _utc_iso(inicio + "Z"), _utc_iso(fin + "Z")
                salida.append(_evento("microsoft", item.get("id", ""), item.get("subject"),
                                      inicio, fin, todo_el_dia, item.get("webLink")))
            url = datos.get("@odata.nextLink")
            parametros = {}
            if not url:
                break
        return salida

    def _cifrar(self, valor: str) -> bytes:
        return self._fernet.encrypt(valor.encode())

    def _descifrar(self, valor: bytes) -> str:
        try:
            return self._fernet.decrypt(bytes(valor)).decode()
        except InvalidToken as error:
            # La clave cambió: los tokens guardados ya no sirven.
            raise ErrorCalendario("La clave de los calendarios cambió; conecta la cuenta "
                                  "de nuevo.", 409) from error


def _rfc3339(fecha: datetime) -> str:
    return fecha.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _utc_iso(valor: str | None) -> str:
    if not valor:
        return ""
    # Graph manda siete decimales; fromisoformat solo acepta seis.
    if "." in valor:
        entero, resto = valor.split(".", 1)
        zona = next((resto[i:] for i, c in enumerate(resto) if c in "Z+-"), "")
        valor = f"{entero}.{resto[:len(resto) - len(zona)][:6]}{zona}"
    fecha = datetime.fromisoformat(valor.replace("Z", "+00:00"))
    return fecha.astimezone(UTC).isoformat()


def _evento(proveedor: str, id_: str, titulo: str | None, inicio: str, fin: str,
            todo_el_dia: bool, enlace: str | None) -> dict:
    # Solo se ofrece abrir el evento en el sitio del propio proveedor.
    seguro = enlace if enlace and enlace.startswith((
        "https://www.google.com/calendar/", "https://calendar.google.com/",
        "https://outlook.office365.com/", "https://outlook.live.com/",
        "https://outlook.office.com/")) else None
    return {"id": f"{proveedor}:{id_}", "proveedor": proveedor,
            "titulo": (titulo or "").strip()[:300] or "(Sin título)",
            "inicio": inicio, "fin": fin or inicio, "todo_el_dia": todo_el_dia,
            "enlace": seguro}
