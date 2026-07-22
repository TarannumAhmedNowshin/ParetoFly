"""Per-session logging for the ParetoFly pipeline.

Every application log flows through the ``paretofly`` logger namespace. A single
:class:`_SessionRoutingHandler` attached to that logger fans each record out to:

* ``logs/app.log``           — combined rolling log across *all* searches.
* ``logs/<session_id>.log``  — one file per search session, so a single run can
                               be inspected next to its ``reports/<id>_report.md``.
* the console (stderr)       — live feedback at ``INFO`` and above.

Session binding uses a :class:`contextvars.ContextVar`, so any module can simply
call ``get_logger("<area>")`` and log without threading a ``session_id`` through
every function signature. The active session is set by:

* :func:`bind_session` — a context manager used at the top level (API request /
  CLI run) that also flushes and closes the session file when the run ends.
* :func:`set_session`  — a lightweight setter each graph node calls at entry so
  logging keeps working even when LangGraph runs a node in a worker thread.

To carry the session into the enrichment thread pool, copy the current context
(``contextvars.copy_context()``) and submit work via ``ctx.run(...)``.
"""

from __future__ import annotations

import contextvars
import logging
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

ROOT_LOGGER_NAME = "paretofly"
_LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_session_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "paretofly_session_id", default=None
)

_configure_lock = threading.Lock()
_handler_lock = threading.Lock()
_configured = False
_session_handlers: dict[str, logging.FileHandler] = {}


def logs_dir() -> Path:
    """Resolve (and create) the repo-root ``logs`` directory."""

    path = Path("logs")
    path.mkdir(parents=True, exist_ok=True)
    return path


def _session_file_handler(session_id: str) -> Optional[logging.FileHandler]:
    """Return a cached file handler for ``session_id`` (created on first use)."""

    handler = _session_handlers.get(session_id)
    if handler is not None:
        return handler
    with _handler_lock:
        handler = _session_handlers.get(session_id)
        if handler is None:
            try:
                handler = logging.FileHandler(
                    logs_dir() / f"{session_id}.log", encoding="utf-8"
                )
            except OSError:  # pragma: no cover - unwritable log dir must not crash a search
                return None
            handler.setFormatter(logging.Formatter(_LOG_FORMAT, _DATE_FORMAT))
            _session_handlers[session_id] = handler
    return handler


class _SessionRoutingHandler(logging.Handler):
    """Route each record to the active session's file (when one is bound)."""

    def emit(self, record: logging.LogRecord) -> None:
        session_id = getattr(record, "session_id", None) or _session_id_var.get()
        if not session_id:
            return
        handler = _session_file_handler(session_id)
        if handler is not None:
            handler.handle(record)


def configure_logging(console_level: int = logging.INFO) -> logging.Logger:
    """Idempotently attach the app-log, console, and session-routing handlers."""

    global _configured
    logger = logging.getLogger(ROOT_LOGGER_NAME)
    if _configured:
        return logger
    with _configure_lock:
        if _configured:
            return logger

        logger.setLevel(logging.DEBUG)
        logger.propagate = False
        formatter = logging.Formatter(_LOG_FORMAT, _DATE_FORMAT)

        app_handler = logging.FileHandler(logs_dir() / "app.log", encoding="utf-8")
        app_handler.setLevel(logging.DEBUG)
        app_handler.setFormatter(formatter)
        logger.addHandler(app_handler)

        console = logging.StreamHandler()
        console.setLevel(console_level)
        console.setFormatter(formatter)
        logger.addHandler(console)

        logger.addHandler(_SessionRoutingHandler())

        _configured = True
    return logger


def get_logger(name: str = ROOT_LOGGER_NAME) -> logging.Logger:
    """Return a child of the ``paretofly`` logger (e.g. ``get_logger("graph.search")``)."""

    configure_logging()
    if name == ROOT_LOGGER_NAME or name.startswith(ROOT_LOGGER_NAME + "."):
        return logging.getLogger(name)
    return logging.getLogger(f"{ROOT_LOGGER_NAME}.{name}")


def current_session_id() -> Optional[str]:
    """Return the session id bound to the current context, if any."""

    return _session_id_var.get()


def set_session(session_id: Optional[str]) -> None:
    """Bind ``session_id`` on the current context (safe to call from any thread)."""

    if session_id:
        configure_logging()
        _session_id_var.set(session_id)


@contextmanager
def bind_session(session_id: str) -> Iterator[logging.Logger]:
    """Bind ``session_id`` for the duration of a run and flush its file at the end."""

    configure_logging()
    token = _session_id_var.set(session_id)
    logger = get_logger("session")
    logger.info("session %s: start", session_id)
    try:
        yield logger
    finally:
        logger.info("session %s: end", session_id)
        with _handler_lock:
            handler = _session_handlers.pop(session_id, None)
        if handler is not None:
            handler.close()
        _session_id_var.reset(token)
