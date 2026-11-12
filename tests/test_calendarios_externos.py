import base64
import json
import sqlite3
from dataclasses import replace
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from fastapi.testclient import TestClient
from test_auth import register

from hilo.config import Settings
from hilo.integraciones.calendarios import _utc_iso, proveedores_desde_entorno
from hilo.web import create_app

ENTORNO = {"HILO_GOOGLE_CLIENT_ID": "google-id", "HILO_GOOGLE_CLIENT_SECRET": "google-secreto",
           "HILO_MICROSOFT_CLIENT_ID": "ms-id", "HILO_MICROSOFT_CLIENT_SECRET": "ms-secreto"}


def id_token(email):
    cuerpo = base64.urlsafe_b64encode(json.dumps({"email": email}).encode()).decode().rstrip("=")
    return f"cabecera.{cuerpo}.firma"


class Proveedores:
    """Simula los servidores de Google y Microsoft y anota lo que Hilo les pide."""

    def __init__(self):
        self.pedidos: list[httpx.Request] = []
        self.alcance_google = ("openid https://www.googleapis.com/auth/userinfo.email "
                               "https://www.googleapis.com/auth/calendar.events.readonly")
        self.expira = 3600
        self.renovacion_valida = True
        self.revocados: list[str] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.pedidos.append(request)
        url = str(request.url)
        form = parse_qs(request.content.decode()) if request.method == "POST" else {}
        if url == "https://oauth2.googleapis.com/token" or url.endswith("/oauth2/v2.0/token"):
            google = "googleapis" in url
            if form["grant_type"] == ["refresh_token"] and not self.renovacion_valida:
                return httpx.Response(400, json={"error": "invalid_grant"})
            if form["grant_type"] == ["authorization_code"]:
                assert form["code"] == ["codigo-ok"] and form["code_verifier"]
            nuevo = "renovado" if form["grant_type"] == ["refresh_token"] else "inicial"
            return httpx.Response(200, json={
                "access_token": f"acceso-{nuevo}", "expires_in": self.expira,
                "refresh_token": None if google and nuevo == "renovado"
                else f"renovacion-{nuevo}-secreta",
                "id_token": id_token("ana@ejemplo.com"),
                **({"scope": self.alcance_google} if google else {}),
            })
        if url == "https://oauth2.googleapis.com/revoke":
            self.revocados.append(form["token"][0])
            return httpx.Response(200)
        if url.startswith("https://www.googleapis.com/calendar/v3/calendars/primary/events"):
            return httpx.Response(200, json={"items": [
                {"id": "g1", "summary": "Clase de diseño", "status": "confirmed",
                 "start": {"dateTime": "2026-11-12T09:00:00-05:00"},
                 "end": {"dateTime": "2026-11-12T10:00:00-05:00"},
                 "htmlLink": "https://www.google.com/calendar/event?eid=g1"},
                {"id": "g2", "summary": "Festivo", "start": {"date": "2026-11-16"},
                 "end": {"date": "2026-11-17"}, "htmlLink": "https://malicioso.example/x"},
                {"id": "g3", "status": "cancelled", "start": {"date": "2026-11-18"},
                 "end": {"date": "2026-11-19"}},
            ]})
        if url.startswith("https://graph.microsoft.com/v1.0/me/calendarView"):
            assert request.headers["Prefer"] == 'outlook.timezone="UTC"'
            return httpx.Response(200, json={"value": [
                {"id": "m1", "subject": "Comité", "isAllDay": False,
                 "start": {"dateTime": "2026-11-13T15:30:00.0000000", "timeZone": "UTC"},
                 "end": {"dateTime": "2026-11-13T16:00:00.0000000", "timeZone": "UTC"},
                 "webLink": "https://outlook.office365.com/owa/?itemid=m1"},
            ]})
        return httpx.Response(404)


