---
name: Hilo · acceso
description: Sistema visual del acceso y registro local adaptado a la referencia del usuario.
colors:
  primary: "#1877d5"
  primary-hover: "#1266bb"
  focus: "#2383e2"
  surface: "#fff"
  ink: "#242424"
  title: "#171717"
  label: "#626262"
  muted: "#737373"
  border: "#c9c9c9"
typography:
  title:
    fontFamily: '"Segoe UI", system-ui, -apple-system, BlinkMacSystemFont, sans-serif'
    fontSize: "22px"
    fontWeight: 650
    lineHeight: 1.25
    letterSpacing: "-.025em"
  subtitle:
    fontFamily: '"Segoe UI", system-ui, -apple-system, BlinkMacSystemFont, sans-serif'
    fontSize: "21px"
    fontWeight: 600
    lineHeight: 1.3
    letterSpacing: "-.02em"
  body:
    fontFamily: '"Segoe UI", system-ui, -apple-system, BlinkMacSystemFont, sans-serif'
    fontSize: "14px"
    lineHeight: 1.5
  label:
    fontFamily: '"Segoe UI", system-ui, -apple-system, BlinkMacSystemFont, sans-serif'
    fontSize: "12px"
    fontWeight: 500
rounded:
  control: "7px"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.surface}"
    rounded: "{rounded.control}"
    padding: "10px 16px"
    width: "100%"
  input:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "0 13px"
    height: "40px"
    width: "100%"
---

# Design System: Hilo · acceso

## Overview

**Creative North Star: "Acceso blanco y centrado de la referencia del usuario"**

Esta documentación describe exclusivamente el acceso y registro de Hilo. La imagen de Notion proporcionada por el usuario fija una superficie blanca, una columna compacta sin caja exterior y una jerarquía centrada. Hilo conserva su logo real y su autenticación local por usuario y contraseña.

El documento complementa el sistema global existente; no extiende esta composición a Inicio, agenda, proyectos o chat. La fuente normativa es el código construido, especialmente `prototipo/frontend/src/style.css` (reglas de acceso), `prototipo/frontend/index.html` (sección de acceso) y `setAuthMode` en `prototipo/frontend/src/main.ts`.

**Key Characteristics:**

- Fondo blanco a altura completa y formulario sin tarjeta exterior.
- Logo real de Hilo centrado y texto en español.
- Azul para la acción principal y el foco; grises para información secundaria.
- Acceso progresivo con usuario primero y contraseña después.

La referencia original era un archivo temporal local. El responsable de la implementación informó inspección manual de acceso en escritorio (720×912), acceso móvil (390×844) y registro móvil, además de compilación correcta. Este pase documental no dispone de capturas del resultado para una revisión visual independiente; no certifica equivalencia píxel a píxel. El informe de comprobación está en `prototipo/data/interface-qa/acceso-reference-2026-09-18.md`.

## Colors

### Primary

El azul de acción ocupa el botón principal; su variante más oscura expresa hover. El azul de foco delimita campos y botones cuando reciben interacción de teclado.

**The Acción Rule.** El azul destaca la acción principal y el foco; las explicaciones permanecen neutras.

### Neutral

El blanco constituye fondo y campos. La tinta oscura organiza título y contenido, mientras label y muted distinguen etiquetas, ayudas, explicación y pie. El borde gris delimita campos. El usuario de solo lectura recibe un fondo gris tenue; el cambio de modo se separa con una línea tenue.

Los errores tienen fondo rojo suave y texto rojo oscuro. Son un estado funcional del formulario, no un acento decorativo para otras superficies.

## Typography

Toda la superficie hereda la familia de interfaz Segoe UI y sus alternativas del proyecto. La jerarquía usa título compacto y subtítulo casi del mismo tamaño; la diferencia proviene del peso, tono y posición. Campos, acción y cambio de modo usan body; etiquetas, ayudas, notas y pie usan tamaño pequeño.

En el breakpoint móvil el subtítulo baja a (20px) y elimina sus márgenes laterales negativos. Título y subtítulo admiten balance de líneas. No se incorpora una familia de display ni se propone sustituir la identidad tipográfica global.

## Layout

La pantalla es una columna flex con altura mínima de (100dvh). Su contenido se centra horizontalmente dentro de una anchura máxima de (350px), con margen lateral de pantalla de (24px). El comienzo del contenido usa `clamp(64px,10.5vh,100px)`; la composición no se centra verticalmente.

El logo mide (40×40px) y se separa del título por (25px). Los campos se separan por (18px). El botón principal queda después del formulario, y el cambio de modo tiene separador con margen superior de (38px) y padding superior de (27px). La nota de privacidad conserva una anchura máxima de (330px).

El pie «Español · Hilo / Ruta DIA» se empuja al fondo mediante margen automático y un padding superior de (56px). Hasta (480px), la pantalla usa padding (64px 24px 18px), y el pie reduce ese espacio a (48px). El registro largo debe poder desplazar la página verticalmente; el pie no es fijo ni superpuesto.

