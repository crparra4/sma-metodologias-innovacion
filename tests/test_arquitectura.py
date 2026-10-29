"""El mapa de contextos (DDD) como prueba: dónde empieza y dónde termina cada módulo.

Cada carpeta de `hilo` es un contexto delimitado. Esta prueba lee las importaciones del
código y falla si un contexto usa otro que no está en su lista, o si el dominio importa el
framework web. La capa de entrada (`web.py`, `cli.py`) arma la aplicación y puede usarlos todos;
`config.py` lo puede usar cualquiera. El detalle está en `docs/dominio-ddd.md`.
"""

import ast
from pathlib import Path

PAQUETE = Path(__file__).resolve().parents[1] / "src" / "hilo"
ENTRADA = {"web.py", "cli.py", "__init__.py", "__main__.py", "config.py"}

PERMITIDOS = {
    "compartido": set(),
    "conocimiento": {"compartido"},
    "herramientas": {"compartido"},
    "practica": {"compartido"},
    "identidad": {"compartido"},
    "inferencia": set(),
    "proyectos": {"compartido", "herramientas"},
    "acompanamiento": {"compartido", "conocimiento", "inferencia"},
    "evaluacion": {"acompanamiento", "compartido", "conocimiento", "inferencia"},
}
# Bibliotecas que solo puede usar la capa de entrada.
SOLO_ENTRADA = {"fastapi", "starlette", "uvicorn"}


def _contextos() -> list[str]:
    return sorted(p.name for p in PAQUETE.iterdir()
                  if p.is_dir() and (p / "__init__.py").exists())


def _importaciones(archivo: Path) -> list[tuple[str, str]]:
    """(contexto o biblioteca importada, texto de la importación) de un archivo."""
    contexto = archivo.parent.name
    salida = []
    for nodo in ast.walk(ast.parse(archivo.read_text(encoding="utf-8"))):
        if isinstance(nodo, ast.ImportFrom) and nodo.level == 2 and nodo.module:
            salida.append((nodo.module.split(".")[0], f"from ..{nodo.module} import"))
        elif isinstance(nodo, ast.ImportFrom) and nodo.level == 1:
            salida.append((contexto, f"from .{nodo.module or ''} import"))
        elif isinstance(nodo, ast.ImportFrom) and nodo.level == 0 and nodo.module:
            salida.append((nodo.module.split(".")[0], f"from {nodo.module} import"))
        elif isinstance(nodo, ast.Import):
            salida.extend((a.name.split(".")[0], f"import {a.name}") for a in nodo.names)
    return salida


def test_every_context_is_in_the_context_map():
    assert _contextos() == sorted(PERMITIDOS)


def test_the_package_root_only_has_the_entry_layer():
    sueltos = {p.name for p in PAQUETE.glob("*.py")}
    assert sueltos <= ENTRADA, f"módulos fuera de un contexto: {sorted(sueltos - ENTRADA)}"


def test_contexts_only_use_the_contexts_allowed_by_the_map():
    violaciones = []
    for contexto, permitidos in PERMITIDOS.items():
        for archivo in sorted((PAQUETE / contexto).glob("*.py")):
            for destino, texto in _importaciones(archivo):
                if destino in PERMITIDOS and destino != contexto and destino not in permitidos:
                    violaciones.append(f"{contexto}/{archivo.name}: {texto} ({destino})")
                if destino in {"web", "cli"}:
                    violaciones.append(f"{contexto}/{archivo.name}: {texto} (capa de entrada)")
    assert not violaciones, "\n".join(violaciones)


def test_the_domain_does_not_depend_on_the_web_framework():
    violaciones = [
        f"{archivo.parent.name}/{archivo.name}: {texto}"
        for contexto in PERMITIDOS
        for archivo in sorted((PAQUETE / contexto).glob("*.py"))
        for destino, texto in _importaciones(archivo)
        if destino in SOLO_ENTRADA
    ]
    assert not violaciones, "\n".join(violaciones)


def test_inference_knows_nothing_of_agents_cards_or_projects():
    """Aguas arriba del mapa: si inferencia conociera el dominio, no se podría separar como
    servicio ni cambiar de proveedor sin tocar a los agentes."""
    usados = {destino for archivo in (PAQUETE / "inferencia").glob("*.py")
              for destino, _ in _importaciones(archivo)}
    assert not usados & (set(PERMITIDOS) - {"inferencia"})