@pytest.fixture
def entorno(tmp_path):
    settings = replace(
        Settings.from_env(),
        memory_path=tmp_path / "notebooks.sqlite3",
        checkpoint_path=tmp_path / "checkpoints.sqlite3",
        audit_path=tmp_path / "audit.jsonl",
        base_url="http://127.0.0.1:18083/v1",
    )
    servidores = Proveedores()
    app = create_app(settings, model_probe=lambda _: True,
                     calendar_providers=proveedores_desde_entorno(ENTORNO),
                     calendar_transport=httpx.MockTransport(servidores))
    return app, servidores, tmp_path


def conectar(client, proveedor, code="codigo-ok"):
    url = client.post(f"/api/calendarios/{proveedor}/conectar").json()["url"]
    state = parse_qs(urlparse(url).query)["state"][0]
    return client.get(f"/calendarios/{proveedor}/vuelta",
                      params={"code": code, "state": state}, follow_redirects=False)


def resultado(respuesta):
    return parse_qs(urlparse(respuesta.headers["location"]).query)


def test_connecting_google_and_outlook_shows_their_events(entorno):
    app, servidores, carpeta = entorno
    with TestClient(app) as client:
        register(client, "ana", "Ana")
        estado = client.get("/api/calendarios").json()["proveedores"]
        assert [(p["id"], p["configurado"], p["conectado"]) for p in estado] == [
            ("google", True, False), ("microsoft", True, False)]

        url = client.post("/api/calendarios/google/conectar").json()["url"]
        query = parse_qs(urlparse(url).query)
        assert url.startswith("https://accounts.google.com/o/oauth2/v2/auth?")
        assert query["code_challenge_method"] == ["S256"] and query["access_type"] == ["offline"]
        assert query["redirect_uri"] == ["http://testserver/calendarios/google/vuelta"]
        assert "calendar.events.readonly" in query["scope"][0]

        for proveedor in ("google", "microsoft"):
            vuelta = conectar(client, proveedor)
            assert vuelta.status_code == 303
            assert resultado(vuelta)["resultado"] == ["ok"]
        estado = client.get("/api/calendarios").json()["proveedores"]
        assert all(p["conectado"] and p["cuenta"] == "ana@ejemplo.com" for p in estado)

        datos = client.get("/api/calendario-externo", params={
            "desde": "2026-11-01T00:00:00-05:00", "hasta": "2026-12-01T00:00:00-05:00"}).json()
        assert datos["errores"] == []
        assert [(e["id"], e["inicio"], e["fin"], e["todo_el_dia"]) for e in datos["eventos"]] == [
            ("google:g1", "2026-11-12T14:00:00+00:00", "2026-11-12T15:00:00+00:00", False),
            ("microsoft:m1", "2026-11-13T15:30:00+00:00", "2026-11-13T16:00:00+00:00", False),
            ("google:g2", "2026-11-16", "2026-11-17", True),
        ]
        # Un enlace que no es del propio proveedor no se ofrece.
        enlaces = {e["id"]: e["enlace"] for e in datos["eventos"]}
        assert enlaces["google:g2"] is None and enlaces["google:g1"].startswith("https://www.")

    # Los tokens quedan cifrados en la base.
    crudo = (carpeta / "auth.sqlite3").read_bytes()
    assert b"renovacion-inicial-secreta" not in crudo and b"acceso-inicial" not in crudo


def test_the_callback_only_works_in_the_browser_that_started_it(entorno):
    app, _, _ = entorno
    with TestClient(app) as ana, TestClient(app) as otro:
        register(ana, "ana", "Ana")
        url = ana.post("/api/calendarios/google/conectar").json()["url"]
        state = parse_qs(urlparse(url).query)["state"][0]
        # Otro navegador (sin la cookie del inicio) no puede terminar el flujo de Ana.
        vuelta = otro.get("/calendarios/google/vuelta", params={"code": "codigo-ok",
                                                                "state": state},
                          follow_redirects=False)
        assert resultado(vuelta)["resultado"] == ["error"]
        # Y el state ya se gastó: tampoco sirve después en el navegador correcto.
        vuelta = ana.get("/calendarios/google/vuelta", params={"code": "codigo-ok",
                                                               "state": state},
                         follow_redirects=False)
        assert resultado(vuelta)["resultado"] == ["error"]
        assert not ana.get("/api/calendarios").json()["proveedores"][0]["conectado"]

        cancelado = ana.get("/calendarios/google/vuelta", params={"error": "access_denied"},
                            follow_redirects=False)
        assert resultado(cancelado)["resultado"] == ["cancelado"]


