"""Descarga Qwen3.5-4B y llama.cpp para la interfaz local de Ruta DIA.

Windows instala el motor con CUDA. Linux elige entre CUDA, Vulkan y solo CPU según el
equipo; `--backend` permite forzar uno.
"""

from __future__ import annotations

import argparse
import ctypes.util
import hashlib
import os
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

from local_runtime import (
    BACKEND_FILE,
    LINUX_BACKENDS,
    LLAMA_BUILD,
    MODEL_FILE,
    WINDOWS,
    find_server,
    local_dir,
    runtime_dir,
)

ROOT = local_dir("QwenLocalTest")
RELEASE = f"https://github.com/ggml-org/llama.cpp/releases/download/{LLAMA_BUILD}/"
MODEL = (
    MODEL_FILE,
    "https://huggingface.co/mradermacher/Qwen3.5-4B-GGUF/resolve/main/"
    "Qwen3.5-4B.Q4_K_M.gguf",
    2_708_804_800,
    "51eafbc127f35598c8f1d2ec58b2520d6126c7d1195c4eca26832e63a2939d39",
)
LLAMA = (
    "llama-b11146-cuda12.zip",
    RELEASE + "llama-b11146-bin-win-cuda-12.4-x64.zip",
    253_869_799,
    "3c806a6ceccc3dae1c743ceb1a1fb2cce5b76f40bfbd4c6b7b8afb6ef45a5807",
)
CUDA = (
    "cudart.zip",
    "https://github.com/ggml-org/llama.cpp/releases/download/b10809/"
    "cudart-llama-bin-win-cuda-12.4-x64.zip",
    391_443_627,
    "8c79a9b226de4b3cacfd1f83d24f962d0773be79f1e7b75c6af4ded7e32ae1d6",
)
RUNTIME_FILES = (
    "llama-server.exe",
    "llama-server-impl.dll",
    "ggml-cuda.dll",
    "cublas64_12.dll",
    "cublasLt64_12.dll",
    "cudart64_12.dll",
)


def _linux(name: str, size: int, digest: str) -> tuple[str, str, int, str]:
    return (name, RELEASE + name, size, digest)


# Paquetes oficiales de la misma compilación que usa Windows. Tamaño y SHA-256 son los que
# publica GitHub para cada archivo de la versión b11146.
LINUX_ARCHIVES = {
    "cuda": (
        _linux(
            "llama-b11146-bin-ubuntu-cuda-12.8-x64.tar.gz", 168_920_581,
            "c2ab9e19838513ff69d1af8d999ad717dd3c7ee4714ac04c7ed5ab9077c50e4e",
        ),
        _linux(
            "cudart-llama-b11146-bin-ubuntu-cuda-12.8-x64.tar.gz", 594_373_356,
            "1466daea60aad1144819e151b2bae19d54556cf1da6c129c4f55a5ded2637c25",
        ),
    ),
    "vulkan": (
        _linux(
            "llama-b11146-bin-ubuntu-vulkan-x64.tar.gz", 30_598_492,
            "d3ce40fce7403cc93bcf5718fc46c6efb61ed9709f8e5d9f10c86bf0e30e8fb3",
        ),
    ),
    "cpu": (
        _linux(
            "llama-b11146-bin-ubuntu-x64.tar.gz", 16_998_357,
            "c150306eb16b5ab696f76a8bdf810c35fd98a24e82158742e6fa28f420ff8410",
        ),
    ),
}
# El paquete con CUDA 12.8 necesita el controlador de NVIDIA de la serie 570 o posterior.
CUDA_MIN_DRIVER = (570, 0)


def shared_models() -> Path | None:
    """Carpeta `modelos` junto al repositorio, o la que indique RUTA_DIA_SHARED_MODELS.

    En un equipo con arranque dual, los dos sistemas ven esa carpeta: lo que uno ya
    descargó, el otro lo copia en vez de bajarlo otra vez.
    """
    custom = os.environ.get("RUTA_DIA_SHARED_MODELS")
    if custom:
        return Path(custom).expanduser()
    parents = Path(__file__).resolve().parents  # scripts, prototipo, repositorio, carpeta
    return parents[3] / "modelos" if len(parents) > 3 else None


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verified(path: Path, size: int, expected_hash: str) -> bool:
    return path.is_file() and path.stat().st_size == size and sha256(path) == expected_hash


def copy_shared(item: tuple[str, str, int, str], destination: Path) -> bool:
    """Trae el archivo de la carpeta compartida si está completo y su SHA-256 coincide."""
    name, _, size, expected_hash = item
    folder = shared_models()
    source = folder / name if folder else None
    if not source or not source.is_file() or source.stat().st_size != size:
        return False
    print(f"Copiando {name} desde {folder}", flush=True)
    part = destination.with_name(destination.name + ".copia")
    shutil.copyfile(source, part)
    if not verified(part, size, expected_hash):
        part.unlink()
        print("  La copia compartida no coincide con el SHA-256 esperado; se descarga.", flush=True)
        return False
    part.replace(destination)
    return True


