from __future__ import annotations

import argparse
import json
import sqlite3
import sys

from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.checkpoint.sqlite import SqliteSaver

from .audit import JsonlVerificationRecorder
from .config import Settings
from .contracts import ProjectState
from .direct_runtime import DirectOpenAIRuntime
from .knowledge import KnowledgeCatalog
from .langgraph_workflow import LangGraphRutaDia
from .memory import NotebookMemory
from .runtime import CrewAIRuntime
from .service import RutaDiaService


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Núcleo multiagente Ruta DIA")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("validate", help="Valida rutas, herramientas y fichas")
    web = subparsers.add_parser("web", help="Abre el servidor de la interfaz gráfica local")
    web.add_argument("--port", type=int, default=8787)

    chat = subparsers.add_parser("chat", help="Ejecuta un turno real de los tres agentes")
    chat.add_argument("--message", required=True)
    chat.add_argument("--stage", type=int, default=1)
    chat.add_argument("--phase", default="Descubrimiento")
    chat.add_argument("--notebook", default="demo")
    chat.add_argument("--role", default="")
    chat.add_argument("--runtime", choices=["langgraph", "crewai"])

    interactive = subparsers.add_parser(
        "interactive", help="Mantiene una conversación de varios turnos"
    )
    interactive.add_argument("--stage", type=int, default=1)
    interactive.add_argument("--phase", default="Descubrimiento")
    interactive.add_argument("--notebook", default="sesion-interactiva")
    interactive.add_argument("--role", default="")
    interactive.add_argument("--runtime", choices=["langgraph", "crewai"])

    memory = subparsers.add_parser("memory", help="Consulta o elimina un cuaderno persistente")
    memory.add_argument("action", choices=["show", "clear"])
    memory.add_argument("--notebook", required=True)
    return parser


def _service(settings: Settings, catalog: KnowledgeCatalog, runtime_name: str, checkpointer=None):
    recorder = JsonlVerificationRecorder(settings.audit_path)
    if runtime_name == "langgraph":
        return LangGraphRutaDia(
            catalog=catalog,
            runtime=DirectOpenAIRuntime(settings),
            recorder=recorder,
            checkpointer=checkpointer,
        )
    return RutaDiaService(
        catalog=catalog,
        runtime=CrewAIRuntime(settings),
        recorder=recorder,
    )


def main() -> None:
    if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = _parser().parse_args()
    if args.command == "web":
        from .web import run_server

        run_server(args.port)
        return
    settings = Settings.from_env()
    catalog = KnowledgeCatalog(settings.route_path)

    if args.command == "validate":
        issues = catalog.validate()
        if issues:
            for issue in issues:
                print(f"ERROR [{issue.code}] {issue.detail}")
            raise SystemExit(1)
        print(
            f"OK · {len(catalog.route.stages)} etapas · "
            f"{len(catalog.route.tools)} fichas habilitadas"
        )
        return

    if args.command == "memory":
        with NotebookMemory(settings.memory_path) as memory:
            if args.action == "show":
                state = memory.load(ProjectState(notebook_id=args.notebook))
                print(json.dumps(state.model_dump(mode="json"), ensure_ascii=False, indent=2))
                return
            removed = memory.delete(args.notebook)
        settings.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(settings.checkpoint_path, check_same_thread=False) as connection:
            SqliteSaver(connection).delete_thread(args.notebook)
        print("Cuaderno eliminado." if removed else "El cuaderno no existía.")
        return

    runtime_name = args.runtime or settings.runtime
    if runtime_name not in {"langgraph", "crewai"}:
        raise ValueError("RUTA_DIA_RUNTIME debe ser 'langgraph' o 'crewai'")
    default_state = ProjectState(
        notebook_id=args.notebook,
        stage=args.stage,
        phase=args.phase,
        role=args.role,
    )
    with NotebookMemory(settings.memory_path) as memory:
        state = memory.load(default_state)
        checkpoint_connection = None
        checkpointer = None
        if runtime_name == "langgraph":
            settings.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
            checkpoint_connection = sqlite3.connect(
                settings.checkpoint_path, check_same_thread=False
            )
            checkpoint_connection.execute("PRAGMA journal_mode = WAL")
            checkpoint_connection.execute("PRAGMA busy_timeout = 5000")
            checkpointer = SqliteSaver(
                checkpoint_connection,
                serde=JsonPlusSerializer(allowed_msgpack_modules=[]),
            )
        try:
            service = _service(settings, catalog, runtime_name, checkpointer)
            if args.command == "chat":
                result = service.handle_turn(args.message, state)
                memory.save_exchange(args.message, result, state)
                print(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2))
                return

            print(
                f"Ruta DIA interactiva · runtime={runtime_name} · "
                f"cuaderno={state.notebook_id}. Escribe /salir para terminar."
            )
            if state.recent_turns:
                print(f"Memoria recuperada: {len(state.recent_turns)} intervenciones recientes.")
            while True:
                try:
                    message = input("Tú> ").strip()
                except (EOFError, KeyboardInterrupt):
                    print()
                    return
                if message.casefold() in {"/salir", "salir", "/exit", "exit"}:
                    return
                if not message:
                    continue
                result = service.handle_turn(message, state)
                print(f"Ruta DIA> {result.message}")
                print(
                    f"[{result.verification.verdict}; herramienta="
                    f"{result.handoff.active_tool or 'sin ficha'}; intentos={result.attempts}]"
                )
                state = memory.save_exchange(message, result, state)
        finally:
            if checkpoint_connection is not None:
                checkpoint_connection.close()


if __name__ == "__main__":
    main()
