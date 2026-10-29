"""Núcleo compartido (DDD): lo que varios contextos usan con el mismo significado.

Los contratos entre agentes (`contracts.py`, validados con Pydantic) y los errores del dominio
(`errores.py`), que la capa web traduce a HTTP. No depende de ningún otro contexto; cambiar algo
aquí afecta a todos, por eso se cambia poco y con pruebas.
"""
