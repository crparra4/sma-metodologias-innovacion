"""Acompañamiento metodológico: el dominio central de Hilo.

Recibe el mensaje de la persona y decide, turno a turno, qué parte de la herramienta se trabaja y
qué respuesta se muestra. Agentes: Orquestador, Planificador (`planificador.py`), Metodólogo y
Verificador (`guardrails.py` y las reglas de `runtime.py`); el camino de cada turno está fijo en
`langgraph_workflow.py`. Lenguaje: turno, pedido, ficha activa, parte, plan, respuesta candidata,
veredicto, hallazgo.

Depende de: compartido, conocimiento (lee las fichas) e inferencia (pide texto al modelo, siempre
a través de `DirectOpenAIRuntime._llamar` y de los contratos, que hacen de capa anticorrupción).
"""
