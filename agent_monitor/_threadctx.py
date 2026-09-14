"""Propagate OpenTelemetry context across thread boundaries.

Why this module exists
----------------------
OpenTelemetry keeps the "current span" in a ``contextvars.ContextVar``.
``asyncio`` copies the context into every ``Task``, so async agent code nests
correctly for free. The stdlib thread primitives do NOT:

* ``concurrent.futures.ThreadPoolExecutor.submit()`` hands the callable to a
  long-lived worker thread, which runs it in the *worker's* (usually empty)
  context;
* ``threading.Thread.start()`` runs ``Thread.run()`` in a brand-new context.

An agent that fans work out over threads therefore emits one orphan trace per
task, even when a root span was injected on the calling thread -- the root span
simply has no way to reach the worker. This module closes that gap the same way
``langchain_core.runnables.config.ContextThreadPoolExecutor`` does: capture
``copy_context()`` at *submit* time and run the callable inside it.

Why not ``opentelemetry-instrumentation-threading``?
---------------------------------------------------
It only patches ``threading.Thread``, capturing the context when the thread is
*created*. Pool workers are created once and reused, so creation-time capture is
the wrong granularity: every task would inherit the first submitter's context
(or an empty one when the pool is built at import time). No official package
patches ``ThreadPoolExecutor.submit`` per task.

Known semantics and limits
--------------------------
* The submitter's span may already have ended by the time the worker runs. That
  is fine for OTel: ``trace_id`` is shared and ``parent_span_id`` is recorded,
  only the timeline in a viewer looks odd.
* ``ContextThreadPoolExecutor`` overrides ``submit`` itself and so does not
  inherit our patch -- no double copy.
* ``Executor.map()`` and ``loop.run_in_executor()`` both funnel through
  ``submit`` and are therefore covered too.
* contextvars cannot cross a *process* boundary. ``multiprocessing`` / Celery
  workers still start their own traces; that needs ``TRACEPARENT`` propagation
  and is out of scope here.
"""
from __future__ import annotations

import functools
import threading
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context

__all__ = ["install", "uninstall", "is_installed"]

# Attribute used to recognise our own patch, so a second install() -- or another
# library that already patched the same method -- never wraps twice.
_MARKER = "_agent_monitor_patched"

_LOCK = threading.Lock()
_INSTALLED = False
_ORIG_SUBMIT = None
_ORIG_START = None


def is_installed() -> bool:
    """True while this module's patches are in place."""
    return _INSTALLED


def _patched_submit(original):
    def submit(self, fn, *args, **kwargs):
        # copy_context() at SUBMIT time, not at pool-creation time: each task
        # must see the span that was current for its own submitter.
        ctx = copy_context()
        return original(self, functools.partial(ctx.run, fn, *args, **kwargs))

    submit.__qualname__ = "ThreadPoolExecutor.submit"
    submit.__doc__ = original.__doc__
    setattr(submit, _MARKER, True)
    return submit


def _patched_start(original):
    def start(self):
        ctx = copy_context()
        original_run = self.run
        # An instance attribute shadows Thread.run(); Thread._bootstrap_inner
        # calls self.run(), so the whole body executes inside the copied context.
        try:
            self.run = functools.partial(ctx.run, original_run)
        except (AttributeError, TypeError):  # pragma: no cover - exotic subclass
            return original(self)
        try:
            return original(self)
        except BaseException:
            # e.g. RuntimeError("threads can only be started once"): leave the
            # object exactly as we found it.
            self.run = original_run
            raise

    start.__qualname__ = "Thread.start"
    start.__doc__ = original.__doc__
    setattr(start, _MARKER, True)
    return start


def install() -> bool:
    """Patch the stdlib thread primitives. Returns True if THIS call did it.

    Idempotent: a second call returns False and changes nothing. Also returns
    False when somebody else already patched these methods, so we never stack a
    second context copy and never uninstall a patch we do not own.
    """
    global _INSTALLED, _ORIG_SUBMIT, _ORIG_START
    with _LOCK:
        if _INSTALLED:
            return False
        current_submit = ThreadPoolExecutor.submit
        current_start = threading.Thread.start
        if getattr(current_submit, _MARKER, False) or getattr(
            current_start, _MARKER, False
        ):  # pragma: no cover - defensive, another library owns the patch
            return False
        _ORIG_SUBMIT = current_submit
        _ORIG_START = current_start
        ThreadPoolExecutor.submit = _patched_submit(current_submit)
        threading.Thread.start = _patched_start(current_start)
        _INSTALLED = True
        return True


def uninstall() -> None:
    """Restore the original ``submit`` / ``start``. Safe when not installed.

    Instance attributes already written onto started ``Thread`` objects are left
    alone: those threads are running (or finished) inside a copied context,
    which is harmless.
    """
    global _INSTALLED, _ORIG_SUBMIT, _ORIG_START
    with _LOCK:
        if not _INSTALLED:
            return
        if _ORIG_SUBMIT is not None:
            ThreadPoolExecutor.submit = _ORIG_SUBMIT
        if _ORIG_START is not None:
            threading.Thread.start = _ORIG_START
        _ORIG_SUBMIT = None
        _ORIG_START = None
        _INSTALLED = False