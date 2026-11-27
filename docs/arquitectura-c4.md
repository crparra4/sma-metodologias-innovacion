# Arquitectura de Hilo · modelo C4

Este documento describe Hilo con el [modelo C4](https://c4model.com) de Simon Brown: cuatro
niveles de zoom, del sistema visto desde afuera hasta el código. Complementa la plantilla
[arc42](arquitectura-arc42.md), que reúne objetivos, restricciones, decisiones y riesgos.

Los diagramas usan Mermaid (GitHub los dibuja) con la notación de C4: cada caja indica su tipo
y su tecnología entre corchetes. Las flechas van de quien usa a quien es usado y llevan el
protocolo.

| Nivel | Pregunta que responde | Sección |
|---|---|---|
| 1 · Contexto | ¿Quién usa Hilo y con qué sistemas habla? | [Contexto del sistema](#nivel-1--contexto-del-sistema) |
| 2 · Contenedores | ¿Qué programas y almacenes forman Hilo? | [Contenedores](#nivel-2--contenedores) |
| 3 · Componentes | ¿Qué hay dentro de la aplicación? | [Componentes](#nivel-3--componentes-de-la-aplicación-hilo) |
| 4 · Código | ¿Cómo está escrito un componente? | [Código](#nivel-4--código) |
| Complementario | ¿Dónde corre cada pieza? | [Despliegue](#diagrama-complementario--despliegue) |
| Complementario | ¿Qué pasa en un turno de chat? | [Dinámico](#diagrama-complementario--un-turno-de-chat) |

Estado descrito: rama `main` al 27 de noviembre de 2026, variante de agentes `g`
(`PlanificadorConControles`, la que usa la interfaz por defecto).

---

## Nivel 1 · Contexto del sistema

```mermaid
flowchart TB
    persona["<b>Persona del equipo de innovación</b><br/>[Persona]<br/>Trabaja un reto con la ruta<br/>metodológica: conversa, llena<br/>tableros y comparte avances"]
    investigador["<b>Investigador</b><br/>[Persona]<br/>Autor del trabajo de grado: instala,<br/>evalúa variantes y revisa auditorías"]

    hilo["<b>Hilo</b><br/>[Sistema de software]<br/>Asistente metodológico multiagente que<br/>guía, paso a paso, las herramientas de<br/>la Ruta DIA y verifica cada respuesta"]

    llm["<b>Servidor del modelo local</b><br/>[Sistema externo: llama.cpp + Qwen3.5-4B]<br/>Genera JSON con esquema estricto<br/>en el computador con GPU"]
    claude["<b>API de Claude</b><br/>[Sistema externo: Anthropic]<br/>Respaldo opcional cuando el<br/>modelo local no responde"]

    persona -- "Usa, por navegador<br/>[HTTP · SSE]" --> hilo
    investigador -- "Ejecuta baterías y turnos<br/>[CLI]" --> hilo
    hilo -- "Pide contratos JSON<br/>[HTTP, API compatible con OpenAI]" --> llm
    hilo -. "Si el local falla y el respaldo<br/>está activo [HTTPS]" .-> claude

    classDef person fill:#08427b,color:#fff,stroke:#052e56
    classDef system fill:#1168bd,color:#fff,stroke:#0b4884
    classDef external fill:#999,color:#fff,stroke:#6b6b6b
    class persona,investigador person
    class hilo system
    class llm,claude external
```

- **Personas.** Hilo es un prototipo de trabajo de grado. Lo usan miembros de un equipo que
  trabaja un reto de innovación, cada uno con su cuenta local, y el investigador, que además
  lo evalúa desde la línea de comandos.
- **Servidor del modelo local.** Es otro programa (`llama-server`), con su propio ciclo de vida
  y su GPU. Hilo lo trata como un sistema externo: si no está, Hilo no puede guiar el turno.
- **API de Claude.** Es opcional (`RUTA_DIA_RESPALDO_CLAUDE`) y tiene un tope de gasto
  (`RUTA_DIA_CLAUDE_TOPE_USD`). Lo que se le envía sale del equipo, y el consentimiento
  informado de las pruebas debe decirlo.
- **Lo que no hay.** No hay proveedores de identidad, correo, avisos del sistema operativo ni
  RAG vectorial. La metodología vive dentro del repositorio.

---

## Nivel 2 · Contenedores

En C4, un *contenedor* es una unidad que se ejecuta o que guarda datos, no necesariamente un
contenedor Docker. Hilo es un **monolito modular**: un solo proceso de Python sirve la API, los
agentes y la interfaz ya compilada.

```mermaid
flowchart TB
    persona["<b>Persona del equipo</b><br/>[Persona]"]
    investigador["<b>Investigador</b><br/>[Persona]"]

    subgraph hilo["Hilo [Sistema de software]"]
        direction TB
        spa["<b>Interfaz web</b><br/>[Contenedor: TypeScript + Vite, en el navegador]<br/>Inicio, chat, Post-its, agenda, calendario,<br/>tableros y práctica de entrevista"]
        app["<b>Aplicación Hilo</b><br/>[Contenedor: Python 3.13, FastAPI, Uvicorn, LangGraph]<br/>API, cuentas, proyectos, grafo de agentes,<br/>verificación y archivos de la interfaz"]
        cli["<b>Línea de comandos</b><br/>[Contenedor: Python, comando hilo]<br/>Turnos sueltos, conversación interactiva<br/>y baterías de evaluación"]
        conocimiento[("<b>Base metodológica</b><br/>[Almacén: JSON + Markdown versionados]<br/>Ruta de 10 etapas, 15 fichas,<br/>partes de cada ficha y marcos")]
        cuentas[("<b>Base de cuentas y colaboración</b><br/>[Almacén: SQLite auth.sqlite3]<br/>Usuarios, sesiones, invitaciones, miembros,<br/>avances y tableros compartidos")]
        cuadernos[("<b>Cuadernos por cuenta</b><br/>[Almacén: SQLite notebooks.sqlite3]<br/>Turnos, campos verificados, avance,<br/>Post-its, tareas y prácticas")]
        checkpoints[("<b>Checkpoints del grafo</b><br/>[Almacén: SQLite checkpoints.sqlite3]<br/>Estado técnico de LangGraph,<br/>thread_id = cuaderno")]
        auditoria[("<b>Auditoría</b><br/>[Almacén: archivos JSONL]<br/>Un registro por veredicto<br/>del Verificador")]
    end

    llm["<b>Servidor del modelo local</b><br/>[Sistema externo: llama.cpp]"]
    claude["<b>API de Claude</b><br/>[Sistema externo]"]

    persona -- "Usa [HTTPS o HTTP local]" --> spa
    spa -- "Llama a la API<br/>[JSON/HTTP · cookie de sesión]<br/>y recibe el turno [SSE]" --> app
    app -- "Entrega index.html y recursos [HTTP]" --> spa
    investigador -- "Ejecuta [terminal]" --> cli
    app -- "Lee [archivos]" --> conocimiento
    app -- "Lee y escribe [sqlite3]" --> cuentas
    app -- "Lee y escribe [sqlite3]" --> cuadernos
    app -- "Lee y escribe [SqliteSaver]" --> checkpoints
    app -- "Agrega [JSONL]" --> auditoria
    app -- "JSON Schema estricto<br/>[HTTP 127.0.0.1:18083/v1]" --> llm
    cli -- "Mismos módulos: lee la metodología,<br/>usa cuadernos, checkpoints y auditoría<br/>y llama al modelo" --> conocimiento
    app -. "Respaldo [HTTPS, salida estructurada]" .-> claude

    classDef person fill:#08427b,color:#fff,stroke:#052e56
    classDef container fill:#438dd5,color:#fff,stroke:#2e6295
    classDef store fill:#438dd5,color:#fff,stroke:#2e6295
    classDef external fill:#999,color:#fff,stroke:#6b6b6b
    class persona,investigador person
    class spa,app,cli container
    class conocimiento,cuentas,cuadernos,checkpoints,auditoria store
    class llm,claude external
```

| Contenedor | Tecnología | Responsabilidad | Dónde está |
|---|---|---|---|
| Interfaz web | TypeScript, Vite, pnpm | Pantallas y tableros; no habla con el modelo | `frontend/` |
| Aplicación Hilo | Python, FastAPI, Uvicorn, LangGraph, Pydantic | API, sesión, permisos, grafo, verificación, colas | `src/hilo/` (entrada `web.py`) |
| Línea de comandos | Python (`hilo`) | Turnos e interacción sin interfaz, evaluación | `src/hilo/cli.py`, `scripts/` |
| Base metodológica | JSON y Markdown | Fuente única de lo que Hilo dice de cada herramienta | `knowledge/`, `conocimiento/partes_fichas.json` |
| Cuentas y colaboración | SQLite | Identidad y proyectos compartidos | `<datos>/auth.sqlite3` |
| Cuadernos | SQLite, uno por cuenta | Memoria del proyecto y prácticas | `<datos>/users/<id>/` |
| Checkpoints | SQLite (LangGraph) | Reanudar el hilo de cada cuaderno | junto a los cuadernos |
| Auditoría | JSONL | Trazabilidad de cada veredicto | `<datos>/users/<id>/verifications.jsonl`, `data/` |

La línea de comandos importa los mismos módulos que la aplicación y usa los mismos almacenes y
el mismo modelo; el diagrama dibuja una sola flecha para no repetir las de la aplicación.

`<datos>` es `%LOCALAPPDATA%\RutaDIA` en Windows, `~/.local/share/RutaDIA` en Linux o
`RUTA_DIA_DATA_DIR` si se define. En la imagen Docker es `/datos`.

---

## Nivel 3 · Componentes de la aplicación Hilo

Cada componente corresponde a un **contexto delimitado** de `src/hilo/`
([dominio-ddd.md](dominio-ddd.md)). La prueba `tests/test_arquitectura.py` hace cumplir las
dependencias que muestra este diagrama: si un módulo importa un contexto que no le corresponde,
falla.

```mermaid
flowchart TB
    spa["<b>Interfaz web</b><br/>[Contenedor]"]
    cli["<b>Línea de comandos</b><br/>[Contenedor]"]

    subgraph app["Aplicación Hilo [Contenedor: Python]"]
        direction TB
        web["<b>Capa de entrada HTTP</b><br/>[Componente: web.py, FastAPI]<br/>Rutas /api, SSE del chat, sesión por cookie,<br/>permisos de proyecto, límite de intentos,<br/>hosts de confianza y tamaño de cuerpo"]
        config["<b>Configuración</b><br/>[Componente: config.py]<br/>Lee las variables RUTA_DIA_* y HILO_*"]

        subgraph nucleo["Acompañamiento · núcleo"]
            grafo["<b>Grafo del turno</b><br/>[Componente: langgraph_workflow.py]<br/>orchestrate → plan → guide → verify<br/>→ finalize · retry · degrade · knowledge_gap"]
            agentes["<b>Agentes</b><br/>[Componente: direct_runtime.py, variantes.py]<br/>Orquestador y Metodólogo; variantes de ablación"]
            plan["<b>Planificador</b><br/>[Componente: planificador.py]<br/>Decide en código qué parte de la ficha<br/>toca según el avance guardado"]
            verif["<b>Verificador</b><br/>[Componente: guardrails.py, runtime.grounded_verdict]<br/>Controles deterministas de contrato,<br/>ficha, evidencia y repetición"]
            sens["<b>Filtro sensible</b><br/>[Componente: sensitive.py]<br/>Crisis y datos personales con texto fijo"]
            audit["<b>Auditoría</b><br/>[Componente: audit.py]"]
        end

        conoc["<b>Conocimiento</b><br/>[Componente: conocimiento/knowledge.py]<br/>Carga ruta, fichas, secciones y partes;<br/>solo lectura"]
        herr["<b>Herramientas</b><br/>[Componente: herramientas/*]<br/>Árbol de problemas, diagnóstico, cinco porqués,<br/>PESTEL, mapa de empatía, recorrido"]
        proy["<b>Proyectos</b><br/>[Componente: proyectos/*]<br/>Cuaderno y memoria, Post-its, tareas,<br/>proyectos compartidos con versión"]
        ident["<b>Identidad</b><br/>[Componente: identidad/auth.py]<br/>Cuentas con scrypt, sesiones con token<br/>guardado como SHA-256"]
        prac["<b>Práctica</b><br/>[Componente: practica/*]<br/>Cliente simulado y registro aparte"]
        infer["<b>Inferencia</b><br/>[Componente: inferencia/*]<br/>Adaptador local, respaldo con Claude,<br/>ModelQueue y ProjectLocks"]
        evalu["<b>Evaluación</b><br/>[Componente: evaluacion/*]<br/>Métricas para la investigación"]
    end

    conocimientoDB[("Base metodológica")]
    sqlite[("SQLite: cuentas, cuadernos,<br/>checkpoints")]
    jsonl[("Auditoría JSONL")]
    llm["Servidor del modelo local"]
    claude["API de Claude"]

    spa -- "JSON/HTTP · SSE" --> web
    cli --> grafo & evalu
    web --> grafo & conoc & herr & proy & ident & prac & infer
    web -. lee .-> config
    grafo --> agentes & plan & verif & sens & audit
    agentes -- "lenguaje publicado" --> conoc
    agentes -- "capa anticorrupción" --> infer
    plan --> conoc
    verif --> conoc
    prac --> infer
    proy -- "conformista" --> herr
    evalu --> grafo
    conoc --> conocimientoDB
    proy & ident & prac --> sqlite
    grafo -- "checkpoints" --> sqlite
    audit --> jsonl
    infer --> llm
    infer -.-> claude

    classDef container fill:#438dd5,color:#fff,stroke:#2e6295
    classDef component fill:#85bbf0,color:#000,stroke:#5d82a8
    classDef external fill:#999,color:#fff,stroke:#6b6b6b
    classDef store fill:#438dd5,color:#fff,stroke:#2e6295
    class spa,cli container
    class web,config,grafo,agentes,plan,verif,sens,audit,conoc,herr,proy,ident,prac,infer,evalu component
    class llm,claude external
    class conocimientoDB,sqlite,jsonl store
```

Falta un componente en el dibujo: **Compartido** (`compartido/`), con los contratos Pydantic y
los errores de dominio. Todos los contextos dependen de él, así que se omite para no cargar el
diagrama con esas flechas.

| Componente | Responsabilidad | Interfaz principal |
|---|---|---|
| Capa de entrada HTTP | Traduce HTTP a llamadas de los contextos y los `ErrorDeDominio` a códigos HTTP. Arma un turno por petición en un hilo aparte y lo transmite por SSE | `create_app`, `run_server`, `POST /api/chat` |
| Grafo del turno | Decide el orden, las bifurcaciones y el único reintento | `LangGraphRutaDia` |
| Agentes | Llaman al modelo con un contexto aislado por rol y validan la salida con Pydantic | `DirectOpenAIRuntime`, `VARIANTES` |
| Planificador | Elige preguntar, aclarar o cerrar y qué parte se trabaja, a partir del avance guardado | `planear` → `Plan` |
| Verificador | Protege las invariantes del dominio; con dos rechazos, el turno se degrada | `validate_handoff`, `validate_candidate`, `grounded_verdict` → `Verdict` |
| Conocimiento | Expone la metodología como datos | `RouteDefinition`, `partes_de` |
| Herramientas | Forma y reglas de cada tablero | `problem_tree`, `why_analysis`, `pestel`… |
| Proyectos | Agregados Proyecto y Proyecto compartido | `NotebookMemory`, `SharingStore` |
| Identidad | Agregado Cuenta | `AuthStore` |
| Práctica | Entrevista con el Cliente simulado; nunca es evidencia | `cliente_simulado`, `RegistroPracticas` |
| Inferencia | Única puerta al modelo; reparte las ranuras y bloquea un proyecto por turno | `llamar_modelo_local`, `ConClaude`, `ModelQueue`, `ProjectLocks` |
| Evaluación | Baterías y métricas; la web no la usa | `evaluation` |

---

## Nivel 4 · Código

C4 recomienda dibujar este nivel solo donde aporta. En Hilo, el único lugar donde aporta es el
grafo del turno ([`langgraph_workflow.py`](../src/hilo/acompanamiento/langgraph_workflow.py)):

```mermaid
flowchart LR
    S((START)) --> O[orchestrate<br/>Orquestador → HandoffContract]
    O -->|herramienta activa| P[plan<br/>Planificador → Plan]
    O -->|etapa sin ficha| G[knowledge_gap]
    P --> M[guide<br/>Metodólogo → CandidateResponse]
    M --> V[verify<br/>Verificador → Verdict]
    V -->|aprobado| F[finalize<br/>TurnResult]
    V -->|rechazo, intento 1| M
    V -->|rechazo, intento 2| D[degrade<br/>respuesta segura]
    G --> E((END))
    F --> E
    D --> E
```

Los contratos entre nodos (`HandoffContract`, `Plan`, `CandidateResponse`, `Verdict`,
`TurnResult`, `ProjectState`) están en
[`compartido/contracts.py`](../src/hilo/compartido/contracts.py). El resto del código se lee
mejor directamente; el mapa de módulos por contexto está en [dominio-ddd.md](dominio-ddd.md).

---

## Diagrama complementario · despliegue

Hilo se ejecuta de tres formas. Las tres usan el mismo código y solo cambian la configuración.

```mermaid
flowchart TB
    subgraph local["A · Instalación local (Windows o Linux)"]
        direction LR
        nav1["Navegador"] -- "HTTP 127.0.0.1:8787" --> app1["Aplicación Hilo<br/>[Uvicorn]"]
        app1 -- "HTTP 127.0.0.1:18083" --> llm1["llama-server + Qwen3.5-4B<br/>[GPU del mismo equipo]"]
        app1 --> d1[("Carpeta de datos<br/>%LOCALAPPDATA%\RutaDIA")]
    end

    subgraph servidor["B · Servidor del equipo (Ubuntu 24.04 ARM64)"]
        direction LR
        nav2["Navegador remoto"] -- "HTTP(S) según nginx" --> nginx["nginx<br/>[proxy reverso del servidor,<br/>configurado fuera del repositorio]"]
        nginx -- "HTTP 127.0.0.1:8787" --> app2["Aplicación Hilo<br/>[systemd hoy · Docker planeado,<br/>red del host, solo lectura]"]
        app2 --> d2[("~/hilo/datos<br/>[volumen /datos]")]
        app2 -- "127.0.0.1:18083<br/>[túnel SSH inverso]" --> llm2["llama-server<br/>[computador con GPU del equipo,<br/>scripts/prestar_modelo.sh]"]
        app2 -. "si el túnel está cerrado [HTTPS]" .-> claude2["API de Claude"]
    end

    subgraph tunel["C · Acceso temporal desde otro computador"]
        direction LR
        nav3["Navegador remoto"] -- "HTTPS *.trycloudflare.com" --> cf["cloudflared<br/>[túnel rápido]"]
        cf -- "HTTP 127.0.0.1:8787" --> app3["Aplicación Hilo<br/>[instalación local A]"]
    end
```

- **A · Local.** Es el modo documentado en el README: todo escucha en `127.0.0.1` y nada sale
  del equipo.
- **B · Servidor.** Hilo corre detrás del nginx del servidor. El modelo no va en el servidor:
  llega por un túnel SSH cuya llave solo puede abrir `127.0.0.1:18083`. Si el túnel se cierra,
  responde el respaldo con Claude, si está activo. El paso a Docker está preparado y probado
  ([contenedores.md](contenedores.md)).
- **C · Túnel rápido.** `scripts/abrir_tunel.sh` publica la instalación local con una dirección
  `trycloudflare.com` que cambia cada vez. Crear una cuenta desde afuera exige un código de
  invitación, y el registro y el inicio de sesión tienen un cupo de intentos por minuto.

---

## Diagrama complementario · un turno de chat

```mermaid
sequenceDiagram
    autonumber
    actor P as Persona
    participant UI as Interfaz web
    participant W as web.py
    participant Q as ModelQueue / ProjectLocks
    participant G as Grafo LangGraph
    participant LLM as llama-server (o Claude)
    participant DB as SQLite y JSONL

    P->>UI: Escribe un mensaje
    UI->>W: POST /api/chat (cookie de sesión)
    W->>W: Comprueba sesión y permiso sobre el proyecto
    W->>Q: Bloquea el proyecto (409 si ya responde)
    W-->>UI: Abre el flujo SSE
    W->>Q: Pide ranura del modelo
    Q-->>UI: Evento «en fila», con cuántos faltan
    W->>DB: Carga ProjectState del cuaderno
    W->>G: invoke(mensaje, estado, thread_id = cuaderno)
    G->>LLM: Orquestador (JSON Schema)
    G-->>UI: Evento de nodo
    G->>G: Planificador decide la parte (código)
    G->>LLM: Metodólogo (JSON Schema)
    G->>G: Verificador (código)
    alt rechazo en el primer intento
        G->>LLM: Metodólogo con los hallazgos
        G->>G: Verificador
    end
    G->>DB: Checkpoint y auditoría del veredicto
    W->>DB: Guarda el turno, los campos validados y el avance
    W-->>UI: Evento final con TurnResult
    W->>Q: Libera la ranura y el proyecto
    UI-->>P: Muestra la respuesta, el veredicto y el avance
```
