"""Descarga Qwen3.5-4B y llama.cpp para la interfaz local de Ruta DIA."""

from __future__ import annotations

import hashlib
import os
import sys
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(os.environ["LOCALAPPDATA"]) / "QwenLocalTest"
MODEL = (
    "Qwen3.5-4B.Q4_K_M.gguf",
    "https://huggingface.co/mradermacher/Qwen3.5-4B-GGUF/resolve/main/"
    "Qwen3.5-4B.Q4_K_M.gguf",
    2_708_804_800,
    "51eafbc127f35598c8f1d2ec58b2520d6126c7d1195c4eca26832e63a2939d39",
)
LLAMA = (
    "llama.zip",
    "https://github.com/ggml-org/llama.cpp/releases/download/b10809/"
    "llama-b10809-bin-win-cuda-12.4-x64.zip",
    253_938_543,
    "c77bfcd9ed8d91e8721a2d6a290b907fddd4fa5412a47b21c6fa1709116b85f9",
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


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verified(path: Path, size: int, expected_hash: str) -> bool:
    return path.is_file() and path.stat().st_size == size and sha256(path) == expected_hash


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


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    print(f"Instalando en {ROOT}", flush=True)
    download(MODEL)
    runtime = ROOT / "runtime"
    if not all((runtime / name).is_file() for name in RUNTIME_FILES):
        runtime.mkdir(exist_ok=True)
        for archive in (download(LLAMA), download(CUDA)):
            with zipfile.ZipFile(archive) as contents:
                contents.extractall(runtime)
    missing = [name for name in RUNTIME_FILES if not (runtime / name).is_file()]
    if missing:
        raise RuntimeError(f"Faltan archivos de llama.cpp después de extraer: {', '.join(missing)}")
    print("Qwen y llama.cpp están listos. Ejecuta .\\scripts\\start_interface.ps1", flush=True)


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, zipfile.BadZipFile) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
