"""Rutas y procesos locales de Hilo, iguales para los scripts de Windows y de Linux.

Solo usa la biblioteca estándar: el instalador del modelo debe poder ejecutarse sin cargar
el paquete `ruta_dia_agents`.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
from collections.abc import Mapping
from pathlib import Path

WINDOWS = os.name == "nt"
LLAMA_BUILD = "b11146"
MODEL_FILE = "Qwen3.5-4B.Q4_K_M.gguf"
# Motores de llama.cpp para Linux, del más rápido al más lento. El instalador elige uno
# según el equipo; el arranque usa el primero que encuentre instalado.
LINUX_BACKENDS = ("cuda", "vulkan", "cpu")
BACKEND_FILE = "llama-backend.txt"  # último motor que instaló el usuario en Linux


def local_dir(
    name: str, *, env: Mapping[str, str] | None = None, windows: bool | None = None,
) -> Path:
    """Carpeta local de este sistema, fuera de cualquier carpeta sincronizada o compartida.

    Windows: `%LOCALAPPDATA%\\<name>`. Linux: `~/.local/share/<name>` (o `XDG_DATA_HOME`).
    """
    env = os.environ if env is None else env
    if WINDOWS if windows is None else windows:
        return Path(env["LOCALAPPDATA"]) / name
    return Path(env.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / name


def runtime_dir(root: Path, backend: str = "") -> Path:
    """Carpeta del motor. En Windows hay uno solo (CUDA); en Linux, uno por backend."""
    suffix = f"-linux-{backend}" if backend else ""
    return root / f"runtime-{LLAMA_BUILD}{suffix}"


def find_server(root: Path, *, windows: bool | None = None) -> Path | None:
    """Ejecutable de llama-server instalado, o None si falta.

    En Linux no se asume en qué subcarpeta lo deja el paquete oficial: se busca. Si hay
    varios motores instalados manda `RUTA_DIA_LLAMA_BACKEND`; si no, el último que eligió
    el instalador, para que reinstalar con otro motor tenga efecto.
    """
    if WINDOWS if windows is None else windows:
        server = runtime_dir(root) / "llama-server.exe"
        return server if server.is_file() else None
    forced = os.environ.get("RUTA_DIA_LLAMA_BACKEND", "").strip().lower()
    chosen = root / BACKEND_FILE
    last = chosen.read_text(encoding="utf-8").strip() if chosen.is_file() else ""
    order = (forced,) if forced else (last, *LINUX_BACKENDS) if last else LINUX_BACKENDS
    for backend in order:
        folder = runtime_dir(root, backend)
        if folder.is_dir():
            found = sorted(path for path in folder.rglob("llama-server") if path.is_file())
            if found:
                return found[0]
    return None


def server_env(server: Path) -> dict[str, str]:
    """Entorno para llama-server en Linux: sus bibliotecas (.so) viajan con el paquete."""
    runtime = next(path for path in server.parents if path.name.startswith("runtime-"))
    folders = sorted({str(path.parent) for path in runtime.rglob("*.so*")})
    env = dict(os.environ)
    previous = env.get("LD_LIBRARY_PATH", "")
    env["LD_LIBRARY_PATH"] = os.pathsep.join([*folders, *([previous] if previous else [])])
    return env


def start_ticks(stat: str) -> str:
    """Momento de inicio del proceso: campo 22 de /proc/<pid>/stat.

    El nombre del proceso va entre paréntesis y puede traer espacios o más paréntesis, así
    que se cuenta desde el último.
    """
    return stat.rsplit(")", 1)[1].split()[19]


def posix_identity(pid: int, proc: Path = Path("/proc")) -> dict | None:
    folder = proc / str(int(pid))
    try:
        return {
            "ProcessId": int(pid),
            "CreationDate": start_ticks((folder / "stat").read_text(encoding="utf-8")),
            "ExecutablePath": os.readlink(folder / "exe"),
        }
    except (OSError, IndexError):
        return None  # no existe, ya terminó o es de otro usuario


def process_identity(pid: int) -> dict | None:
    """PID, inicio y ejecutable: distingue al proceso propio de otro que reutilice el PID."""
    if not WINDOWS:
        return posix_identity(pid)
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


def stop_process(pid: int) -> None:
    if not WINDOWS:
        os.kill(int(pid), signal.SIGTERM)
        return
    subprocess.run(
        ["powershell.exe", "-NoProfile", "-Command", f"Stop-Process -Id {int(pid)}"],
        check=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )


def detached() -> dict:
    """Argumentos de Popen para un proceso sin ventana que sobrevive a la terminal."""
    if WINDOWS:
        return {"creationflags": subprocess.CREATE_NO_WINDOW}
    return {"start_new_session": True}
