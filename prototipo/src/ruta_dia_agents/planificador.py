"""Planificador: lleva el avance de la ficha y decide la intención de cada turno.

Así funcionan los tutores que guían con preguntas y sí escuchan (KELE, IntelliCode, StratL): el
estado vive fuera del modelo, un solo componente lo escribe y el modelo solo redacta lo que toca.
En la evaluación exigente, 73 % de los fallos de escucha de Hilo eran volver a pedir algo que la
persona ya había dicho: el modelo de 4B no lleva bien esa cuenta. Aquí la lleva el código.

El avance de cada ficha es un diccionario guardable en JSON:
    {"en_curso": "<id de la parte preguntada>", "partes": {"<id>": {"estado", "texto"}}}
Se guarda con cada respuesta (`TurnResult.progreso`) y la memoria lo devuelve en el turno
siguiente (`ProjectState.progreso`): queda versionado turno a turno.
"""

from __future__ import annotations

import copy
import json
import re
import unicodedata
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

ARCHIVO = Path(__file__).with_name("partes_fichas.json")
RESPONDIDA = "respondida"
NO_SABE = "no_sabe"
LARGO_TEXTO = 200


@dataclass(frozen=True)
class Parte:
    id: str
    nombre: str
    definicion: str
    alias: tuple[str, ...] = ()
    prellenar: str = ""


@dataclass
class Plan:
    intencion: str  # «preguntar», «aclarar» o «cerrar»
    objetivo: Parte | None
    progreso: dict
    aclaracion: str = ""
    nota: str = ""
    respondidas: list[Parte] = field(default_factory=list)
    sin_saber: list[Parte] = field(default_factory=list)


def _plano(texto: str) -> str:
    normalizado = unicodedata.normalize("NFKD", texto.casefold())
    return "".join(c for c in normalizado if not unicodedata.combining(c))


@lru_cache(maxsize=1)
def _todas() -> dict[str, tuple[Parte, ...]]:
    datos = json.loads(ARCHIVO.read_text(encoding="utf-8"))["fichas"]
    return {
        ficha: tuple(
            Parte(p["id"], p["nombre"], p["definicion"], tuple(p.get("alias", ())),
                  p.get("prellenar", ""))
            for p in partes
        )
        for ficha, partes in datos.items()
    }


def partes_de(tool_id: str) -> tuple[Parte, ...]:
    return _todas().get(tool_id, ())


def _patron(parte: Parte) -> re.Pattern:
    nombres = sorted({_plano(a) for a in (*parte.alias, parte.nombre) if a}, key=len, reverse=True)
    return re.compile(r"(?<!\w)(" + "|".join(re.escape(n) for n in nombres) + r")(?!\w)")


def _posicion(texto_plano: str, parte: Parte) -> int | None:
    hallado = _patron(parte).search(texto_plano)
    return hallado.start() if hallado else None


def _frases(texto: str) -> list[str]:
    return [f.strip() for f in re.split(r"(?<=[.!?¿\n])\s+", texto) if f.strip()]


def _sin_citas(texto: str) -> str:
    return re.sub(r"«[^»]*»|“[^”]*”|\"[^\"]*\"|\*\*[^*]*\*\*", "", texto)


_NO_SE = re.compile(
    r"\b(no se|ni idea|no tengo (ni )?idea|no lo se|no sabria|no conozco (ninguna|ninguno|nada)"
    r"|no se me ocurre|ninguna mas|ninguno mas|no tengo datos|de eso no se|no tengo como saber)\b"
)
_PEDIDO = re.compile(
    r"\b(pasemos|pasamos|pasar|sigamos|seguimos|vamos|empecemos|empezamos|arranquemos|"
    r"mejor|trabajemos|hagamos)\b"
)
_DUDA = re.compile(
    r"\b(que (significa|quiere decir|es eso|es esto|seria)|cuenta como|cuentan como|va en|"
    r"van en|diferencia (hay )?entre|(cual|que) es la diferencia|a que se refiere|como asi|"
    r"que (es|son) (un|una|el|la|los|las|lo) |eso (cuenta|sirve|va|aplica)|"
    r"(en|a) (que|cual) (bloque|factor|parte|sombrero|lente|patron) va)\b"
)
# «Quiero hacer el árbol de problemas» pide empezar la ficha: no responde ninguna de sus partes.
_PIDE_FICHA = re.compile(
    r"\b(quiero|quisiera|me gustaria|vamos a|hagamos|ayudame (a|con)|empecemos( con)?|"
    r"necesito|podemos) (hacer|aplicar|usar|empezar|trabajar|armar|construir|con|el|la|los)\b"
)
_ETIQUETA = (
    r"(^|[.;!?\n]\s*)((en|sobre|para|de) (lo|el|la|los|las) )?((factor|bloque|parte|sombrero) )?"
)


