"""Turnos para el modelo cuando varias personas usan Hilo a la vez.

El modelo local atiende varias peticiones juntas (ranuras de llama-server), pero no infinitas.
`ModelQueue` deja pasar tantas generaciones como ranuras haya y pone a las demás en fila, en
orden de llegada. `ProjectLocks` evita que un mismo proyecto genere dos veces a la vez: las
dos respuestas escribirían sobre el mismo hilo de LangGraph y la misma memoria.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from collections.abc import Callable


class ModelQueue:
    """Cupos del modelo con fila de espera en orden de llegada."""

    def __init__(self, slots: int):
        if slots < 1:
            raise ValueError("El modelo necesita al menos una ranura.")
        self.slots = slots
        self._active = 0
        self._waiting: deque[object] = deque()
        self._condition = threading.Condition()

    def acquire(
        self,
        timeout: float | None = None,
        on_wait: Callable[[int], None] | None = None,
        heartbeat: float | None = None,
    ) -> bool:
        """Espera un cupo.

        `on_wait` recibe cuántas respuestas faltan por terminar antes de entrar, cada vez que
        cambia y, con `heartbeat`, al menos cada tantos segundos: así una conexión en espera
        no queda muda.
        """
        ticket = object()
        deadline = None if timeout is None else time.monotonic() + timeout
        with self._condition:
            self._waiting.append(ticket)
            reported, reported_at = None, 0.0
            while not (self._waiting[0] is ticket and self._active < self.slots):
                ahead = max(self._waiting.index(ticket) + self._active - self.slots + 1, 1)
                now = time.monotonic()
                stale = heartbeat is not None and now - reported_at >= heartbeat
                if on_wait is not None and (ahead != reported or stale):
                    reported, reported_at = ahead, now
                    on_wait(ahead)
                remaining = None if deadline is None else deadline - now
                if remaining is not None and remaining <= 0:
                    self._waiting.remove(ticket)
                    self._condition.notify_all()
                    return False
                waits = [value for value in (remaining, heartbeat) if value is not None]
                self._condition.wait(min(waits) if waits else None)
            self._waiting.popleft()
            self._active += 1
            self._condition.notify_all()
            return True

    def release(self) -> None:
        with self._condition:
            self._active -= 1
            self._condition.notify_all()

    def snapshot(self) -> dict:
        with self._condition:
            return {"slots": self.slots, "active": self._active, "waiting": len(self._waiting)}


class ProjectLocks:
    """Una generación o cambio de memoria a la vez por proyecto."""

    def __init__(self):
        self._lock = threading.Lock()
        self._busy: set[str] = set()

    def acquire(self, project_id: str) -> bool:
        with self._lock:
            if project_id in self._busy:
                return False
            self._busy.add(project_id)
            return True

    def release(self, project_id: str) -> None:
        with self._lock:
            self._busy.discard(project_id)

    def busy(self, project_id: str) -> bool:
        with self._lock:
            return project_id in self._busy

    def any_busy(self) -> bool:
        with self._lock:
            return bool(self._busy)
