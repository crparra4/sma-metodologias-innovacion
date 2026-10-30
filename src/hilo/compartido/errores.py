"""Errores del dominio, sin depender del framework web.

Los contextos los lanzan con un mensaje para la persona; la capa web (`web.py`) los traduce a
la respuesta HTTP con el estado de cada clase. Así el dominio no importa FastAPI.
"""

from __future__ import annotations


class ErrorDeDominio(Exception):
    """Regla del dominio que impide la operación; `mensaje` se muestra tal cual."""

    estado = 400

    def __init__(self, mensaje: str):
        super().__init__(mensaje)
        self.mensaje = mensaje


class NoEncontrado(ErrorDeDominio):
    estado = 404


class Conflicto(ErrorDeDominio):
    estado = 409


class SinPermiso(ErrorDeDominio):
    estado = 403