def es_duda(mensaje: str) -> bool:
    """Una duda puntual («¿eso cuenta como político?», «¿qué significa normativa?»).

    «¿Qué hago?» o «¿por dónde empiezo?» no son dudas: piden seguir.
    """
    return "?" in mensaje and bool(_DUDA.search(_plano(mensaje)))


def parte_pedida(mensaje: str, partes: tuple[Parte, ...]) -> Parte | None:
    """La parte a la que la persona pide pasar («pasemos a lo económico»)."""
    plano = _plano(mensaje)
    pedido = _PEDIDO.search(plano)
    if not pedido:
        return None
    resto = plano[pedido.start():]
    halladas = [(pos, p) for p in partes if (pos := _posicion(resto, p)) is not None]
    return min(halladas, key=lambda par: par[0])[1] if halladas else None


def partes_etiquetadas(mensaje: str, partes: tuple[Parte, ...]) -> dict[str, str]:
    """Datos que la persona etiquetó con el nombre de la parte («En lo político, …»)."""
    plano = _plano(mensaje)
    halladas: dict[str, str] = {}
    for parte in partes:
        nombres = _patron(parte).pattern
        etiqueta = re.search(_ETIQUETA + nombres + r"\s*[:,]\s*(.+)", plano)
        if etiqueta:
            inicio = etiqueta.start(etiqueta.lastindex)
            halladas[parte.id] = mensaje[inicio:inicio + LARGO_TEXTO].strip()
    return halladas


def _contenido(mensaje: str) -> str:
    """Lo que la persona afirmó, sin sus preguntas."""
    return " ".join(f for f in _frases(mensaje) if "?" not in f)


def _definicion_para(duda: str, partes: tuple[Parte, ...], en_curso: Parte | None) -> Parte | None:
    preguntas = " ".join(f for f in _frases(duda) if "?" in f) or duda
    plano = _plano(preguntas)
    # Gana el nombre más largo: en «¿qué es una causa de fondo?» también aparece «causa».
    nombradas = [(-len(m.group()), m.start(), p) for p in partes
                 if (m := _patron(p).search(plano))]
    if nombradas:
        return min(nombradas, key=lambda par: par[:2])[2]
    palabras = {w for w in re.findall(r"\w{5,}", plano)} - {"significa", "quiere", "decir",
                                                              "cuenta", "diferencia", "refiere"}
    for parte in partes:
        if palabras & set(re.findall(r"\w{5,}", _plano(parte.definicion))):
            return parte
    return en_curso


def salida_con_plan(plan: Plan | None) -> str | None:
    """Salida segura cuando el modelo no logró una pregunta que pasara la verificación.

    En vez de pegar el paso a paso de la ficha, pregunta por la parte que decidió el
    Planificador, con su definición literal: no depende del modelo y no vuelve a lo respondido.
    """
    if plan is None or plan.objetivo is None:
        return None
    partes = [plan.aclaracion] if plan.aclaracion else []
    if _cita(plan.objetivo) in plan.aclaracion:  # la aclaración ya citó esta parte
        partes.append(f"Sigamos con **{plan.objetivo.nombre}**.")
    else:
        partes.append(f"Sigamos con **{plan.objetivo.nombre}**. La ficha lo explica así: "
                      f"{_cita(plan.objetivo)}")
    partes.append("¿Qué puedes contarme de eso en tu proyecto?")
    return "\n\n".join(partes)


def _cita(parte: Parte) -> str:
    return "«" + parte.definicion.replace("**", "").replace("«", "").replace("»", "") + "»"