def test_google_needs_the_calendar_permission_checked(entorno):
    app, servidores, _ = entorno
    servidores.alcance_google = "openid https://www.googleapis.com/auth/userinfo.email"
    with TestClient(app) as client:
        register(client, "ana", "Ana")
        vuelta = resultado(conectar(client, "google"))
        assert vuelta["resultado"] == ["error"] and "permiso" in vuelta["motivo"][0]
        assert not client.get("/api/calendarios").json()["proveedores"][0]["conectado"]


def test_expired_access_is_renewed_and_a_revoked_one_asks_to_reconnect(entorno):
    app, servidores, carpeta = entorno
    servidores.expira = 30  # vence dentro del margen: la siguiente lectura renueva
    rango = {"desde": "2026-11-01T00:00:00Z", "hasta": "2026-11-30T00:00:00Z"}
    with TestClient(app) as client:
        register(client, "ana", "Ana")
        conectar(client, "microsoft")
        assert client.get("/api/calendario-externo", params=rango).json()["errores"] == []
        graph = [r for r in servidores.pedidos if "graph.microsoft.com" in str(r.url)]
        assert graph[-1].headers["Authorization"] == "Bearer acceso-renovado"
        # Microsoft rota el token de renovación y Hilo guarda el nuevo.
        with sqlite3.connect(carpeta / "auth.sqlite3") as db:
            assert db.execute("SELECT COUNT(*) FROM calendar_connections").fetchone()[0] == 1

        servidores.renovacion_valida = False
        datos = client.get("/api/calendario-externo", params=rango).json()
        assert datos["eventos"] == []
        assert datos["errores"][0]["proveedor"] == "microsoft"
        assert datos["errores"][0]["reconectar"] is True
        assert not client.get("/api/calendarios").json()["proveedores"][1]["conectado"]


def test_disconnecting_google_revokes_the_permission(entorno):
    app, servidores, _ = entorno
    with TestClient(app) as client:
        register(client, "ana", "Ana")
        conectar(client, "google")
        estado = client.delete("/api/calendarios/google").json()["proveedores"]
        assert not estado[0]["conectado"]
        assert servidores.revocados == ["renovacion-inicial-secreta"]


def test_without_credentials_the_provider_is_not_offered(tmp_path):
    settings = replace(
        Settings.from_env(),
        memory_path=tmp_path / "notebooks.sqlite3",
        checkpoint_path=tmp_path / "checkpoints.sqlite3",
        audit_path=tmp_path / "audit.jsonl",
        base_url="http://127.0.0.1:18083/v1",
    )
    app = create_app(settings, model_probe=lambda _: True,
                     calendar_providers=proveedores_desde_entorno({}))
    with TestClient(app) as client:
        assert client.get("/api/calendarios").status_code == 401
        register(client, "ana", "Ana")
        assert not any(p["configurado"]
                       for p in client.get("/api/calendarios").json()["proveedores"])
        assert client.post("/api/calendarios/google/conectar").status_code == 503
        assert client.post("/api/calendarios/yahoo/conectar").status_code == 404
        rango = {"desde": "2026-11-01T00:00:00Z", "hasta": "2027-06-01T00:00:00Z"}
        assert client.get("/api/calendario-externo", params=rango).status_code == 400


def test_graph_dates_with_seven_decimals_are_read():
    assert _utc_iso("2026-11-13T15:30:00.1234567Z") == "2026-11-13T15:30:00.123456+00:00"
