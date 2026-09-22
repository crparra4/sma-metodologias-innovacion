# Decisión de arquitectura · versión 0.1

## Qué se conserva de las figuras

- Cliente → API → capa de orquestación → persistencia/conocimiento.
- Tres roles: Orquestador, Metodólogo y Verificador.
- Divulgación progresiva de máximo tres herramientas.
- Memoria aislada por cuaderno y biblioteca institucional de solo lectura.
- Verificación estructural y semántica, con un único reintento.

## Mejora aplicada

Los tres agentes **no forman una conversación autónoma abierta**. Un servicio de aplicación
controla el orden, selecciona exactamente qué contexto recibe cada rol y valida sus salidas con
modelos Pydantic. Esta decisión mejora la arquitectura por cuatro razones:

1. Evita que CrewAI decida por sí solo el flujo crítico o delegue tareas fuera del diseño.
2. Hace posible probar cada frontera con datos sintéticos y sin consumir tokens.
3. Garantiza que el Orquestador vea solo el índice y que los otros roles vean una sola ficha.
4. Permite registrar cada dictamen y degradar con honestidad después del segundo rechazo.

CrewAI sigue siendo el motor de razonamiento y creación de los tres agentes. El flujo determinista
actúa como la capa de seguridad y auditoría alrededor del modelo, no como un cuarto agente.

## Flujo de un turno

```text
mensaje + estado
      │
      ▼
Orquestador ──Contrato 1──► filtro de ruta
                                  │
                                  ▼
                            carga 1 ficha
                                  │
                                  ▼
Metodólogo ──Contrato 2──► filtro estructural ──► Verificador
                                  ▲                    │
                                  └── 1 reintento ─────┘
                                                       │
                                         Contrato 3 + auditoría
                                                       │
                                                       ▼
                                                respuesta al usuario
```

## Siguientes incrementos

1. Persistencia SQLite de usuarios, cuadernos, turnos, plantillas, verificaciones y mediciones.
2. API FastAPI sobre el servicio ya probado.
3. Interfaz React/Vite administrada con pnpm.
4. Incorporación y validación experta de las fichas todavía faltantes.

