"""Piloto comparativo real. Ejecutar con .venv/Scripts/python.exe desde prototipo."""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import importlib.metadata
import json
import os
import random
import secrets
import shutil
import socket
import statistics
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
LOCAL = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "QwenLocalTest"
MODELS = {
    "small": {
        "alias": "Qwen3.5-4B-Q4_K_M",
        "file": "Qwen3.5-4B.Q4_K_M.gguf",
        "sha256": "51eafbc127f35598c8f1d2ec58b2520d6126c7d1195c4eca26832e63a2939d39",
        "source": "https://huggingface.co/mradermacher/Qwen3.5-4B-GGUF",
    },
    "large": {
        "alias": "Qwen3.8-27B-Q4_K_M",
        "file": "Qwen3.8-27B.Q4_K_M.gguf",
        "sha256": "1dc0ce077ffb27a39f40081b66269f40719f922feea7e27c582caebd07f019ec",
        "source": "https://huggingface.co/mradermacher/Qwen3.8-27B-GGUF",
    },
}
HIDDEN = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def digest(path):
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(8 * 1024 * 1024):
            hasher.update(chunk)
    return hasher.hexdigest()


class MemoryStatus(ctypes.Structure):
    _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [
        (name, ctypes.c_ulonglong)
        for name in (
            "total",
            "avail",
            "total_page",
            "avail_page",
            "total_virtual",
            "avail_virtual",
            "ext",
        )
    ]


def memory():
    status = MemoryStatus()
    status.length = ctypes.sizeof(status)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))
    result = {
        "time": time.time(),
        "ram_percent": status.load,
        "available_ram_gib": status.avail / 2**30,
    }
    try:
        raw = (
            subprocess.check_output(
                [
                    "nvidia-smi",
                    "--query-gpu=memory.used,utilization.gpu",
                    "--format=csv,noheader,nounits",
                ],
                text=True,
                creationflags=HIDDEN,
                timeout=10,
            )
            .strip()
            .split(",")
        )
        result.update(gpu_used_mib=int(raw[0]), gpu_percent=int(raw[1]))
    except (OSError, ValueError, subprocess.SubprocessError):
        result["gpu_used_mib"] = None
    return result


def monitor(stop, path):
    with path.open("w", encoding="utf-8") as stream:
        while not stop.is_set():
            stream.write(json.dumps(memory()) + "\n")
            stream.flush()
            stop.wait(5)


def stop_process(process):
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def warmup(port, key):
    body = {
        "messages": [{"role": "user", "content": "Responde solo: listo"}],
        "max_tokens": 8,
        "temperature": 0.7,
        "chat_template_kwargs": {"enable_thinking": False},
        "cache_prompt": False,
    }
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}/v1/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
    )
    with urllib.request.urlopen(request, timeout=240) as response:
        return json.load(response)


