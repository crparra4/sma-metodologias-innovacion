# Guía de pruebas · Árbol, diagnóstico y 5 porqués

Pruebas manuales de lo agregado en septiembre de 2026. Tiempo estimado: **35 a 45 minutos**.
Marca cada casilla; si algo falla, anótalo como se indica al final.

---

## 0 · Antes de empezar

**Reinicia Hilo.** Si ya estaba abierto, sigue corriendo con el código anterior: el backend
no se recarga solo. Desde la raíz del repositorio:

```powershell
.\scripts\stop_interface.ps1
.\scripts\start_interface.ps1
```

Se abre en **http://127.0.0.1:8787/**. Si el modelo no arranca, compruébalo con
`.\.venv\Scripts\python.exe scripts/local_model.py status`.

**Usa un proyecto de prueba**, para no mezclar estos datos con tus proyectos reales:

- Nombre: `Prueba OKR`
- Reto: `Los equipos no ven el avance de sus OKR`

Bórralo al terminar.

---

## Datos para copiar

### Árbol A · con errores a propósito

Sirve para el diagnóstico y los 5 porqués.

| Lugar | Texto | Origen |
|---|---|---|
| **Problema central** | Implementar los OKR con IA y crear una app para centralizarlos | *(vacío)* |
| Causa 1 | Las doce iniciativas están en un solo archivo de Excel | Observación |
| Causa 2 | Falta de una aplicación que centralice los indicadores | *(vacío)* |
| Causa 3 | Nadie es responsable de actualizar cada KR | Entrevistas |
| Efecto 1 | Se duplican reportes entre áreas | Entrevistas |
| Efecto 2 | Las decisiones se toman tarde | *(vacío)* |

Errores plantados: el problema central **describe una solución**; la Causa 2 **nombra lo que
falta**; ninguna causa tiene **causa de fondo**; 2 tarjetas **sin fuente** (Causa 2 y Efecto 2).

### Árbol B · bien hecho

Sirve para comprobar que el diagnóstico **no invente** problemas. Usa otro proyecto de prueba.

| Lugar | Texto | Origen |
|---|---|---|
| **Problema central** | Los equipos no ven el avance de sus OKR a tiempo para decidir | Entrevistas |
| Causa 1 | La demanda de reportes se concentra al cierre de cada mes | Conteo |
| ↳ de fondo de la Causa 1 | Nadie acordó una fecha de corte común | Entrevista 2 |
| Efecto 1 | Uno de cada cinco KR se revisa con datos viejos | Registro |

### Respuestas para los 5 porqués

1. `Porque cada área armó su propio seguimiento y al final alguien los juntó a mano`
2. `No sé, nunca lo he preguntado`
3. `Podría preguntarle a los líderes de área cómo arrancaron`
4. `Creo que nunca se definió un formato común para reportar`

---

## 1 · Árbol: tarjetas y jerarquía

No usa el modelo; todo debería responder al instante.

- [ ] **1.1 Contador.** Al añadir causas y efectos, junto al botón aparece «N de 30».
- [ ] **1.2 Anidar.** En la Causa 3 pulsa «Anidar». Pasa a ser «Causa de fondo 2.1», con sangría
      y la raíz fina, debajo de la Causa 2.
- [ ] **1.3 Subir de nivel.** En esa causa de fondo pulsa «Subir de nivel». Vuelve a ser principal.
- [ ] **1.4 Quitar con hijas.** Anida una causa bajo otra y quita la de arriba. La de fondo
      **no se pierde**: sube de nivel.
- [ ] **1.5 Pasar a efecto.** Una causa con hijas pasa a efectos **junto con sus hijas**.
- [ ] **1.6 Guardar y recargar.** Guarda, recarga la página (F5) y abre el árbol. Todo sigue igual,
      incluida la jerarquía.
- [ ] **1.7 Cambios sin guardar.** Escribe algo sin guardar y cierra la pestaña o cambia de
      proyecto. Aparece un aviso antes de descartar.

---

## 2 · Diagnóstico del árbol

Carga el **Árbol A** tal cual, **sin causas anidadas** (si hiciste la sección 1, deshaz los cambios), y guárdalo.

- [ ] **2.1 Diagnóstico completo.** Pulsa «Diagnosticar» (tarda unos 2 a 5 s). Debe aparecer:
  - en el **problema central**: «Describe una solución»
  - en la **Causa 2**: «Nombra lo que falta»
  - bajo el título **Causas**: «Sin causa de fondo»
  - arriba, en el resumen: «2 de 5 tarjetas todavía no registran de dónde salen»
- [ ] **2.2 Cada nota va en su lugar.** Ninguna observación de una tarjeta aparece solo en el
      resumen: cada una está junto a lo que señala.
- [ ] **2.3 Desactualizado.** Después de diagnosticar, cambia una letra. Aparece «El árbol cambió
      desde este diagnóstico», las notas se atenúan y «Diagnosticar» pide guardar primero.
- [ ] **2.4 Sin alarmas falsas.** Con el **Árbol B** guardado, el diagnóstico **no** marca el
      problema central ni «Nombra lo que falta».
- [ ] **2.5 Sin modelo.** Detén el modelo
      (`.\.venv\Scripts\python.exe scripts/local_model.py stop`) y diagnostica. Salen las reglas y
      el aviso «El modelo local no respondió; por ahora solo se aplicaron las reglas». Vuelve a
      iniciarlo al terminar.
- [ ] **2.6 El agente lo lee.** Con el Árbol A diagnosticado, pregunta en el chat:
      `¿Qué debería corregir primero en mi árbol?`. *Observa* si la respuesta toma en cuenta el
      diagnóstico. No está garantizado: anota lo que pase.

