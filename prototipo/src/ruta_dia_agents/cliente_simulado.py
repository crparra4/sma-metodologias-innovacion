"""Cliente simulado: practicar una entrevista antes de salir a campo.

Es un agente aparte, con su propio contexto: solo conoce su personaje y la entrevista. No ve las
fichas ni las instrucciones del Metodólogo; si las viera, respondería lo que el método busca y la
práctica no serviría. Por eso no puede ser el mismo agente que guía.

La retroalimentación sobre las preguntas la da el código, citando literalmente la ficha de
Trabajo de campo: no depende del modelo y no inventa criterios. Lo que el cliente responde es
práctica, nunca evidencia: no entra en la ficha, ni en los campos verificados, ni en el contexto
que ve el Orquestador.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

AVISO = (
    "Cliente simulado: es una práctica. Lo que responda no es evidencia de tus usuarios reales "
    "y no se guarda en la ficha."
)
LARGO_PERSONA = 600


def _plano(texto: str) -> str:
    normalizado = unicodedata.normalize("NFKD", texto.casefold())
    return "".join(c for c in normalizado if not unicodedata.combining(c))


@dataclass(frozen=True)
class Regla:
    codigo: str
    nombre: str
    cita: str  # literal de la ficha «Trabajo de campo»
    patron: re.Pattern
    buena: bool = False


_INTERROGATIVAS = (
    r"que|como|cuando|donde|por que|porque|cual|cuales|cuanto|cuanta|cuantos|cuantas|quien|"
    r"quienes|para que|en que|de que|con que|a que"
)
REGLAS: tuple[Regla, ...] = (
    Regla(
        "dirigida", "Pregunta dirigida",
        "Nada de preguntas dirigidas.",
        re.compile(r"\b(no (crees|cree|te parece|le parece|seria|es cierto)|verdad que|"
                   r"cierto que|seria genial|no te gustaria|no le gustaria)\b|"
                   r"[,\s]¿?\s*(verdad|cierto|no)\s*\?"),
    ),
    Regla(
        "hipotetica", "Pregunta hipotética",
        "Cuidado con la deseabilidad social (dan la respuesta que creen que quieres oír)",
        re.compile(r"\b(usarias|usaria|comprarias|compraria|pagarias|pagaria|te gustaria|"
                   r"le gustaria|si (existiera|hubiera|tuvieras|tuviera|pudieras|pudiera))\b"),
    ),
    Regla(
        "generalidad", "Pregunta por lo general",
        "Pregunta por hechos específicos, no generalidades",
        re.compile(r"\b(usualmente|normalmente|en general|por lo general|generalmente|"
                   r"siempre|todos los dias|habitualmente)\b"),
    ),
    Regla(
        "doble", "Dos preguntas en una",
        "Evita preguntas de doble cañón (dos temas a la vez) y de sí/no.",
        re.compile(rf"\?.*\?|\by (tambien )?({_INTERROGATIVAS})\b"),
    ),
    Regla(
        "si_no", "Pregunta de sí o no",
        "Evita preguntas de doble cañón (dos temas a la vez) y de sí/no.",
        # Se decide en `revisar_pregunta`: sin palabra interrogativa es de sí o no.
        re.compile(r"(?!x)x"),
    ),
    Regla(
        "opinion", "Comparte su opinión",
        "no compartas tus opiniones",
        re.compile(r"\b(yo creo que|en mi opinion|a mi me parece|yo pienso que|para mi)\b"),
    ),
    Regla(
        "historia", "Pide una historia, un porqué o cómo se siente",
        'incluye muchas de "cuéntame de la última vez que…", "¿por qué?" y preguntas sobre '
        "cómo se SIENTE.",
        re.compile(r"\b(cuentame|cuenteme|la ultima vez|caminame|describeme|describame|"
                   r"como fue|que paso|que hiciste|que hizo|por que|como se sintio|"
                   r"como te sentiste|que sentiste|que sintio|como se siente|como te sientes)\b"),
        buena=True,
    ),
)


_CON_TILDE = re.compile(
    r"\b(qué|cómo|cuándo|dónde|cuál|cuáles|cuánto|cuánta|cuántos|cuántas|quién|quiénes)\b",
    re.IGNORECASE,
)
_ABRE_SIN_TILDE = re.compile(rf"(^|¿)\s*({_INTERROGATIVAS})\b")


def _es_si_no(texto: str, plano: str) -> bool:
    """Sin palabra interrogativa («¿Tienes celular?», «¿Usarías…?») es de sí o no.

    Las interrogativas se reconocen con tilde en cualquier parte («¿Normalmente cómo…?») o,
    sin tilde, al abrir la pregunta («¿que paso?»), porque «que» sin tilde suele ser conjunción.
    """
    return "?" in texto and not (_CON_TILDE.search(texto) or _ABRE_SIN_TILDE.search(plano))


def revisar_pregunta(texto: str) -> list[Regla]:
    """Reglas que la pregunta del entrevistador cumple (buenas) o rompe (las demás)."""
    plano = _plano(texto.strip())
    halladas = [regla for regla in REGLAS if regla.patron.search(plano)]
    buena = any(regla.buena for regla in halladas)
    if _es_si_no(texto, plano) and not buena:  # «¿Me cuentas…?» no es de sí o no
        halladas.append(next(regla for regla in REGLAS if regla.codigo == "si_no"))
    if "?" not in texto:  # una afirmación del entrevistador no cuenta como pregunta doble
        halladas = [regla for regla in halladas if regla.codigo != "doble"]
    return sorted(halladas, key=REGLAS.index)


def retroalimentacion(preguntas: list[str]) -> dict:
    """Resumen de la práctica: qué se hizo bien y qué evitar, con la cita de la ficha."""
    detalle = []
    conteo: dict[str, int] = {}
    for texto in preguntas:
        reglas = revisar_pregunta(texto)
        for regla in reglas:
            conteo[regla.codigo] = conteo.get(regla.codigo, 0) + 1
        detalle.append({
            "pregunta": texto,
            "bien": [r.nombre for r in reglas if r.buena],
            "evitar": [{"nombre": r.nombre, "cita": r.cita} for r in reglas if not r.buena],
        })
    limpias = sum(1 for d in detalle if not d["evitar"])
    return {
        "preguntas": len(preguntas),
        "sin_problemas": limpias,
        "detalle": detalle,
        "consejos": [
            {"nombre": regla.nombre, "cita": regla.cita, "veces": conteo[regla.codigo]}
            for regla in REGLAS if not regla.buena and conteo.get(regla.codigo)
        ],
        "aviso": AVISO,
    }


def instruccion_personaje(persona: str, reto: str) -> str:
    """Lo único que sabe el cliente simulado: quién es y de qué lo van a entrevistar."""
    return f"""Haces de una persona real en una entrevista. Esta es la persona:
{persona.strip()[:LARGO_PERSONA]}

