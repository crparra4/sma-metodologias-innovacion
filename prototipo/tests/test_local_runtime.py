"""Soporte de Linux en los scripts locales. Estas pruebas corren en cualquier sistema:
no arrancan llama.cpp ni descargan nada."""

import hashlib
import io
import sys
import tarfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import install_local_model as installer  # noqa: E402
import local_runtime  # noqa: E402
from local_runtime import (  # noqa: E402
    BACKEND_FILE,
    find_server,
    local_dir,
    posix_identity,
    runtime_dir,
    server_env,
    start_ticks,
)


def touch(path: Path, content: bytes = b"x") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def test_each_system_keeps_local_files_in_its_own_place(tmp_path):
    windows = local_dir("RutaDIA", env={"LOCALAPPDATA": str(tmp_path)}, windows=True)
    assert windows == tmp_path / "RutaDIA"
    custom = local_dir("RutaDIA", env={"XDG_DATA_HOME": str(tmp_path / "xdg")}, windows=False)
    assert custom == tmp_path / "xdg" / "RutaDIA"
    # En Linux se ignora LOCALAPPDATA y se usa la carpeta de datos del usuario.
    default = local_dir("RutaDIA", env={"LOCALAPPDATA": str(tmp_path)}, windows=False)
    assert default == Path.home() / ".local" / "share" / "RutaDIA"


def test_windows_server_has_a_fixed_place(tmp_path):
    assert find_server(tmp_path, windows=True) is None
    server = touch(runtime_dir(tmp_path) / "llama-server.exe")
    assert find_server(tmp_path, windows=True) == server


def test_linux_server_is_found_wherever_the_package_puts_it(tmp_path, monkeypatch):
    monkeypatch.delenv("RUTA_DIA_LLAMA_BACKEND", raising=False)
    assert find_server(tmp_path, windows=False) is None
    cpu = touch(runtime_dir(tmp_path, "cpu") / "llama-b11146" / "llama-server")
    vulkan = touch(runtime_dir(tmp_path, "vulkan") / "build" / "bin" / "llama-server")
    # sin más datos, gana el motor más rápido instalado
    assert find_server(tmp_path, windows=False) == vulkan
    # reinstalar con otro motor debe tener efecto
    (tmp_path / BACKEND_FILE).write_text("cpu\n", encoding="utf-8")
    assert find_server(tmp_path, windows=False) == cpu
    # la variable de entorno manda sobre todo lo demás
    monkeypatch.setenv("RUTA_DIA_LLAMA_BACKEND", "vulkan")
    assert find_server(tmp_path, windows=False) == vulkan
    monkeypatch.setenv("RUTA_DIA_LLAMA_BACKEND", "cuda")
    assert find_server(tmp_path, windows=False) is None


def test_server_env_points_to_the_bundled_libraries(tmp_path, monkeypatch):
    runtime = runtime_dir(tmp_path, "cuda")
    server = touch(runtime / "llama-b11146" / "llama-server")
    touch(runtime / "llama-b11146" / "libllama.so")
    touch(runtime / "cudart" / "libcublas.so.12")
    monkeypatch.setenv("LD_LIBRARY_PATH", "/opt/previa")
    folders = server_env(server)["LD_LIBRARY_PATH"].split(local_runtime.os.pathsep)
    assert folders == [str(runtime / "cudart"), str(runtime / "llama-b11146"), "/opt/previa"]
    monkeypatch.delenv("LD_LIBRARY_PATH")
    assert not server_env(server)["LD_LIBRARY_PATH"].endswith(local_runtime.os.pathsep)


def test_start_time_survives_odd_process_names():
    tail = " ".join(["S", "1", *["0"] * 17, "987654", "0", "0"])
    assert start_ticks(f"4242 (llama-server) {tail}") == "987654"
    assert start_ticks(f"4242 (mi (raro) proceso) {tail}") == "987654"


def test_a_missing_process_has_no_identity(tmp_path):
    assert posix_identity(4242, proc=tmp_path) is None
    touch(tmp_path / "4242" / "stat", b"4242 (zombi) Z 1")  # sin campos suficientes ni exe
    assert posix_identity(4242, proc=tmp_path) is None


@pytest.mark.parametrize(("driver", "vulkan", "expected"), [
    ((580, 65), True, "cuda"),
    ((570, 0), False, "cuda"),
    ((550, 120), True, "vulkan"),   # controlador viejo para CUDA 12.8
    (None, True, "vulkan"),
    ((550, 120), False, "cpu"),
    (None, False, "cpu"),
])
def test_backend_follows_what_the_machine_has(driver, vulkan, expected):
    backend, reason = installer.default_backend(driver, vulkan)
    assert backend == expected and reason


def test_linux_packages_are_pinned_to_the_same_build_as_windows():
    assert set(installer.LINUX_ARCHIVES) == set(local_runtime.LINUX_BACKENDS)
    for archives in installer.LINUX_ARCHIVES.values():
        for name, url, size, digest in archives:
            assert url == installer.RELEASE + name
            assert f"-{local_runtime.LLAMA_BUILD}-bin-ubuntu-" in name
            assert name.endswith("-x64.tar.gz")
            assert size > 0 and len(digest) == 64 and int(digest, 16) >= 0