def planear(tool_id: str, progreso: dict | None, mensaje: str, reto: str = "") -> Plan | None:
    """Actualiza el avance con lo que dijo la persona y decide qué toca en este turno."""
    partes = partes_de(tool_id)
    if not partes:
        return None
    por_id = {p.id: p for p in partes}
    estado = copy.deepcopy(progreso) if progreso else {"en_curso": "", "partes": {}}
    estado.setdefault("partes", {})
    registro = estado["partes"]
    if reto.strip():  # el reto del cuaderno responde la parte «reto» si todavía falta
        for parte in partes:
            if parte.prellenar == "reto" and parte.id not in registro:
                registro[parte.id] = {"estado": RESPONDIDA, "texto": reto.strip()[:LARGO_TEXTO]}
    plano = _plano(mensaje)
    duda = es_duda(mensaje)
    pedida = parte_pedida(mensaje, partes)
    etiquetadas = partes_etiquetadas(mensaje, partes)
    for parte_id, texto in etiquetadas.items():
        registro[parte_id] = {"estado": RESPONDIDA, "texto": texto}
    nota = ""
    en_curso = por_id.get(estado.get("en_curso") or "")
    # La respuesta cuenta para la parte preguntada salvo que la persona haya etiquetado otra
    # («En lo social, …»), pida pasar a otra o tenga una duda: con una duda se aclara y se
    # sigue en la misma parte.
    pide_ficha = bool(_PIDE_FICHA.search(plano)) and all(
        palabra in plano for palabra in tool_id.split("-") if len(palabra) > 2)
    if (en_curso and en_curso.id not in registro and not etiquetadas and not pedida
            and not duda and not pide_ficha):
        contenido = _contenido(mensaje)
        # «No sé, ¿2 de 10 ya sería bueno?» es una respuesta tentativa, no un «no sé».
        tentativa = len(_NO_SE.sub("", plano).split()) >= 6
        if _NO_SE.search(plano) and not tentativa:
            registro[en_curso.id] = {"estado": NO_SABE, "texto": ""}
            nota = "Lo dejamos anotado como algo por averiguar."
        elif len(contenido.split()) >= 3 or tentativa:
            registro[en_curso.id] = {"estado": RESPONDIDA,
                                     "texto": (contenido or mensaje)[:LARGO_TEXTO]}
    # La parte pedida manda; si no, se retoma la que estaba en curso y quedó sin responder
    # (por una duda o porque la persona habló de otra) y, si no, la siguiente pendiente.
    pendiente = en_curso if en_curso and en_curso.id not in registro else None
    objetivo = pedida or pendiente or next((p for p in partes if p.id not in registro), None)
    aclaracion = ""
    if duda:
        parte = _definicion_para(mensaje, partes, en_curso)
        aclaracion = (
            f"Sobre tu duda, la ficha dice: {_cita(parte)}" if parte
            else "Esa duda no la resuelve la ficha: anótala como algo por averiguar."
        )
    estado["en_curso"] = objetivo.id if objetivo else ""
    return Plan(
        intencion="cerrar" if objetivo is None else "aclarar" if duda else "preguntar",
        objetivo=objetivo,
        progreso=estado,
        aclaracion=aclaracion,
        nota=nota,
        respondidas=[por_id[i] for i, d in registro.items()
                     if d["estado"] == RESPONDIDA and i in por_id],
        sin_saber=[por_id[i] for i, d in registro.items()
                   if d["estado"] == NO_SABE and i in por_id],
    )


def bloque_para_metodologo(plan: Plan) -> str:
    """Lo que el Metodólogo recibe: la parte que toca y lo que no debe volver a pedir."""
    objetivo = plan.objetivo
    lineas = [
        "PLAN DEL TURNO (lo decidió el Planificador con el avance de la ficha; síguelo):",
        f"- Parte que toca ahora: «{objetivo.nombre}». En la ficha: {_cita(objetivo)}",
    ]
    textos = plan.progreso["partes"]
    if plan.respondidas:
        lineas.append("- Ya respondido por la persona (no lo vuelvas a pedir):")
        lineas += [f"  - {p.nombre}: «{textos[p.id]['texto']}»" for p in plan.respondidas]
    if plan.sin_saber:
        lineas.append("- La persona no lo sabe (no insistas): "
                      + ", ".join(p.nombre for p in plan.sin_saber))
    lineas.append(
        f"- En message haz UNA sola pregunta concreta sobre «{objetivo.nombre}», en palabras "
        "sencillas y partiendo de lo último que dijo la persona. No preguntes por otras partes."
    )
    return "\n".join(lineas)


def cierre(plan: Plan, nombre_ficha: str) -> str:
    """Respuesta fija cuando Hilo ya preguntó por cada parte.

    Solo dice lo que es cierto: que ya se preguntó por cada parte. No afirma que la ficha esté
    completa ni resume lo anotado, porque el código no sabe si cada respuesta fue completa (en
    la evaluación exigente, un resumen así exponía partes a medias como terminadas).
    """
    pendientes = ", ".join(p.nombre for p in plan.sin_saber)
    return (
        f"Ya te pregunté por cada parte de **{nombre_ficha}**."
        + (f" Quedaron por averiguar: {pendientes}." if pendientes else "")
        + " ¿Hay alguna parte que quieras completar o revisar antes de pasar a la siguiente ficha?"
    )


def _recorte(texto: str, largo: int = 90) -> str:
    texto = " ".join(texto.split())
    return texto if len(texto) <= largo else texto[:largo].rsplit(" ", 1)[0] + "…"


def partes_repetidas(mensaje: str, plan: Plan) -> list[Parte]:
    """Partes ya respondidas (o que la persona no sabe) por las que vuelve a preguntar."""
    cerradas = [p for p in (*plan.respondidas, *plan.sin_saber)
                if not plan.objetivo or p.id != plan.objetivo.id]
    preguntas = _plano(_sin_citas(" ".join(f for f in _frases(mensaje) if "?" in f)))
    objetivo = _patron(plan.objetivo) if plan.objetivo else None
    repetidas = []
    for parte in cerradas:
        if _posicion(preguntas, parte) is None:
            continue
        # Un alias compartido con la parte que toca no es repetir («dolores» en dos bloques).
        hallado = _patron(parte).search(preguntas)
        if objetivo and objetivo.search(hallado.group(0)):
            continue
        repetidas.append(parte)
    return repetidas