---

## 3 · 5 porqués desde el árbol

Usa el **Árbol A** guardado. Cada turno del modelo tarda entre 20 y 40 segundos.

- [ ] **3.1 Dónde aparece.** «Profundizar con 5 porqués» está en las **causas principales** y
      **no** en las causas de fondo. Con cambios sin guardar, el botón está deshabilitado.
- [ ] **3.2 Inicio.** Pulsa el botón de la **Causa 1**. El chat se abre junto al árbol, se envía
      solo un mensaje de inicio y Hilo pregunta por qué ocurre lo del Excel. La barra dice
      «0 de 5 respuestas».
- [ ] **3.3 Primera respuesta.** Envía la **respuesta 1**. Entra a la cadena («1 de 5») y la
      siguiente pregunta es sobre **tu respuesta**, no sobre el Excel.
- [ ] **3.4 «No sé».** Envía la **respuesta 2**. Aparece «Por investigar», la cuenta **no sube** y
      Hilo pregunta qué podrías revisar o a quién consultar, **sin repetir** la pregunta.
- [ ] **3.5 Plan.** Envía la **respuesta 3**. Se agrega a la duda como «Plan: …» y **no** entra a la
      cadena. Hilo pregunta algo como «Aunque todavía no esté confirmado, ¿por qué crees que…?».
- [ ] **3.6 Hipótesis.** Envía la **respuesta 4**. Entra como paso 2 y la siguiente pregunta es
      sobre **el formato común**.
- [ ] **3.7 Evidencia.** En un paso escribe algo en «De dónde sale» y haz clic fuera. Recarga la
      página: sigue ahí.
- [ ] **3.8 Revisar.** Pulsa «Revisar cadena». Hilo pregunta qué conexión te parece más débil.
      Responde cualquier cosa: tu comentario **no** entra a la cadena.
- [ ] **3.9 Terminar.** Pulsa «Terminar». La causa candidata propuesta viene **sin «Creo que»**.
      Edítala si quieres y pulsa «Guardar resultado».
- [ ] **3.10 Incorporar.** Pulsa «Incorporar al árbol». Aparece una causa de fondo bajo la
      Causa 1, con origen «Análisis de 5 porqués». El botón de la Causa 1 dice
      «Profundizar otra vez».
- [ ] **3.11 Uno a la vez.** Inicia otro análisis. Mientras siga en curso, los botones de las otras
      causas están deshabilitados y su descripción explica por qué.
- [ ] **3.12 Descartar.** Pulsa «Descartar» y confirma. La barra desaparece y la conversación
      queda en el chat.
- [ ] **3.13 Herramienta fija.** Inicia un análisis nuevo y, a mitad de él, escribe `quiero aplicar PESTEL`. Hilo
      **sigue** con los 5 porqués. *(Ese mensaje entra como paso: quítalo con «Quitar».)*
- [ ] **3.14 Respuestas flojas.** En un análisis en curso, envía una por una:
  - `por muchas cosas`: **no** entra; la barra dice «No se anotó…» y Hilo pide una sola razón.
  - `Porque no hemos comprado Power BI`: **no** entra; Hilo pregunta qué dificultad resolvería.
    Envíala **otra vez**: ahora sí entra (la cadena es tuya).
  - `¿Cuánto cuesta una licencia de Power BI?`: **no** entra y Hilo **no** inventa un precio.
- [ ] **3.15 Sin idea.** Tras un «no sé», responde `tampoco sé` (la duda queda con
      «Plan: sin definir») y luego otra vez `no sé`: Hilo **deja de insistir** y ofrece revisar la
      cadena o probar otra razón.
- [ ] **3.16 Revisión sin bucle.** En «Revisar cadena», responde `no sé, todas me parecen bien`.
      Hilo **no** repite la pregunta: ofrece seguir preguntando o terminar.

---

## 4 · Interfaz

- [ ] **4.1 Bienvenida.** Un proyecto sin mensajes muestra el símbolo de Hilo, «¡Hola, <tu nombre>!»
      y tres tarjetas. Al pulsar una, el mensaje queda listo en la caja de texto.
- [ ] **4.2 Chat mini.** Con el árbol abierto y el chat al lado, el chat muestra el título en una
      línea, sin el anillo de etapa, y con Compartir. Cierra el chat: Compartir vuelve a la
      cabecera del árbol.
- [ ] **4.3 Chat en grande.** Cierra el árbol. El chat recupera su cabecera original, con anillo y
      etapa.
- [ ] **4.4 Estética.** Hojas en los efectos, raíces en las causas, barras de desplazamiento finas
      que no tapan las esquinas.

---

## Lo que no es un error

- **La redacción del agente cambia** de una vez a otra. Juzga si pregunta **por lo correcto** (la
  última respuesta), no si usa las mismas palabras de esta guía.
- **Los turnos tardan** de 20 a 40 segundos con el modelo local.
- **Durante un análisis, casi todo mensaje cuenta como paso.** No entran: el «no sé», el plan que
  le sigue, lo que se escribe durante la revisión, las preguntas, y, la primera vez, las
  respuestas muy generales o que nombran una herramienta que falta. Si algo entró sin ser una
  respuesta, usa «Quitar».
- La **ficha de 5 porqués** cambió y está **pendiente de validación experta**.

## Si algo falla, anota

1. El número del caso, por ejemplo **3.4**
2. Qué hiciste, qué esperabas y qué pasó
3. Si fue el agente, **copia su mensaje completo**
4. Una captura de pantalla

Las decisiones del Verificador quedan en `data/verifications.jsonl`, una línea por
intento. Sirven para saber si una respuesta rara fue un rechazo y un reintento.
