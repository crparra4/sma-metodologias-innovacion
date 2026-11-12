# Despliegue automático de `main` a la VPS

Cada `push` a `main` que pase el CI se publica solo:

```
push a main ──► CI (Ruff, pruebas, build) ──► Despliegue
                                               ├─ 1. construye la imagen ARM64 y la publica en GHCR
                                               └─ 2. entra a la VPS por SSH y corre ~/hilo/desplegar.sh
                                                     ├─ descarga la imagen (Hilo sigue en línea)
                                                     ├─ detiene Hilo y respalda ~/hilo/datos
                                                     ├─ arranca la versión nueva
                                                     └─ si no queda «healthy» en 150 s, vuelve a la anterior
```

Archivos: `.github/workflows/despliegue.yml` (el workflow) y `scripts/desplegar_vps.sh` (lo que
corre en el servidor; sus pruebas están en `tests/test_desplegar_vps.py`).

`develop` y `staging` siguen pasando por el CI, pero no se despliegan.

## Seguridad

- **La llave SSH de GitHub solo puede desplegar.** En `authorized_keys` va con `command=`: aunque
  alguien la robara, solo podría correr `desplegar.sh`. El script rechaza cualquier orden que no
  sea `desplegar sha-<commit> <usuario>`.
- **El servidor decide qué imagen corre.** El nombre de la imagen está fijo en el script; GitHub
  solo dice qué versión.
- **No quedan credenciales del registro en la VPS.** El token de GHCR es el temporal del workflow,
  llega por la entrada estándar y se cierra la sesión al terminar.
- **Huella del servidor fija** (`VPS_KNOWN_HOSTS`): si alguien suplanta la VPS, la conexión se
  rechaza.
- **Las claves de Hilo nunca entran a la imagen ni a GitHub.** Los `.env` (Claude, calendarios,
  invitación) siguen en el servidor. El repositorio es público.
- **Fuera del alcance:** los `pull_request` (incluidos los de forks) nunca disparan el despliegue,
  solo los `push` a `main` del propio repositorio.

## Configuración (una sola vez)

### 1. En la VPS

Hilo ya debe correr con `docker compose` en `~/hilo/app` (`docs/contenedores.md`). Actualiza ahí
el código para que `compose.yaml` tenga la línea
`image: ${HILO_IMAGEN:-hilo}:${HILO_VERSION:-local}` y luego instala el script **fuera** del
código, para que un cambio en el repositorio no lo modifique sin que lo revises:

```bash
install -m 700 ~/hilo/app/scripts/desplegar_vps.sh ~/hilo/desplegar.sh
```

### 2. Una llave solo para desplegar

En tu PC (no en la VPS):

```bash
ssh-keygen -t ed25519 -f hilo-despliegue -N "" -C "github-despliegue-hilo"
```

Copia el contenido de `hilo-despliegue.pub` y agrégalo en la VPS al final de
`~/.ssh/authorized_keys`, **en una sola línea** y con las restricciones delante:

```
command="/home/ubuntu/hilo/desplegar.sh",no-port-forwarding,no-X11-forwarding,no-agent-forwarding,no-pty ssh-ed25519 AAAA... github-despliegue-hilo
```

(Cambia `/home/ubuntu` si el usuario del servidor es otro: `echo $HOME`.)

### 3. La huella del servidor

Desde tu PC:

```bash
ssh-keyscan -t ed25519 DIRECCION-DE-LA-VPS
```

Compara la huella con la que muestra la VPS (`ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub`)
antes de confiar en ella.

### 4. En GitHub

1. **Settings → Environments → New environment**: `produccion`.
   - En *Deployment branches*, deja solo `main`.
   - Opcional: *Required reviewers* con tu usuario, si quieres aprobar cada despliegue con un clic.
2. En ese entorno, **Environment secrets**:

   | Secreto | Valor |
   |---|---|
   | `VPS_HOST` | Dirección de la VPS |
   | `VPS_USER` | Usuario del servidor (por ejemplo, `ubuntu`) |
   | `VPS_SSH_KEY` | Contenido completo de `hilo-despliegue` (la privada) |
   | `VPS_KNOWN_HOSTS` | La línea que devolvió `ssh-keyscan` |
   | `VPS_PORT` | Solo si SSH no usa el 22 |

3. Borra `hilo-despliegue` de tu PC: ya quedó en GitHub.

Opcionales, en **Settings → Secrets and variables → Actions → Variables**: `HILO_RUNNER` y
`HILO_PLATAFORMA`, si algún día la VPS deja de ser ARM64 (para x86: `ubuntu-latest` y
`linux/amd64`).

### 5. Primera vez

El workflow solo existe para GitHub cuando está en `main`. Tras unir `develop` en `main`:
**Actions → Despliegue → Run workflow** (rama `main`). La primera publicación crea el paquete en
GHCR, ligado al repositorio; puede quedar privado.

## Uso diario

- **Desplegar:** haz merge o push a `main`. En unos minutos queda en línea. El resumen del job
  dice qué versión salió.
- **Volver atrás:** **Actions → Despliegue → Run workflow**, con la etiqueta anterior
  (`sha-xxxxxxx`) en `version`. Las etiquetas están en GHCR y en `~/hilo/despliegue/historial.log`.
- **Respaldos:** `~/hilo/respaldos/datos-*-antes-de-sha-*.tar.gz`. Se guardan los 5 más recientes.
- **Qué no se despliega solo:** los cambios en `compose.yaml`, en `desplegar_vps.sh` y en los
  `.env`. Esos se aplican a mano en el servidor, a propósito.
- **Corte de servicio:** de unos segundos a un minuto por despliegue, mientras se respalda y
  arranca. Mejor no desplegar en plena sesión con usuarios.
