"""Inicia o detiene la interfaz local de Hilo en Linux.

Hace lo mismo que `start_interface.ps1` y `stop_interface.ps1` en Windows. Se usa a través
de `start_interface.sh` y `stop_interface.sh`, que eligen el Python del entorno.
"""

from __future__ import annotations

import argparse
import json
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

from local_runtime import (
    MODEL_FILE,
    WINDOWS,
    detached,
    find_server,
    local_dir,
    process_identity,
    stop_process,
)

SCRIPTS = Path(__file__).resolve().parent
PROJECT = SCRIPTS.parent
APP_ID = "ruta-dia-local"


def app_status(url: str) -> dict | None:
    """Respuesta de /api/status si en ese puerto contesta Hilo; None en cualquier otro caso."""
    try:
        with urllib.request.urlopen(f"{url}/api/status", timeout=5) as response:
            status = json.load(response)
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        return None
    return status if isinstance(status, dict) and status.get("app_id") == APP_ID else None


def run_script(name: str, *args: str) -> None:
    subprocess.run([sys.executable, str(SCRIPTS / name), *args], cwd=PROJECT, check=True)


def ensure_model() -> None:
    models = local_dir("QwenLocalTest")
    if not (models / MODEL_FILE).is_file() or find_server(models) is None:
        print("Falta Qwen o llama.cpp en este equipo. Descargando los archivos locales...")
        run_script("install_local_model.py")
    run_script("local_model.py", "start")


def start(port: int, browser: bool) -> None:
    url = f"http://127.0.0.1:{port}"
    data = local_dir("RutaDIA")
    record = data / f"interface-{port}.json"
    existing = app_status(url)
    if existing:
        if not existing.get("available"):
            ensure_model()
        print(f"La interfaz ya está disponible: {url}")
    else:
        with socket.socket() as check:
            if check.connect_ex(("127.0.0.1", port)) == 0:
                raise RuntimeError(
                    f"El puerto {port} está ocupado por otro servicio. Usa --port con otro número."
                )
        ensure_model()
        if not (PROJECT / "frontend" / "dist" / "index.html").is_file():
            raise RuntimeError(
                "Falta la interfaz construida. Ejecuta: bash scripts/build_frontend.sh"
            )
        data.mkdir(parents=True, exist_ok=True)
        logs = [data / f"interface-{port}.{kind}.log" for kind in ("out", "err")]
        with logs[0].open("w", encoding="utf-8") as out, logs[1].open("w", encoding="utf-8") as err:
            process = subprocess.Popen(
                [sys.executable, "-m", "ruta_dia_agents", "web", "--port", str(port)],
                cwd=PROJECT, stdout=out, stderr=err, **detached(),
            )
        for _ in range(60):
            if process.poll() is not None:
                raise RuntimeError(f"La interfaz terminó al iniciar. Revisa {logs[1]}")
            if app_status(url):
                break
            time.sleep(0.5)
        else:
            process.terminate()
            raise RuntimeError(f"La interfaz no respondió. Revisa {logs[1]}")
        record.write_text(json.dumps(process_identity(process.pid)), encoding="utf-8")
        print(f"Hilo listo: {url}")
    if browser:
        webbrowser.open(url)


def stop(port: int) -> None:
    record = local_dir("RutaDIA") / f"interface-{port}.json"
    if not record.is_file():
        print("No hay una interfaz registrada.")
        return
    recorded = json.loads(record.read_text(encoding="utf-8"))
    # Solo se detiene si sigue siendo el mismo proceso, no otro que reutilice el PID.
    if recorded and process_identity(recorded["ProcessId"]) == recorded:
        stop_process(recorded["ProcessId"])
        print("Interfaz detenida.")
    else:
        print("La interfaz registrada ya estaba detenida.")
    record.unlink()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["start", "stop"])
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args(argv)
    if WINDOWS:
        raise SystemExit("En Windows usa scripts\\start_interface.ps1 y stop_interface.ps1.")
    if args.action == "start":
        start(args.port, not args.no_browser)
    else:
        stop(args.port)


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