def download(item: tuple[str, str, int, str]) -> Path:
    name, url, size, expected_hash = item
    destination = ROOT / name
    if verified(destination, size, expected_hash):
        print(f"Ya está descargado: {name}", flush=True)
        return destination
    if destination.exists():
        raise RuntimeError(
            f"El archivo existente no coincide con la descarga esperada: {destination}"
        )
    if copy_shared(item, destination):
        return destination

    part = ROOT / f"{name}.part"
    for attempt in range(1, 6):
        offset = part.stat().st_size if part.exists() else 0
        if offset >= size:
            if verified(part, size, expected_hash):
                part.replace(destination)
                return destination
            part.unlink()
            offset = 0
        headers = {"User-Agent": "RutaDIA-local-installer/1.0"}
        if offset:
            headers["Range"] = f"bytes={offset}-"
        print(f"Descargando {name}: {offset / 1e9:.2f}/{size / 1e9:.2f} GB", flush=True)
        try:
            request = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(request, timeout=120) as response:
                if offset and response.status != 206:
                    part.unlink()
                    continue
                if response.status not in (200, 206):
                    raise RuntimeError(f"Respuesta HTTP inesperada: {response.status}")
                last_report = time.monotonic()
                with part.open("ab" if offset else "wb") as output:
                    while chunk := response.read(4 * 1024 * 1024):
                        output.write(chunk)
                        offset += len(chunk)
                        if time.monotonic() - last_report >= 15:
                            print(f"  {offset / 1e9:.2f}/{size / 1e9:.2f} GB", flush=True)
                            last_report = time.monotonic()
            if verified(part, size, expected_hash):
                part.replace(destination)
                print(f"Descarga verificada: {name}", flush=True)
                return destination
            if part.stat().st_size >= size:
                part.unlink()
                raise RuntimeError(f"La descarga de {name} no coincide con el SHA-256 esperado")
        except (TimeoutError, urllib.error.URLError) as exc:
            print(f"Intento {attempt}/5 interrumpido: {exc}", flush=True)
        if attempt < 5:
            time.sleep(2)
    raise RuntimeError(f"No se pudo descargar {name}; vuelve a ejecutar este comando para reanudar")


def nvidia_driver() -> tuple[int, int] | None:
    """Versión del controlador de NVIDIA en uso, o None si no hay uno funcionando."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=15, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    match = re.match(r"\s*(\d+)\.(\d+)", result.stdout)
    return (int(match[1]), int(match[2])) if result.returncode == 0 and match else None


def default_backend(driver: tuple[int, int] | None, vulkan: bool) -> tuple[str, str]:
    """Motor más rápido que este equipo puede usar, y el motivo en una frase."""
    if driver and driver >= CUDA_MIN_DRIVER:
        return "cuda", f"controlador de NVIDIA {driver[0]}.{driver[1]}"
    if vulkan:
        reason = "hay Vulkan"
        if driver:
            reason += f"; el controlador de NVIDIA {driver[0]}.{driver[1]} es anterior al 570"
        return "vulkan", reason
    return "cpu", "no se encontró controlador de NVIDIA ni Vulkan"


def install_windows_runtime() -> None:
    runtime = runtime_dir(ROOT)
    if not all((runtime / name).is_file() for name in RUNTIME_FILES):
        runtime.mkdir(exist_ok=True)
        for archive in (download(LLAMA), download(CUDA)):
            with zipfile.ZipFile(archive) as contents:
                contents.extractall(runtime)
    missing = [name for name in RUNTIME_FILES if not (runtime / name).is_file()]
    if missing:
        raise RuntimeError(f"Faltan archivos de llama.cpp después de extraer: {', '.join(missing)}")
    print("Qwen y llama.cpp están listos. Ejecuta .\\scripts\\start_interface.ps1", flush=True)


def extract_linux(archives: list[Path], runtime: Path) -> Path:
    """Extrae los paquetes y devuelve llama-server, esté en la subcarpeta que esté."""
    runtime.mkdir(parents=True, exist_ok=True)
    for archive in archives:
        with tarfile.open(archive) as contents:
            contents.extractall(runtime, filter="data")
    servers = sorted(path for path in runtime.rglob("llama-server") if path.is_file())
    if not servers:
        raise RuntimeError(f"El paquete no trae llama-server: {runtime}")
    servers[0].chmod(0o755)
    return servers[0]


def install_linux_runtime(backend: str | None) -> None:
    if platform.machine().lower() not in ("x86_64", "amd64"):
        raise RuntimeError(
            f"Este instalador solo cubre Linux x86-64; este equipo es {platform.machine()}."
        )
    if backend:
        reason = "elegido con --backend"
    else:
        backend, reason = default_backend(
            nvidia_driver(), bool(ctypes.util.find_library("vulkan")),
        )
    print(f"Motor de llama.cpp: {backend} ({reason})", flush=True)
    runtime = runtime_dir(ROOT, backend)
    servers = sorted(runtime.rglob("llama-server")) if runtime.is_dir() else []
    if not servers:
        extract_linux([download(item) for item in LINUX_ARCHIVES[backend]], runtime)
    (ROOT / BACKEND_FILE).write_text(backend, encoding="utf-8")
    if find_server(ROOT) is None:
        raise RuntimeError(f"No se encontró llama-server después de extraer en {runtime}")
    if backend == "cpu":
        print("Sin GPU, cada respuesta puede tardar varios minutos.", flush=True)
    print(
        "Qwen y llama.cpp están listos. Ejecuta: bash scripts/start_interface.sh\n"
        "Si el modelo no arranca, prueba otro motor: "
        "python scripts/install_local_model.py --backend vulkan (o cpu)",
        flush=True,
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--backend", choices=LINUX_BACKENDS,
        help="Solo Linux: motor de llama.cpp. Sin indicarlo, se elige según el equipo.",
    )
    args = parser.parse_args(argv)
    ROOT.mkdir(parents=True, exist_ok=True)
    print(f"Instalando en {ROOT}", flush=True)
    download(MODEL)
    if WINDOWS:
        install_windows_runtime()
    else:
        install_linux_runtime(args.backend)


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, zipfile.BadZipFile, tarfile.TarError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
