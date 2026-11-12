"""El script de despliegue de la VPS (`scripts/desplegar_vps.sh`) con un `docker` falso.

Comprueba lo que no se puede ensayar en GitHub sin tocar el servidor: que solo acepte la orden
esperada, que respalde antes de cambiar de versión y que vuelva a la anterior si la nueva no
queda sana. En Windows se salta salvo que HILO_BASH apunte a un bash de Git o MSYS.
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "desplegar_vps.sh"
BASH = os.environ.get("HILO_BASH") or (shutil.which("bash") if os.name == "posix" else None)
pytestmark = pytest.mark.skipif(not BASH, reason="hace falta bash (en Windows, HILO_BASH)")

DOCKER_FALSO = r"""#!/usr/bin/env bash
# Anota cada llamada y simula un contenedor que queda sano salvo la versión FALSO_MALA.
registro="$FALSO_DIR/llamadas.log"
case "$1" in
  login) read -r token; echo "login usuario=$4 token=${#token}" >> "$registro" ;;
  logout) echo "logout" >> "$registro" ;;
  image) [[ "${FALSO_HAY_LOCAL:-0}" == 1 ]] ;;
  compose)
    shift; echo "compose $HILO_IMAGEN:$HILO_VERSION $*" >> "$registro"
    [[ "$1" == up ]] && echo "$HILO_IMAGEN:$HILO_VERSION" > "$FALSO_DIR/corriendo"
    true ;;
  inspect)
    if [[ "$(cat "$FALSO_DIR/corriendo" 2>/dev/null)" == *"${FALSO_MALA:-ninguna}" ]]; then
      echo unhealthy; else echo healthy; fi ;;
  *) echo "otro $*" >> "$registro" ;;
esac
"""


@pytest.fixture
def servidor(tmp_path):
    binarios = tmp_path / "bin"
    binarios.mkdir()
    for nombre, contenido in {"docker": DOCKER_FALSO, "sleep": "#!/usr/bin/env bash\n"}.items():
        archivo = binarios / nombre
        archivo.write_text(contenido, encoding="utf-8", newline="\n")
        archivo.chmod(0o755)
    if not shutil.which("flock"):  # Git Bash no lo trae; en Linux se usa el real
        (binarios / "flock").write_text("#!/usr/bin/env bash\n", encoding="utf-8", newline="\n")
        (binarios / "flock").chmod(0o755)
    hilo = tmp_path / "hilo"
    (hilo / "app").mkdir(parents=True)
    (hilo / "datos").mkdir()
    (hilo / "datos" / "notebooks.sqlite3").write_bytes(b"datos")
    return tmp_path, binarios, hilo


def ruta(camino: Path) -> str:
    """Ruta como la ve bash. En Git Bash, C:/x pasa a /c/x: tar toma «C:» por un equipo remoto."""
    if os.name == "posix":
        return camino.as_posix()
    return "/" + camino.as_posix().replace(":", "", 1)


def desplegar(servidor, orden, token="token-temporal", **extra):
    tmp, binarios, hilo = servidor
    sistema = os.environ.get("PATH", "") if os.name == "posix" else "/usr/bin:/bin"
    entorno = {
        **os.environ, "HOME": ruta(tmp), "HILO_DIR": ruta(hilo), "FALSO_DIR": ruta(tmp),
        "SSH_ORIGINAL_COMMAND": orden, "PATH": f"{ruta(binarios)}:{sistema}", **extra,
    }
    # En bytes, para que Windows no cambie el salto de línea del token.
    resultado = subprocess.run([BASH, SCRIPT.as_posix()], input=f"{token}\n".encode(),
                               env=entorno, capture_output=True, timeout=60)
    resultado.stdout, resultado.stderr = resultado.stdout.decode(), resultado.stderr.decode()
    llamadas = tmp / "llamadas.log"
    return resultado, llamadas.read_text().splitlines() if llamadas.exists() else []


IMAGEN = "ghcr.io/crparra4/sma-metodologias-innovacion"


def test_a_healthy_version_goes_live_after_a_backup(servidor):
    _, _, hilo = servidor
    resultado, llamadas = desplegar(servidor, "desplegar sha-abc1234 crparra4",
                                    FALSO_HAY_LOCAL="1")
    assert resultado.returncode == 0, resultado.stderr
    assert llamadas[0] == "login usuario=crparra4 token=14"
    assert llamadas[1] == f"compose {IMAGEN}:sha-abc1234 pull --quiet aplicacion"
    # La primera vez detiene la versión construida en el servidor.
    assert llamadas[2] == "compose hilo:local stop aplicacion"
    assert f"compose {IMAGEN}:sha-abc1234 up -d --no-build --force-recreate aplicacion" in llamadas
    assert llamadas[-1] == "logout"
    assert (hilo / "despliegue" / "version-actual").read_text().strip() == f"{IMAGEN}:sha-abc1234"
    assert len(list((hilo / "respaldos").glob("datos-*-antes-de-sha-abc1234.tar.gz"))) == 1


def test_an_unhealthy_version_rolls_back_to_the_previous_one(servidor):
    _, _, hilo = servidor
    desplegar(servidor, "desplegar sha-aaaaaaa crparra4")
    resultado, llamadas = desplegar(servidor, "desplegar sha-bbbbbbb crparra4",
                                    FALSO_MALA="sha-bbbbbbb")
    assert resultado.returncode == 1
    assert "volviendo a" in resultado.stdout
    assert llamadas[-2] == (
        f"compose {IMAGEN}:sha-aaaaaaa up -d --no-build --force-recreate aplicacion")
    assert llamadas[-1] == "logout"
    assert (hilo / "despliegue" / "version-actual").read_text().strip() == f"{IMAGEN}:sha-aaaaaaa"
    assert "fallo" in (hilo / "despliegue" / "historial.log").read_text()


@pytest.mark.parametrize("orden", [
    "bash -i", "desplegar latest crparra4", "desplegar sha-abc1234",
    "desplegar sha-abc1234 crparra4; rm -rf ~", "desplegar sha-ABC1234 crparra4",
    "desplegar sha-abc1234 crparra4 extra", "desplegar sha-abc1234 -u=raro",
])
def test_anything_but_the_expected_order_is_refused_before_touching_docker(servidor, orden):
    resultado, llamadas = desplegar(servidor, orden)
    assert resultado.returncode == 1
    assert llamadas == []


def test_without_a_token_nothing_is_deployed(servidor):
    resultado, llamadas = desplegar(servidor, "desplegar sha-abc1234 crparra4", token="")
    assert resultado.returncode == 1 and "token" in resultado.stderr
    assert llamadas == []
