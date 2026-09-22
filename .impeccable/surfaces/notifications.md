# Notificaciones de Hilo

Actualizado el 18 de septiembre de 2026. Modo: Operate. Esta superficie documenta la campanita y los avisos transitorios implementados; la agenda y sus datos siguen definidos en `PRODUCT.md` y en la superficie de Calendario.

## Bandeja

La campanita de la cabecera es un objetivo de 44×44px y abre una bandeja blanca de hasta 390px. La lista contiene solo entradas pendientes y las agrupa, en este orden, como **Vencidas**, **Para hoy** y **Próximos días**. «Próximos días» cubre los tres días posteriores al actual. Cada fila presenta icono de tipo, título, fecha u hora y proyecto; al pulsarla, cierra la bandeja y abre el calendario en esa fecha.

Los chips unen texto y color: «Vencida» rojo, «Hoy» ámbar y «Próxima» azul. El badge rojo de la campana y el contador de Calendario suman únicamente vencidas y las pendientes que quedan hoy; el valor visible se compacta a `9+`. El total dentro del panel sí incluye los tres grupos.

Cada grupo muestra como máximo seis entradas. Si quedan más, aparece «Y N avisos más en el calendario». El pie «Ver calendario completo» siempre ofrece la salida a la agenda. Cuando no hay entradas en la ventana de aviso, se muestra «Todo está en orden» con icono de verificación y explicación; no se deja una lista vacía.

## Toasts

Los avisos transitorios admiten cuatro tonos: información, éxito, advertencia y error. Todos incluyen icono, título, texto y botón de cierre con nombre accesible; el cierre mide 44×44px. El tono se expresa por color y contenido, no por color solo. Los avisos que no son error usan `role=status`; los errores usan `role=alert`.

Se muestran como máximo tres y un mensaje repetido sustituye al anterior. Información, éxito y advertencia se retiran a los 4.8 segundos; error, a los 7 segundos. El temporizador se pausa mientras el aviso tiene hover o foco y se reanuda al salir. Abrir la campanita retira todos los toasts para que la bandeja sea la única capa de avisos.

En escritorio se apilan arriba a la derecha. Hasta 700px se fijan abajo con 12px de margen lateral y 14px inferior. Entrada y salida se desactivan con `prefers-reduced-motion`; el contenido no depende de la animación.

## Límites

Son avisos dentro de Hilo, derivados de la agenda local. No implican push, correo ni notificaciones del sistema operativo. Esta documentación no cambia la persistencia, el cálculo temporal ni el código de la aplicación.
