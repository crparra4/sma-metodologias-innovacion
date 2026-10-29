"""Inferencia: el acceso a los modelos de lenguaje.

Adaptadores hacia el servidor del modelo local (`modelo_local.py`, API compatible con OpenAI) y
hacia la API de Claude como respaldo (`respaldo_claude.py`), y la fila que reparte el modelo
entre varias personas (`turnos.py`). Subdominio genérico y aguas arriba: no conoce agentes, fichas
ni proyectos. Es el primer candidato a servicio independiente.

Depende de: ninguno (solo la configuración).
"""