**The Columna Rule.** Conservar una sola columna sin tarjeta exterior en ambos modos de acceso.

## Elevation & Depth

La pantalla y el contenedor del formulario no tienen sombra. Los controles se distinguen por borde y color. El botón principal sí conserva la sombra sutil observada en el código; esto no autoriza sombras de tarjeta ni una prohibición global de sombras.

## Shapes

Campos y acción principal comparten esquinas suavemente curvas. El estado de error tiene esquinas de (6px). Los enlaces de cambio de modo y de usuario son botones sin relleno visible, con texto subrayado.

## Components

### Buttons

La acción principal ocupa toda la columna, tiene altura mínima de (40px) y usa texto blanco seminegrita. El hover oscurece el fondo sin animación propia. El foco visible tiene contorno azul de (2px) y separación de (3px). El estado disabled hereda opacidad (.48) y cursor de no disponibilidad del proyecto.

«Crear cuenta», «Iniciar sesión» y «Cambiar usuario» son botones secundarios de texto subrayado. No se presentan como pestañas en una barra ni como acciones de proveedor externo.

### Inputs / Fields

Campos blancos con borde continuo de (1px), padding horizontal y texto body. El foco cambia el borde a azul y aplica contorno de (2px) con offset (-1px). Las etiquetas permanecen visibles; el placeholder complementa su significado. El usuario se vuelve de solo lectura al avanzar a contraseña.

El error usa `role="alert"`; la validación devuelve el foco al campo pertinente. La ayuda del usuario se enlaza mediante `aria-describedby`. Los modos ocultos usan el atributo `hidden` y salen de la presentación.

### Acceso progresivo y registro

«Continuar» valida el formato del usuario y revela contraseña, sin consultar aún si existe la cuenta. El botón pasa a «Iniciar sesión» y el foco pasa a contraseña. «Cambiar usuario» vuelve al primer paso. El registro muestra nombre, usuario, contraseña y confirmación, junto con la ayuda de longitud mínima.

Cambiar de modo limpia las contraseñas y el error, ajusta autocomplete, texto de acción y nota, y enfoca el primer campo correspondiente. Durante envío se deshabilitan acción y cambios de modo. La autenticación y registro siguen usando las rutas locales existentes.

## Do's and Don'ts

### Do:

- **Do** conservar el logo real de Hilo, el español y la columna blanca centrada.
- **Do** mantener usuario y contraseña locales, con avance y retorno entre pasos.
- **Do** permitir desplazamiento del registro y mantener visible el foco de teclado.

### Don't:

- **Don't** introducir tarjeta exterior o sombra de contenedor en esta superficie.
- **Don't** añadir proveedores externos, acceso por correo o enlaces legales sin funcionalidad respaldada.
- **Don't** trasladar las reglas específicas de acceso al sistema global de proyectos y chat.

No se canonizan la marca de Notion ni sus opciones de proveedor y condiciones: pertenecen a la referencia, no a las capacidades o identidad de Hilo. Tampoco se canoniza el hallazgo de transición de padding de la biblioteca metodológica, ajeno al acceso.


## Métodos preparados para integración futura · 18 de septiembre de 2026

Por solicitud explícita del usuario se incorpora la segunda referencia: Google, ChatGPT, Apple, Microsoft, Passkey y SSO, en ese orden, en una cuadrícula de tres columnas y dos filas. Aparecen después del botón principal, bajo «o continúa con», con iconos de 20px, borde gris fino, radio de 7px y altura mínima de 73px. La cuadrícula mantiene sus tres columnas en móvil.

Son botones HTML deshabilitados y conservan el contraste normal para respetar la referencia. Cada nombre accesible indica «próximamente» y la nota visible explica su disponibilidad futura. No envían credenciales, abren servicios externos ni sustituyen la autenticación local. La integración futura se identifica mediante `data-provider`.

Los iconos OpenAI y Apple son SVG locales de Simple Icons 13.21.0; Google y Microsoft son vectores multicolor y Passkey/SSO usan vectores de interfaz. Compilación correcta e inspección manual en escritorio 720×912 y móvil 390×844 sin desbordamiento horizontal.


## Idiomas de acceso · 18 de septiembre de 2026

El pie contiene un selector nativo compacto con dos opciones: Español (`es`) y English (`en`). Se inicia en español y guarda la elección en `hilo-language` del almacenamiento local del navegador; si el almacenamiento no está disponible, la selección sigue funcionando durante la visita.

La elección traduce títulos, campos, placeholders, ayudas, acciones, estados de carga, mensajes de validación y disponibilidad futura de los métodos de acceso. Cambiar idioma conserva los campos y el paso actual. La sección de acceso declara su propio atributo `lang`. El registro y los errores habituales de autenticación también se traducen. La biblioteca, la agenda, el chat y las fichas todavía están en español; este cambio se limita al acceso y registro.

Verificación manual: inglés conservado tras recargar; contraseña vacía traducida al volver a español; nombre del registro conservado al cambiar a inglés; registro móvil 390×844 sin desbordamiento horizontal. Compilación TypeScript/Vite correcta.
