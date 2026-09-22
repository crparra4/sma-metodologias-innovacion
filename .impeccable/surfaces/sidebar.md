# Menú lateral de Hilo

> Estado: sustituido el 18 de septiembre de 2026. `supersededBy: chat-workspace`. La navegación vigente es superior, con desplegable móvil; las medidas laterales siguientes son registro histórico. Consultar [chat-workspace.md](chat-workspace.md).

Actualizado el 18 de septiembre de 2026. Modo: Operate. Esta especificación de la superficie sustituye las reglas anteriores de Menú y Perfil del sistema global para el panel lateral.

La referencia del usuario (`codex-clipboard-cd60059d-ac95-4857-bf5c-7f8e6f2b16ab.png`) fija una navegación compacta y vertical, perfil arriba, grupos separados y selección tonal. Se conserva el azul de Hilo: fondo plano `#2a55bc`, texto `#f0f5fe`, secundarios `#ffffffdb` y selección `#ffffff26`. Panel de 232px en escritorio, a toda altura, esquinas rectas y sin sombra de escritorio. El cajón móvil mantiene los 260px existentes y su capa de fondo.

## Estructura y comportamiento

- Cabecera: avatar de 24px con iniciales y estado real del modelo, nombre de cuenta con elipsis y acceso al diálogo de perfil; búsqueda y nuevo proyecto a su derecha.
- Navegación: Inicio; Espacio de trabajo con Proyectos y Fichas metodológicas; Tus proyectos con los tres recientes. Los contadores representan datos reales.
- Búsqueda vuelve a Inicio y enfoca el campo de búsqueda de proyectos. Proyectos abre la biblioteca existente. Nuevo proyecto abre el formulario existente.
- Las filas recientes muestran icono y título en una línea, conservan el nombre completo en tooltip y estado `aria-current`. No se modifican los proyectos ni el historial.
- El bloque inferior de marca, estado escrito y recarga se retiró por solicitud del usuario. La comprobación automática y el punto de estado del avatar permanecen activos.

Filas de al menos 32px en escritorio y 40px en móvil; tipografía de 12px, títulos de grupo de 11px, radio de 6px e iconos de 15px. Foco claro sobre azul. Los nuevos accesos de navegación se bloquean durante carga o generación junto con los existentes.

## Verificación

Compilación TypeScript/Vite correcta. Prueba manual con una cuenta y tres proyectos claramente sintéticos en un almacenamiento temporal independiente, mediante un servidor de prueba local en 8791. Verificados: navegación a fichas, búsqueda y su foco, nuevo proyecto y cancelación, abrir proyecto reciente, selección resaltada y cajón móvil 390×844. Confirmación final: filas de 32px, selección `aria-current=page`, sin desbordamiento horizontal. Escritorio inspeccionado en 1280×720.

Detector: un aviso anterior de transición de padding fuera del menú; sin hallazgos nuevos del menú. El servidor y la pestaña de prueba se cerraron; no se creó ninguna cuenta ni proyecto en la memoria real del usuario.