Te entrevista alguien de un equipo que trabaja en este tema: {reto.strip() or "su proyecto"}.

Reglas:
- Responde en primera persona, como hablaría esta persona en Colombia, en una a tres frases.
- Habla de tu experiencia concreta. Si te piden contar una vez concreta («cuéntame de la última
  vez que…»), cuenta un episodio con detalles: qué pasó, qué hiciste, cómo te sentiste.
- Si la pregunta es de sí o no, responde corto y sin profundizar.
- Si la pregunta es dirigida o hipotética («¿no sería genial…?», «¿usarías…?», «¿pagarías…?»),
  responde con amabilidad lo que crees que el entrevistador quiere oír, sin comprometerte de
  verdad, como hace mucha gente.
- No conoces métodos de innovación ni sabes qué busca el entrevistador. No das consejos de
  diseño ni propones soluciones.
- Si te preguntan algo que esta persona no sabría, dilo.
- Si te preguntan directamente si eres real, di que eres un personaje simulado para practicar."""


def responder(client, modelo: str, persona: str, reto: str, turnos: list[dict],
              pregunta: str) -> str:
    """Respuesta del cliente simulado. `turnos`: [{"rol": "entrevistador"|"cliente", "texto"}]."""
    mensajes = [{"role": "system", "content": instruccion_personaje(persona, reto)}]
    for turno in turnos[-12:]:
        rol = "user" if turno["rol"] == "entrevistador" else "assistant"
        mensajes.append({"role": rol, "content": turno["texto"]})
    mensajes.append({"role": "user", "content": pregunta})
    respuesta = client.chat.completions.create(
        model=modelo, messages=mensajes, max_tokens=220, temperature=0.8,
        extra_body={"chat_template_kwargs": {"enable_thinking": False}},
    )
    texto = (respuesta.choices[0].message.content or "").strip()
    if not texto:
        raise ValueError("El cliente simulado no respondió")
    return texto
