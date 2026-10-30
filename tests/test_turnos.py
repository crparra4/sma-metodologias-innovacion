import threading
import time

import pytest

from hilo.inferencia.turnos import ModelQueue, ProjectLocks


def test_queue_admits_up_to_its_slots_and_then_waits_in_arrival_order():
    queue = ModelQueue(2)
    assert queue.acquire(timeout=0) and queue.acquire(timeout=0)
    assert not queue.acquire(timeout=0.05)  # lleno: se rinde al vencer el plazo
    order, places = [], {}

    def wait(name):
        assert queue.acquire(timeout=5, on_wait=lambda ahead: places.setdefault(name, ahead))
        order.append(name)

    threads = []
    for name in ("primera", "segunda"):
        threads.append(threading.Thread(target=wait, args=(name,)))
        threads[-1].start()
        while name not in places:
            time.sleep(0.01)
    assert places == {"primera": 1, "segunda": 2}
    assert queue.snapshot() == {"slots": 2, "active": 2, "waiting": 2}
    queue.release()
    threads[0].join(timeout=5)
    assert order == ["primera"]
    queue.release()
    threads[1].join(timeout=5)
    assert order == ["primera", "segunda"]
    queue.release()
    queue.release()
    assert queue.snapshot() == {"slots": 2, "active": 0, "waiting": 0}


def test_waiting_turn_hears_from_the_queue_even_if_its_place_does_not_change():
    queue = ModelQueue(1)
    assert queue.acquire(timeout=0)
    reports = []
    assert not queue.acquire(timeout=0.25, on_wait=reports.append, heartbeat=0.05)
    assert len(reports) >= 3 and set(reports) == {1}
    assert queue.snapshot()["waiting"] == 0


def test_queue_needs_at_least_one_slot():
    with pytest.raises(ValueError):
        ModelQueue(0)


def test_project_lock_is_per_project():
    locks = ProjectLocks()
    assert locks.acquire("a") and not locks.acquire("a")
    assert locks.acquire("b") and locks.busy("a") and locks.any_busy()
    locks.release("a")
    locks.release("b")
    assert not locks.busy("a") and not locks.any_busy()
