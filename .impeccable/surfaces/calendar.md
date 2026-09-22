# Calendario de Hilo

Actualizado el 18 de septiembre de 2026. Modo: Operate. Referencias del usuario: calendarios de citas con panel lateral del día, vista de mes con entradas de color y vista semanal por horas.

## Qué se anota

Cada entrada es una tarea, un recordatorio o una reunión (`kind`), con fecha y hora de inicio y hora de fin opcional (`ends_at`, posterior al inicio). Puede ligarse a un proyecto o quedar como personal. Las tareas previas al calendario se leen como tipo tarea, sin fin. Guardar una entrada envía siempre tipo y fin: completarla desde el calendario o desde la agenda de Inicio no los borra, y editar la fecha desde Inicio traslada la duración.

## Identificación

Dos señales independientes: el color es el proyecto (el de su carpeta; lo personal en rosa) y el icono es el tipo. La paleta de entradas (`--ev-bg`, `--ev-ink`, `--ev-dot`) es propia, porque los tonos de las carpetas no sostienen texto; la tinta sobre su fondo da al menos 7:1. Vencida: punto rojo delante del título, nunca franjas laterales. Completada: tachada y atenuada. Los filtros del panel (tipos y proyectos, con su color) sirven también de leyenda.

## Vistas

- Mes: semana desde el lunes, seis filas. Cada día muestra las entradas que caben en el alto real de su fila (`fitMonthCells`, recalculado al cambiar el tamaño de la ventana) y el resto como «+N más», que abre el día en el panel. Alturas fijas de número, entradas y «+N más», porque el ajuste cuenta píxeles. Un botón + por día aparece al apuntarlo.
- Semana: columnas por día y 48px por hora, desplazada al inicio de la primera entrada. Lo que tiene fin es un bloque de su duración; lo puntual, una píldora a su hora. Las entradas que se solapan se reparten en carriles (`dayLanes` en `agenda.ts`). Línea roja de «ahora» en el día actual. Pulsar un espacio libre crea una entrada a esa hora.
- Panel del día a la derecha: lista completa con casilla para completar, tipo, rango horario, proyecto y «Vencida».
- Hasta 860px el panel pasa debajo y el mes muestra puntos de color por día en lugar de textos.

## Notificaciones

La campanita cuenta lo vencido y lo que queda de hoy, y lista Vencidas, Hoy y Próximos días (tres días). Cada aviso abre el calendario en su día. El mismo número aparece junto a Calendario en el menú. Se recalcula cada minuto y tras cada cambio. Solo dentro de Hilo: no hay avisos del sistema ni correos.
