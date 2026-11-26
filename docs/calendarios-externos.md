# Calendarios de Google y Outlook en Hilo

Hilo tiene dos formas de juntar su calendario con el de cada persona:

| | Dirección | Qué necesita |
|---|---|---|
| **Enlace .ics** (Ajustes → Preferencias → «Llevar tu calendario de Hilo…») | Hilo → Google u Outlook | Solo que Hilo tenga dirección pública. Nada que registrar. |
| **Conectar la cuenta** (Ajustes → Preferencias → «Ver tus calendarios…») | Google u Outlook → Hilo | Registrar Hilo como aplicación en Google y en Microsoft (esta guía). |

Las dos son de solo lectura. Al conectar la cuenta, Hilo lee los eventos del rango que se ve en la
pantalla y los muestra con borde punteado. No los guarda, no los cambia y no se los pasa al
asistente.

## 1. Registrar Hilo en Google

Se hace una vez, con la cuenta de Google de quien administra Hilo.

1. Entra a <https://console.cloud.google.com/> y crea un proyecto (por ejemplo, «Hilo»).
2. **APIs y servicios → Biblioteca**: busca **Google Calendar API** y habilítala.
3. **Pantalla de consentimiento de OAuth** (en consolas nuevas: *Google Auth Platform*):
   - Tipo de usuario **Externo**, nombre de la aplicación y correo de asistencia.
   - **Público**: déjala en modo **Prueba** y agrega como *usuarios de prueba* los correos que
     van a conectar su calendario (hasta 100).
   - **Acceso a los datos / Permisos**: agrega `openid`, `email` y
     `https://www.googleapis.com/auth/calendar.events.readonly`.
4. **Credenciales → Crear credenciales → ID de cliente de OAuth**, tipo **Aplicación web**. En
   **URI de redireccionamiento autorizados** escribe, exactamente:
   - `https://TU-DOMINIO/calendarios/google/vuelta` (el servidor)
   - `http://localhost:8787/calendarios/google/vuelta` (opcional, para probar en el PC)
5. Copia el **ID de cliente** y el **secreto** en `HILO_GOOGLE_CLIENT_ID` y
   `HILO_GOOGLE_CLIENT_SECRET`.

**Límites del modo Prueba:**
- Solo pueden entrar los correos que agregaste como usuarios de prueba.
- Google anula el permiso a los 7 días y la persona tiene que volver a conectar. Hilo lo detecta y
  avisa en el calendario.

Para quitar esos límites hay que **publicar** la aplicación. Como el permiso de calendario es
sensible, Google la revisa: pide un dominio propio verificado, una página de inicio y una política
de privacidad publicadas, y puede tardar semanas.

## 2. Registrar Hilo en Microsoft

1. Entra a <https://entra.microsoft.com/> → **Aplicaciones → Registros de aplicaciones → Nuevo
   registro**. Si tu cuenta personal no te deja crear registros, Microsoft puede pedirte un
   directorio de Entra.
2. **Tipos de cuenta admitidos**: «Cuentas en cualquier directorio organizativo y cuentas
   personales de Microsoft» (así entran Outlook.com, Hotmail y cuentas de empresa).
3. **URI de redirección**: plataforma **Web**, `https://TU-DOMINIO/calendarios/microsoft/vuelta`.
   Puedes agregar también la de `http://localhost:8787/...` para pruebas.
4. **Certificados y secretos → Nuevo secreto de cliente**: copia el **Valor** (no el «Id. de
   secreto»). Vence; anota la fecha para renovarlo.
5. **Permisos de API → Microsoft Graph → Permisos delegados**: `Calendars.Read`,
   `offline_access`, `openid` y `email`.
6. En **Información general**, el **Id. de aplicación (cliente)** va en `HILO_MICROSOFT_CLIENT_ID`
   y el valor del secreto en `HILO_MICROSOFT_CLIENT_SECRET`.

Con cuentas de una organización (por ejemplo, la de la universidad), el administrador puede tener
bloqueado que las personas den permisos a aplicaciones de terceros. En ese caso Microsoft muestra
«Se necesita la aprobación del administrador» y solo la organización puede habilitarlo.

## 3. Configurar el servidor

En el archivo de entorno de Hilo (en la VPS, `~/hilo/.env.hilo`):

```env
HILO_GOOGLE_CLIENT_ID=...
HILO_GOOGLE_CLIENT_SECRET=...
HILO_MICROSOFT_CLIENT_ID=...
HILO_MICROSOFT_CLIENT_SECRET=...
# La misma dirección que registraste, sin / al final:
HILO_URL_PUBLICA=https://TU-DOMINIO
# Opcional: clave Fernet para cifrar los permisos guardados.
# HILO_CLAVE_CALENDARIOS=
```

- **`HILO_URL_PUBLICA`** debe coincidir con la de los pasos anteriores. Si no está, Hilo arma la
  dirección con la que llega cada petición. Detrás de nginx eso solo funciona si nginx envía
  `X-Forwarded-Proto` y `Host`.
- **`HILO_CLAVE_CALENDARIOS`**: sin esta variable, Hilo crea `calendarios.key` en su carpeta de
  datos. Si esa clave cambia o se pierde, las conexiones guardadas dejan de servir y cada persona
  tiene que conectar otra vez. Para generar una:

  ```bash
  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
  ```

Reinicia Hilo después de cambiar el entorno. El proveedor que no tenga sus dos variables aparece
en Ajustes como «No disponible en este servidor todavía».

## Cómo funciona por dentro

- **Flujo**: código de autorización con PKCE (S256) y cliente confidencial, en
  `src/hilo/integraciones/calendarios.py`. Las rutas están en `web.py`:
  `POST /api/calendarios/{proveedor}/conectar`, `GET /calendarios/{proveedor}/vuelta`,
  `DELETE /api/calendarios/{proveedor}`, `GET /api/calendarios` y `GET /api/calendario-externo`.
- **Seguridad del regreso**: el `state` es de un solo uso, vence a los 10 minutos y va ligado a la
  cuenta y a una cookie del navegador que empezó (`SameSite=Lax`, ruta `/calendarios/`). Así nadie
  puede terminar en su navegador un flujo iniciado por otra cuenta, ni al revés.
- **Permisos guardados**: los tokens de acceso y de renovación se guardan cifrados con Fernet en
  `auth.sqlite3`, tabla `calendar_connections`. Microsoft rota el de renovación en cada uso y Hilo
  guarda el nuevo.
- **Desconectar**: borra la conexión. En Google también anula el permiso. En Microsoft, la persona
  lo quita desde <https://myaccount.microsoft.com/> → Aplicaciones y servicios.
- **Rango**: Hilo pide como máximo 100 días por consulta, solo del calendario principal, y descarta
  los eventos cancelados. Los de todo el día van en una franja aparte en la vista semanal.
