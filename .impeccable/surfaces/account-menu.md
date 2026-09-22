# Menú de cuenta de Hilo

Modo: Operate. Actualizado el 18 de septiembre de 2026. La referencia del usuario fija un desplegable azul de Hilo bajo el avatar, con identidad destacada y acciones agrupadas. Sustituye la apertura directa del editor de perfil desde el avatar.

El avatar conserva las iniciales y el estado del modelo; al pulsarlo abre un panel de hasta 320px, radio 12px, fondo #2a55bc y tarjeta de identidad #244ba8. La tarjeta presenta un avatar sobre blanco translúcido #ffffff26 de 54px, el nombre real y @usuario de la cuenta local. Hilo no dispone de correo de cuenta: no se inventa ni se copia el de la referencia.

Acciones: Perfil abre el editor existente; Configuración de la cuenta reutiliza ese editor y muestra el usuario local; Tema expande el estado Claro actual y Oscuro próximamente; guía de inicio rápido abre Ayuda; Cambiar de cuenta y Finalizar la sesión cierran la sesión local y regresan al acceso. No hay conmutación instantánea entre cuentas ni modo oscuro implementado. El cierre de sesión bloquea sus acciones mientras se procesa y muestra un error si falla.

El panel cierra al pulsar fuera o presionar Escape, que devuelve el foco al avatar. aria-expanded y aria-controls reflejan su estado. En móvil es un panel fijo debajo de la barra, ajustado al ancho y alto disponibles; su contenido puede desplazarse. Abrir la navegación, ayuda o campanita cierra el panel de cuenta.

Verificación: TypeScript/Vite y detector sin hallazgos. Capturas inline inspeccionadas en escritorio 1280×720 y móvil 390×844. Con cuenta sintética en localhost:8791 y almacenamiento aislado se verificaron Perfil y Configuración (sin guardar), guía, Tema, Escape con foco restaurado y Cambiar de cuenta, que mostró el acceso. Finalizar la sesión usa la misma función de cierre. Sin cambios en cuentas o proyectos reales.
