from datetime import UTC, datetime

from fastapi.testclient import TestClient
from test_auth import client_for, register

from hilo.proyectos.calendario_ics import generar_ics

AHORA = datetime(2026, 11, 9, 12, 0, tzinfo=UTC)


def entrada(**cambios):
    base = {"id": "t1", "title": "Revisar prototipo", "kind": "tarea",
            "due_at": "2026-11-10T15:00:00+00:00", "ends_at": None, "priority": "high",
            "notebook_id": None, "completed": False, "updated_at": "2026-11-09T10:00:00+00:00"}
    return {**base, **cambios}


def eventos(texto: str) -> list[dict[str, str]]:
    """Desdobla las líneas y devuelve cada VEVENT como diccionario de propiedades."""
    lineas = texto.replace("\r\n ", "").split("\r\n")
    salida, actual = [], None
    for linea in lineas:
        if linea == "BEGIN:VEVENT":
            actual = {}
        elif linea == "END:VEVENT":
            salida.append(actual)
            actual = None
        elif actual is not None:
            clave, _, valor = linea.partition(":")
            actual[clave] = valor
    return salida


def test_each_entry_becomes_an_event_in_utc():
    texto = generar_ics([
        entrada(),
        entrada(id="t2", title="Asesoría", kind="reunion",
                due_at="2026-11-11T09:00:00-05:00", ends_at="2026-11-11T10:30:00-05:00"),
    ], AHORA)
    assert texto.startswith("BEGIN:VCALENDAR\r\nVERSION:2.0\r\n")
    assert texto.endswith("END:VCALENDAR\r\n")
    tarea, reunion = eventos(texto)
    assert tarea["UID"] == "t1@hilo"
    assert tarea["DTSTAMP"] == "20261109T120000Z"
    # Sin hora de fin, la tarea ocupa media hora y no bloquea el horario.
    assert (tarea["DTSTART"], tarea["DTEND"]) == ("20261110T150000Z", "20261110T153000Z")
    assert tarea["TRANSP"] == "TRANSPARENT"
    assert tarea["DESCRIPTION"] == "Tarea · Importancia alta"
    assert (reunion["DTSTART"], reunion["DTEND"]) == ("20261111T140000Z", "20261111T153000Z")
    assert reunion["TRANSP"] == "OPAQUE"
    assert reunion["CATEGORIES"] == "Reunión"


def test_text_is_escaped_and_long_lines_are_folded():
    titulo = "Entrevista; usuarios, \\ notas\nsegunda línea " + "á" * 80
    texto = generar_ics([entrada(title=titulo, notebook_id="App de reserva", completed=True)],
                        AHORA)
    assert all(len(linea.encode("utf-8")) <= 75 for linea in texto.split("\r\n"))
    evento = eventos(texto)[0]
    assert evento["SUMMARY"] == (
        "✓ Entrevista\\; usuarios\\, \\\\ notas\\nsegunda línea " + "á" * 80)
    assert evento["DESCRIPTION"].endswith("Proyecto: App de reserva")


def test_feed_link_serves_only_the_owner_entries_and_can_be_changed(tmp_path):
    client, _ = client_for(tmp_path)
    with client:
        # Sin cuenta, el enlace no existe; con cuenta, empieza desactivado.
        assert client.get("/api/calendar-feed").status_code == 401
        register(client, "ana", "Ana")
        assert client.get("/api/calendar-feed").json() == {"path": None, "created_at": None}
        client.post("/api/tasks", json={"title": "Tarea de Ana",
                                        "due_at": "2026-11-10T10:00:00-05:00"})
        path = client.post("/api/calendar-feed").json()["path"]
        assert path.startswith("/calendario/") and path.endswith(".ics")
        assert client.get("/api/calendar-feed").json()["path"] == path

        client.post("/api/auth/logout")
        register(client, "bruno", "Bruno")
        client.post("/api/tasks", json={"title": "Tarea de Bruno",
                                        "due_at": "2026-11-10T10:00:00-05:00"})
        bruno_path = client.post("/api/calendar-feed").json()["path"]

        # Google lo lee sin cookie de sesión.
        with TestClient(client.app) as google:
            feed = google.get(path)
            assert feed.status_code == 200
            assert feed.headers["content-type"].startswith("text/calendar")
            assert "Tarea de Ana" in feed.text and "Tarea de Bruno" not in feed.text
            assert "Tarea de Bruno" in google.get(bruno_path).text
            assert google.get("/calendario/no-existe.ics").status_code == 404

        # Cambiar el enlace invalida el anterior; desactivarlo lo quita.
        renewed = client.post("/api/calendar-feed").json()["path"]
        assert renewed != bruno_path
        assert client.get(bruno_path).status_code == 404
        assert client.get(renewed).status_code == 200
        assert client.delete("/api/calendar-feed").json()["path"] is None
        assert client.get(renewed).status_code == 404