def block(model, seed, case_ids, root, port, key, thinking=False):
    folder = root / f"{model}-seed-{seed}"
    folder.mkdir()
    spec = MODELS[model]
    args = [
        str(LOCAL / "runtime/llama-server.exe"),
        "-m",
        str(LOCAL / spec["file"]),
        "--alias",
        spec["alias"],
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--api-key-file",
        str(root / "session.key"),
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
        "on" if thinking else "off",
        "--no-reasoning-preserve",
        "--jinja",
    ]
    if thinking:
        args.extend(["--reasoning-budget", "1024"])
    metadata = {"model": model, "seed": seed, "command": args, "before": memory()}
    env = os.environ.copy()
    env.update(
        OTEL_SDK_DISABLED="true",
        CREWAI_TRACING_ENABLED="false",
        CREWAI_TELEMETRY_ENABLED="false",
        RUTA_DIA_EVAL_KEY=key,
        PYTHONUTF8="1",
        RUTA_DIA_THINKING="true" if thinking else "false",
    )
    stop = threading.Event()
    sampler = threading.Thread(target=monitor, args=(stop, folder / "memory.jsonl"), daemon=True)
    server = None
    with (folder / "server.log").open("w", encoding="utf-8") as log:
        try:
            print(f"START {model} seed={seed}", flush=True)
            started = time.perf_counter()
            server = subprocess.Popen(
                args,
                stdout=log,
                stderr=subprocess.STDOUT,
                cwd=LOCAL / "runtime",
                env=env,
                creationflags=HIDDEN,
            )
            save(folder / "process.json", {"server_pid": server.pid})
            sampler.start()
            while True:
                if server.poll() is not None:
                    raise RuntimeError(f"Server exited: {server.returncode}")
                try:
                    with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2):
                        break
                except (urllib.error.URLError, TimeoutError):
                    pass
                if time.perf_counter() - started > 420:
                    raise TimeoutError("Carga superior a 420 segundos")
                time.sleep(2)
            metadata["load_seconds"] = time.perf_counter() - started
            save(folder / "warmup.json", warmup(port, key))
            order = list(case_ids)
            random.Random(seed).shuffle(order)
            metadata["case_order"] = order
            save(folder / "block.json", metadata)
            for case_id in order:
                print(f"RUN {model} seed={seed} case={case_id}", flush=True)
                output = folder / case_id
                command = [
                    sys.executable,
                    "-m",
                    "ruta_dia_agents.evaluation",
                    "--case",
                    case_id,
                    "--model",
                    spec["alias"],
                    "--seed",
                    str(seed),
                    "--output",
                    str(output),
                    "--port",
                    str(port),
                ]
                started = time.perf_counter()
                with (folder / f"{case_id}.worker.log").open("w", encoding="utf-8") as worker_log:
                    worker = subprocess.Popen(
                        command,
                        stdout=worker_log,
                        stderr=subprocess.STDOUT,
                        cwd=PROJECT,
                        env=env,
                        creationflags=HIDDEN,
                    )
                    try:
                        worker.wait(timeout=600)
                    except subprocess.TimeoutExpired:
                        stop_process(worker)
                        output.mkdir(exist_ok=True)
                        save(
                            output / "result.json",
                            {
                                "case_id": case_id,
                                "model": spec["alias"],
                                "seed": seed,
                                "status": "timeout",
                                "mechanical_pass": False,
                                "seconds": time.perf_counter() - started,
                                "error": "Límite de 600 segundos por caso",
                                "review_status": "pending",
                            },
                        )
                        # No continuar sobre un servidor que podría seguir procesando la solicitud.
                        raise TimeoutError(
                            f"Caso {case_id} agotó el tiempo; bloque detenido"
                        ) from None
                    finally:
                        stop_process(worker)
                if not (output / "result.json").exists():
                    output.mkdir(exist_ok=True)
                    save(
                        output / "result.json",
                        {
                            "case_id": case_id,
                            "model": spec["alias"],
                            "seed": seed,
                            "status": "worker_error",
                            "mechanical_pass": False,
                            "seconds": time.perf_counter() - started,
                            "review_status": "pending",
                        },
                    )
                result = json.loads((output / "result.json").read_text(encoding="utf-8"))
                print(
                    f"DONE {case_id}: {result['status']}, {result['seconds']:.1f}s, "
                    f"mechanical={result['mechanical_pass']}",
                    flush=True,
                )
        except Exception as exc:
            metadata["error"] = f"{type(exc).__name__}: {exc}"
            print(metadata["error"], flush=True)
        finally:
            if server:
                stop_process(server)
            stop.set()
            if sampler.is_alive():
                sampler.join(timeout=15)
            metadata["after"] = memory()
            save(folder / "block.json", metadata)


