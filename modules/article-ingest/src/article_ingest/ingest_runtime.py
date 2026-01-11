from __future__ import annotations

import signal
import threading
from typing import Any

from .run_logger import RunLogger


def heartbeat_loop(
    stop_event: threading.Event,
    logger: RunLogger,
    interval_seconds: float,
) -> None:
    while not stop_event.wait(interval_seconds):
        logger.log("heartbeat")


def start_heartbeat(
    logger: RunLogger, interval_seconds: float
) -> tuple[threading.Event, threading.Thread]:
    stop_event = threading.Event()
    thread = threading.Thread(
        target=heartbeat_loop,
        args=(stop_event, logger, interval_seconds),
        daemon=True,
    )
    thread.start()
    return stop_event, thread


def stop_heartbeat(stop_event: threading.Event, thread: threading.Thread) -> None:
    stop_event.set()
    thread.join(timeout=1)


class RunSignalHandler:
    def __init__(self, logger: RunLogger) -> None:
        self._logger = logger
        self._previous_handlers: dict[int, Any] = {}
        self.interrupted = False

    def __enter__(self) -> "RunSignalHandler":
        self._install(signal.SIGTERM)
        self._install(signal.SIGINT)
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        for signum, handler in self._previous_handlers.items():
            signal.signal(signum, handler)
        return False

    def _install(self, signum: signal.Signals) -> None:
        self._previous_handlers[int(signum)] = signal.getsignal(signum)
        signal.signal(signum, self._handle)

    def _handle(self, signum, frame) -> None:
        self.interrupted = True
        name = signal.Signals(signum).name
        self._logger.log(f"run interrupted signal={name}")
        raise KeyboardInterrupt
