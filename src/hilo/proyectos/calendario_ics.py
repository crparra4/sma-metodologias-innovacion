"""El calendario de Hilo como archivo iCalendar (RFC 5545), para suscribirse desde fuera.

Google Calendar, Outlook y Apple Calendar se suscriben a un enlace .ics y lo vuelven a leer
cada cierto tiempo (Google, cada varias horas). La suscripción es de solo lectura: lo que se
cambie allá no vuelve a Hilo. Cada entrada sale como VEVENT, porque Google ignora los VTODO.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

# Una tarea o un recordatorio sin hora de fin se muestra como un bloque corto.
DURACION_SIN_FIN = timedelta(minutes=30)
TIPOS = {"tarea": "Tarea", "recordatorio": "Recordatorio", "reunion": "Reunión"}
IMPORTANCIA = {"high": "alta", "medium": "media", "low": "baja"}


def _texto(valor: str) -> str:
    """Escapa un valor TEXT: barra invertida, punto y coma, coma y saltos de línea."""
    return (valor.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")
            .replace("\r\n", "\\n").replace("\n", "\\n").replace("\r", "\\n"))


def _plegar(linea: str) -> list[str]:
    """Corta en trozos de hasta 75 octetos sin partir un carácter UTF-8 (RFC 5545, 3.1)."""
    trozos, actual, tamano, limite = [], "", 0, 75
    for caracter in linea:
        ancho = len(caracter.encode("utf-8"))
        if tamano + ancho > limite:
            trozos.append(actual)
            # Las líneas de continuación empiezan con un espacio, que cuenta en el límite.
            actual, tamano, limite = " ", 1, 75
        actual += caracter
        tamano += ancho
    trozos.append(actual)
    return trozos


def _fecha(valor: str | datetime) -> datetime:
    fecha = datetime.fromisoformat(valor) if isinstance(valor, str) else valor
    return (fecha if fecha.tzinfo else fecha.replace(tzinfo=UTC)).astimezone(UTC)


def _utc(valor: str | datetime) -> str:
    return _fecha(valor).strftime("%Y%m%dT%H%M%SZ")


def generar_ics(entradas: list[dict], ahora: datetime | None = None,
                nombre: str = "Hilo") -> str:
    """Documento VCALENDAR con una VEVENT por entrada (tareas, recordatorios y reuniones)."""
    sello = _utc(ahora or datetime.now(UTC))
    lineas = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Hilo//Calendario//ES",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{_texto(nombre)}",
        # Sugerencia de cada cuánto volver a leerlo; Google la ignora y usa su propio ritmo.
        "REFRESH-INTERVAL;VALUE=DURATION:PT1H",
        "X-PUBLISHED-TTL:PT1H",
    ]
    for entrada in entradas:
        inicio = _fecha(entrada["due_at"])
        fin = _fecha(entrada["ends_at"]) if entrada.get("ends_at") else inicio + DURACION_SIN_FIN
        tipo = TIPOS.get(entrada.get("kind") or "tarea", "Tarea")
        titulo = entrada["title"]
        if entrada.get("completed"):
            titulo = f"✓ {titulo}"
        detalle = [tipo, f"Importancia {IMPORTANCIA.get(entrada.get('priority'), 'media')}"]
        if entrada.get("notebook_id"):
            detalle.append(f"Proyecto: {entrada['notebook_id']}")
        modificada = entrada.get("updated_at")
        lineas += [
            "BEGIN:VEVENT",
            f"UID:{entrada['id']}@hilo",
            f"DTSTAMP:{sello}",
            f"DTSTART:{_utc(inicio)}",
            f"DTEND:{_utc(fin)}",
            f"SUMMARY:{_texto(titulo)}",
            f"DESCRIPTION:{_texto(' · '.join(detalle))}",
            f"CATEGORIES:{_texto(tipo)}",
            # Solo las reuniones ocupan el horario; una tarea o un recordatorio no lo bloquean.
            f"TRANSP:{'OPAQUE' if entrada.get('kind') == 'reunion' else 'TRANSPARENT'}",
            *([f"LAST-MODIFIED:{_utc(modificada)}"] if modificada else []),
            "END:VEVENT",
        ]
    lineas.append("END:VCALENDAR")
    return "".join(f"{trozo}\r\n" for linea in lineas for trozo in _plegar(linea))