def summarize(root, manifest):
    records = []
    for model, seed in manifest["blocks"]:
        for case_id in manifest["cases"]:
            path = root / f"{model}-seed-{seed}" / case_id / "result.json"
            if path.exists():
                record = json.loads(path.read_text(encoding="utf-8"))
            else:
                record = {
                    "case_id": case_id,
                    "model": MODELS[model]["alias"],
                    "seed": seed,
                    "status": "not_run",
                    "mechanical_pass": False,
                    "seconds": None,
                }
            records.append(record)
    save(root / "summary.json", records)
    lines = [
        "# Piloto comparativo local",
        "",
        "Criterios mecánicos y tiempos. La fidelidad requiere revisar las respuestas; "
        "un aprobado del Verificador no equivale a una validación independiente.",
        "",
        "| Modelo | Semilla | Caso | Estado | Segundos | Criterios mecánicos |",
        "|---|---:|---|---|---:|---|",
    ]
    for record in records:
        seconds = record["seconds"]
        duration = f"{seconds:.2f}" if seconds is not None else "—"
        lines.append(
            f"| {record['model']} | {record['seed']} | {record['case_id']} | "
            f"{record['status']} | {duration} | {record['mechanical_pass']} |"
        )
    lines += ["", "## Medianas de turnos completos F01", ""]
    for spec in MODELS.values():
        values = [
            r["seconds"]
            for r in records
            if r["model"] == spec["alias"] and r["case_id"] == "F01" and r["status"] == "ok"
        ]
        if values:
            lines.append(f"- {spec['alias']}: {statistics.median(values):.2f} s (n={len(values)}).")
    lines += [
        "",
        "Dos repeticiones por caso no permiten generalizar exactitud ni carga cognitiva.",
        "Errores y casos no ejecutados permanecen en el denominador del resumen.",
    ]
    (root / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", nargs="+", choices=list(MODELS), default=["small", "large"])
    parser.add_argument("--seeds", nargs="+", type=int, default=[42, 43])
    parser.add_argument("--cases", nargs="+", default=["F01", "G01", "V01", "V02"])
    parser.add_argument("--port", type=int, default=18083)
    parser.add_argument("--thinking", action="store_true")
    args = parser.parse_args()
    with socket.socket() as check:
        check.bind(("127.0.0.1", args.port))
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    root = PROJECT / "data" / "evaluations" / stamp
    root.mkdir(parents=True, exist_ok=False)
    manifest = {
        "created_utc": stamp,
        "models": {},
        "cases": args.cases,
        "seeds": args.seeds,
        "packages": {
            name: importlib.metadata.version(name)
            for name in ("crewai", "pydantic", "openai", "httpx")
        },
        "files": {},
        "blocks": [],
    }
    for name in args.models:
        spec = MODELS[name]
        print(f"VERIFY {name}", flush=True)
        actual = digest(LOCAL / spec["file"])
        if actual != spec["sha256"]:
            raise ValueError(f"SHA256 incorrecto para {name}")
        manifest["models"][name] = {**spec, "verified_sha256": actual}
    for base in ("src", "knowledge", "evaluation", "scripts"):
        for path in (PROJECT / base).rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts:
                relative = path.relative_to(PROJECT)
                manifest["files"][str(relative)] = digest(path)
                destination = root / "frozen" / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, destination)
    for index, seed in enumerate(args.seeds):
        order = args.models if index % 2 == 0 else list(reversed(args.models))
        manifest["blocks"].extend((model, seed) for model in order)
    save(root / "manifest.json", manifest)
    key = secrets.token_urlsafe(24)
    (root / "session.key").write_text(key, encoding="utf-8")
    print(f"OUTPUT {root}", flush=True)
    try:
        for model, seed in manifest["blocks"]:
            block(model, seed, args.cases, root, args.port, key, args.thinking)
            summarize(root, manifest)
    finally:
        (root / "session.key").unlink(missing_ok=True)
        summarize(root, manifest)
    print(f"COMPLETE {root / 'summary.md'}", flush=True)


if __name__ == "__main__":
    main()