def item_for(content: bytes, name: str = "modelo.gguf"):
    return (name, "https://ejemplo.invalid/" + name, len(content),
            hashlib.sha256(content).hexdigest())


def test_a_verified_shared_copy_replaces_the_download(tmp_path, monkeypatch):
    shared, local = tmp_path / "modelos", tmp_path / "local"
    local.mkdir()
    monkeypatch.setenv("RUTA_DIA_SHARED_MODELS", str(shared))
    monkeypatch.setattr(installer, "ROOT", local)
    monkeypatch.setattr(installer.urllib.request, "urlopen", lambda *a, **k: pytest.fail("red"))
    content = b"pesos del modelo"
    touch(shared / "modelo.gguf", content)
    assert installer.download(item_for(content)) == local / "modelo.gguf"
    assert (local / "modelo.gguf").read_bytes() == content


def test_a_shared_copy_that_does_not_match_is_not_used(tmp_path, monkeypatch):
    shared, local = tmp_path / "modelos", tmp_path / "local"
    local.mkdir()
    monkeypatch.setenv("RUTA_DIA_SHARED_MODELS", str(shared))
    expected = item_for(b"pesos del modelo")
    # mismo tamaño, otro contenido: se copia, falla la verificación y no queda nada
    touch(shared / "modelo.gguf", b"PESOS DEL MODELO")
    assert not installer.copy_shared(expected, local / "modelo.gguf")
    assert list(local.iterdir()) == []
    # otro tamaño: ni se intenta
    touch(shared / "modelo.gguf", b"corto")
    assert not installer.copy_shared(expected, local / "modelo.gguf")
    # sin carpeta compartida
    monkeypatch.setenv("RUTA_DIA_SHARED_MODELS", str(tmp_path / "no-existe"))
    assert not installer.copy_shared(expected, local / "modelo.gguf")


def packed(tmp_path: Path, name: str, files: dict[str, bytes]) -> Path:
    archive = tmp_path / name
    with tarfile.open(archive, "w:gz") as contents:
        for path, data in files.items():
            info = tarfile.TarInfo(path)
            info.size, info.mode = len(data), 0o755
            contents.addfile(info, io.BytesIO(data))
    return archive


def test_linux_packages_are_extracted_into_one_runtime(tmp_path):
    engine = packed(tmp_path, "llama.tar.gz", {
        "llama-b11146/llama-server": b"binario", "llama-b11146/libllama.so": b"so"})
    cuda = packed(tmp_path, "cudart.tar.gz", {"libcublas.so.12": b"so"})
    runtime = runtime_dir(tmp_path, "cuda")
    server = installer.extract_linux([engine, cuda], runtime)
    assert server == runtime / "llama-b11146" / "llama-server"
    assert (runtime / "libcublas.so.12").is_file()
    assert find_server(tmp_path, windows=False) == server


def test_a_package_without_the_server_is_an_error(tmp_path):
    empty = packed(tmp_path, "otro.tar.gz", {"llama-b11146/llama-cli": b"binario"})
    with pytest.raises(RuntimeError, match="llama-server"):
        installer.extract_linux([empty], runtime_dir(tmp_path, "cpu"))


def test_memory_stays_in_the_local_folder(tmp_path, monkeypatch):
    from ruta_dia_agents import config

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert config._local_root() == tmp_path / "RutaDIA"


class FakeApp:
    """Servicio local mínimo para probar cómo reconoce el lanzador a Hilo."""

    def __init__(self, body: bytes):
        from http.server import BaseHTTPRequestHandler, HTTPServer
        from threading import Thread

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


def test_launcher_only_trusts_a_port_that_answers_as_hilo():
    import interface

    hilo = FakeApp(b'{"app_id": "ruta-dia-local", "available": false}')
    other = FakeApp(b'{"app_id": "otra-cosa"}')
    broken = FakeApp(b"<html>no es json</html>")
    try:
        assert interface.app_status(hilo.url) == {"app_id": "ruta-dia-local", "available": False}
        assert interface.app_status(other.url) is None
        assert interface.app_status(broken.url) is None
    finally:
        for app in (hilo, other, broken):
            app.close()
    assert interface.app_status(hilo.url) is None  # ya no hay nadie en ese puerto


def test_stop_forgets_a_process_that_is_no_longer_the_same(tmp_path, monkeypatch, capsys):
    import interface

    monkeypatch.setattr(interface, "local_dir", lambda name: tmp_path)
    stopped = []
    monkeypatch.setattr(interface, "stop_process", stopped.append)
    interface.stop(8787)
    assert "No hay una interfaz registrada" in capsys.readouterr().out

    record = tmp_path / "interface-8787.json"
    saved = {"ProcessId": 4242, "CreationDate": "100", "ExecutablePath": "/usr/bin/python"}
    record.write_text(interface.json.dumps(saved), encoding="utf-8")
    # mismo PID, otro inicio: es otro proceso y no se toca
    monkeypatch.setattr(interface, "process_identity", lambda pid: {**saved, "CreationDate": "9"})
    interface.stop(8787)
    assert stopped == [] and not record.exists()

    record.write_text(interface.json.dumps(saved), encoding="utf-8")
    monkeypatch.setattr(interface, "process_identity", lambda pid: dict(saved))
    interface.stop(8787)
    assert stopped == [4242] and not record.exists()
