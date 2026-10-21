"""Temas sensibles: lo que Hilo no atiende, cómo lo reconoce y qué responde.

Todo es código y texto fijo, sin modelo: un mensaje sensible no llega al Orquestador. Un
proyecto *sobre* un tema delicado (salud mental, educación sexual, seguridad) sí se acompaña;
lo que se detecta aquí es la petición personal, la opinión o el contenido dañino.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Literal

SensitiveTopic = Literal["", "crisis", "dano", "sexual", "odio", "opinion", "consejo"]


def _plain(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text.casefold())
    return "".join(char for char in normalized if not unicodedata.combining(char))


_HARM_SELF = (
    r"matarme|morirme|morir|suicidarme|quitarme la vida|hacerme dano|lastimarme|cortarme|"
    r"desaparecer para siempre|acabar con (mi vida|todo)"
)
_FIGURATIVE = r"(?! de (la |el )?(risa|pena|verguenza|hambre|sueno|cansancio))"
# En primera persona: «prevenir el suicidio en jóvenes» es un proyecto, no una crisis.
_CRISIS = re.compile(
    r"\b(quiero|quisiera|voy a|pienso en|he pensado en|tengo ganas de|ganas de) "
    rf"({_HARM_SELF})\b{_FIGURATIVE}|"
    r"\bme (quiero|quisiera|voy a) "
    rf"(matar|morir|suicidar|quitar la vida|hacer dano|lastimar|cortar)\b{_FIGURATIVE}|"
    r"\bno quiero (seguir )?(vivir|viviendo|existir|existiendo)\b|\bsuicidarme\b|"
    r"\bno (vale|tiene) (la pena|sentido) (seguir )?(vivir|viviendo|estar viv[oa])\b|"
    r"\bno le (veo|encuentro) sentido a (la vida|vivir|seguir viviendo)\b|"
    r"\b(estaria|estaba|seria) mejor (estar )?muert[oa]\b|\bmejor me muero\b|"
    r"\bojala (me muriera|no despertara|no existiera)\b|"
    r"\b(todos|todo el mundo) (estarian|estaria) mejor sin mi\b|"
    # «quiero desaparecer» sola; «quiero desaparecer el papeleo» es un proyecto.
    r"\b(quiero|quisiera) desaparecer\b(?! (el|la|los|las|ese|esa|este|esta|mis|sus|un|una)\b)|"
    r"\bme (autolesiono|corto|hago dano)\b"
)
_DANGEROUS_THINGS = (
    r"bomba\w*|explosivo\w*|arma\w*|pistola\w*|veneno\w*|droga\w*|cocaina|metanfetamina|"
    r"fentanilo|bazuco|malware|virus informatico|ransomware"
)
_HARM = re.compile(
    r"\b(como|donde|ayudame a|ensename a|quiero|necesito|dime como|pasos para|"
    r"instrucciones para|receta (de|para))\b.{0,40}"
    r"\b(fabricar|hacer|armar|construir|conseguir|comprar|vender|preparar|cocinar|sintetizar|"
    rf"crear|programar)\b.{{0,25}}\b({_DANGEROUS_THINGS})\b|"
    r"\b(como|quiero|necesito|ayudame a|ensename a|dime como)\s+(puedo |podria |se puede )?"
    r"(hackear|jaquear|robar|estafar|falsificar|extorsionar|secuestrar|envenenar|"
    r"lavar (dinero|plata)|evadir impuestos|suplantar|clonar (una )?tarjetas?|espiar a)\b|"
    r"\b(quiero|voy a|como) (matar|golpear|lastimar|amenazar|vengarme de|hacerle dano) "
    r"(a|de) (mi|un|una|el|la|ese|esa|alguien)\b"
)
_SEXUAL = re.compile(
    r"\b(porno\w*|pornografi\w+|contenido (sexual|erotico)|relato erotico|cuento erotico|"
    r"sexo explicito|sexting|fantasia sexual|fotos? (intimas?|desnud[oa]s?)|"
    r"videos? (intimos?|sexual(es)?))\b"
)
_HATE = re.compile(
    r"\bodio a (los|las)\b|\bhay que (matar|eliminar|exterminar|sacar del pais) a\b|"
    r"\bson (una |unos |unas )?(plaga|inferiores|escoria|basura|subhumanos)\b|"
    r"\braza (superior|inferior)\b"
)
_OPINION_CUE = re.compile(
    r"\b(que opinas|que piensas|cual es tu (opinion|postura|posicion)|tu que crees|"
    r"estas de acuerdo|a favor o en contra|quien tiene la razon|es buen[oa] o mal[oa]|"
    r"quien deberia ganar|cual es (el|la) mejor|te gusta|apoyas|crees que|te parece que|"
    r"verdad que|cierto que)\b"
)
_OPINION_TOPIC = re.compile(
    r"\b(partidos? politicos?|candidat\w+|presidente|presidencia|eleccion(es)?|votar|"
    r"votaciones|izquierda|derecha|guerrilla\w*|paramilitar\w*|religion(es)?|dios|iglesia|"
    r"catolic\w+|cristianismo|cristianos|evangelic\w+|musulman\w+|islam|judios|judaismo|"
    r"ateo\w*|ateismo|aborto|eutanasia|pena de muerte|matrimonio (gay|igualitario)|"
    r"ideologia de genero|feminismo|machismo|inmigrantes|migrantes|israel|palestina|"
    r"los politicos|politiqueria|corrupt\w+|comunis\w+|capitalis\w+|socialis\w+)\b"
)
_VOTE = re.compile(r"\bpor quien (voto|votar|votarias|votaria|debo votar|deberia votar)\b")
_ADVICE = re.compile(
    r"\bque (medicamento|pastilla|remedio|dosis|antibiotico) (me|puedo|debo|tomo|tomar)\b|"
    r"\b(cuanto|cuanta|que dosis de) \w+ (debo|puedo|tengo que) tomar\b|"
    r"\b(me duele|tengo (fiebre|sintomas|dolor)|estoy enferm[oa])\b.{0,80}"
    r"\b(que (hago|tomo|sera)|es grave|que tengo)\b|"
    r"\b(diagnosticame|dame un diagnostico)\b|"
    r"\bcrees que tengo (depresion|ansiedad|tdah|cancer|diabetes)\b|"
    r"\b(debo|deberia|puedo|me conviene) (demandar|denunciar|divorciarme)\b|"
    r"\ben que (invierto|invertir|debo invertir)\b|"
    r"\b(compro|vendo|invierto en|me conviene comprar) "
    r"(bitcoin|acciones|criptomonedas?|dolares)\b|"
    r"\bcomo (bajo|bajar|puedo bajar) de peso\b"
)
# Datos personales que el asistente no debe pedir.
_PERSONAL_DATA = re.compile(
    r"\b(cedula|numero de (documento|identificacion|telefono|celular|cuenta|tarjeta)|"
    r"contrasena|nombre completo|direccion (exacta|de (tu|su) (casa|residencia)))\b"
)
_DISTRESS = re.compile(
    r"\b(estoy|me siento|me tiene|ando|quede|estamos|nos sentimos)\b.{0,15}"
    r"\b(muy |super |tan |re |bastante )?(frustrad|desanimad|desmotivad|agotad|abrumad|"
    r"estresad|angustiad|cansad|triste|decepcionad|hart[oa]\b|perdid[oa]\b|sol[oa]\b|mal\b|"
    r"sin ganas)|"
    r"\b(mi|nuestro|nuestra|el|la) (proyecto|negocio|emprendimiento|idea|empresa|tesis)\b.{0,25}"
    r"\b(fracaso|fracasando|no sirve|no funciono|se hundio|va muy mal|no avanza|"
    r"no va para ningun lado)\b|"
    r"\b(fracase|fracasamos|no puedo mas|quiero rendirme|voy a renunciar|tirar la toalla|"
    r"no sirvo para esto|me siento (un|una) (fracaso|inutil)|no se si vale la pena)\b"
)


def sensitive_topic(text: str) -> SensitiveTopic:
    """Categoría sensible del texto, o «» si no hay ninguna. La crisis personal va primero."""
    plain = _plain(text)
    if _CRISIS.search(plain):
        return "crisis"
    if _HARM.search(plain):
        return "dano"
    if _SEXUAL.search(plain):
        return "sexual"
    if _HATE.search(plain):
        return "odio"
    if _VOTE.search(plain) or (_OPINION_CUE.search(plain) and _OPINION_TOPIC.search(plain)):
        return "opinion"
    if _ADVICE.search(plain):
        return "consejo"
    return ""


def asks_personal_data(text: str) -> bool:
    return bool(_PERSONAL_DATA.search(_plain(text)))


def shows_distress(text: str) -> bool:
    """Desánimo con el proyecto, sin riesgo para la persona: se acompaña y se sigue."""
    return bool(_DISTRESS.search(_plain(text)))


_BACK_TO_PROJECT = "Con tu proyecto sí te acompaño: ¿qué parte quieres trabajar?"
SENSITIVE_REPLIES: dict[str, str] = {
    "crisis": (
        "Lamento mucho que estés pasando por esto. Lo que sientes importa más que el proyecto, "
        "y yo no soy la ayuda adecuada para acompañarte en ello. Por favor habla ahora con "
        "alguien de confianza o con un profesional: en Colombia puedes llamar al 123 "
        "(emergencias) y, si estás en Bogotá, a la línea 106 de apoyo emocional. El proyecto "
        "puede esperar; cuando quieras retomarlo, aquí estoy."
    ),
    "dano": (
        "Con eso no puedo ayudarte: puede hacerle daño a alguien o es ilegal. Si tu proyecto "
        "busca prevenir o resolver un problema así, cuéntame el reto y lo trabajamos con una "
        "ficha."
    ),
    "sexual": f"Ese contenido no lo trato aquí. {_BACK_TO_PROJECT}",
    "odio": (
        "No participo en mensajes que desprecian o atacan a un grupo de personas. "
        f"{_BACK_TO_PROJECT}"
    ),
    "opinion": (
        "Sobre política, religión y otros temas en los que la gente tiene posiciones "
        "encontradas no doy opinión: no me corresponde inclinarte hacia ningún lado. Si tu "
        "proyecto toca ese tema, puedo ayudarte a analizarlo con una ficha. "
        "¿Qué parte quieres trabajar?"
    ),
    "consejo": (
        "No puedo darte consejo médico, psicológico, legal ni financiero: una respuesta "
        "equivocada te puede perjudicar y eso lo debe ver un profesional. "
        f"{_BACK_TO_PROJECT}"
    ),
}
DISTRESS_OPENING = (
    "Siento que te estés sintiendo así. Que un proyecto se ponga cuesta arriba no dice nada malo "
    "de ti. Vamos con calma, un paso a la vez."
)
