"""Inicia, consulta o detiene el servidor Qwen local configurado para este prototipo."""

import argparse
import json
import os
import socket
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from ruta_dia_agents.config import Settings

LOCAL = Path(os.environ["LOCALAPPDATA"]) / "QwenLocalTest"
RECORD = LOCAL / "ruta-dia-server.json"
KEY = LOCAL / "ruta-dia-server.key"


def identity(pid):
    command = (
        f"Get-CimInstance Win32_Process -Filter 'ProcessId={int(pid)}' | "
        "Select-Object ProcessId,CreationDate,ExecutablePath | ConvertTo-Json -Compress"
    )
    raw = subprocess.check_output(
        ["powershell.exe", "-NoProfile", "-Command", command],
        text=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
    ).strip()
    return json.loads(raw) if raw else None


def owned_process():
    if RECORD.exists():
        recorded = json.loads(RECORD.read_text(encoding="utf-8"))
        if identity(recorded["ProcessId"]) == recorded:
            return recorded
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["start", "status", "stop"])
    action = parser.parse_args().action
    current = owned_process()
    if action == "status":
        print("Servidor activo" if current else "Servidor detenido")
        return
    if action == "stop":
        if current:
            subprocess.run(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-Command",
                    f"Stop-Process -Id {int(current['ProcessId'])}",
                ],
                check=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        RECORD.unlink(missing_ok=True)
        KEY.unlink(missing_ok=True)
        print("Servidor detenido")
        return
    if current:
        print("El servidor ya está iniciado")
        return
    settings = Settings.from_env()
    url = urllib.parse.urlparse(settings.base_url or "")
    if url.scheme != "http" or url.hostname != "127.0.0.1" or not url.port:
        raise ValueError("Configura RUTA_DIA_BASE_URL=http://127.0.0.1:18083/v1")
    if settings.model != "Qwen3.5-4B-Q4_K_M" or not settings.api_key:
        raise ValueError("Configura el alias Qwen3.5-4B-Q4_K_M y RUTA_DIA_API_KEY en .env")
    model = LOCAL / "Qwen3.5-4B.Q4_K_M.gguf"
    server = LOCAL / "runtime/llama-server.exe"
    missing = [path for path in (model, server) if not path.is_file()]
    if missing:
        paths = "\n".join(f"  - {path}" for path in missing)
        raise FileNotFoundError(
            "No se encontraron los archivos necesarios para iniciar Qwen:\n"
            f"{paths}\n"
            f"LOCALAPPDATA en esta sesion: {os.environ['LOCALAPPDATA']}"
        )
    with socket.socket() as check:
        check.bind(("127.0.0.1", url.port))
    KEY.write_text(settings.api_key, encoding="utf-8")
    args = [
        str(server),
        "-m",
        str(model),
        "--alias",
        settings.model,
        "--host",
        "127.0.0.1",
        "--port",
        str(url.port),
        "--api-key-file",
        str(KEY),
        "-c",
        "8192",
        "-np",
        "1",
        "-b",
        "128",
        "-ub",
        "128",
        "-t",
        "6",
        "--fit",
        "on",
        "--fit-target",
        "1024",
        "--cache-ram",
        "0",
        "--reasoning",
        "on" if settings.thinking else "off",
        "--no-reasoning-preserve",
        "--jinja",
    ]
    if settings.thinking:
        args.extend(["--reasoning-budget", "1024"])
    with (LOCAL / "ruta-dia-server.log").open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            args,
            stdout=log,
            stderr=subprocess.STDOUT,
            cwd=server.parent,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    try:
        record = identity(process.pid)
        if record is None:
            raise RuntimeError("El servidor terminó al iniciar; revisa ruta-dia-server.log")
        RECORD.write_text(json.dumps(record), encoding="utf-8")
        started = time.monotonic()
        while time.monotonic() - started < 120:
            if process.poll() is not None:
                raise RuntimeError("El servidor terminó; revisa ruta-dia-server.log")
            try:
                request = urllib.request.Request(
                    f"http://127.0.0.1:{url.port}/v1/models",
                    headers={"Authorization": f"Bearer {settings.api_key}"},
                )
                with urllib.request.urlopen(request, timeout=2) as response:
                    models = json.load(response)
                if any(m["id"] == settings.model for m in models["data"]):
                    print(f"Qwen3.5-4B listo en {settings.base_url}")
                    return
            except (urllib.error.URLError, TimeoutError):
                pass
            time.sleep(1)
        raise TimeoutError("El modelo no estuvo disponible en 120 segundos")
    except BaseException:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=15)
        RECORD.unlink(missing_ok=True)
        KEY.unlink(missing_ok=True)
        raise


if __name__ == "__main__":
    main()
