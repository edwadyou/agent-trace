"""OpenTelemetry distro: trace any agent with zero code changes.

Registering this class under the ``opentelemetry_distro`` entry-point group is
what makes the zero-code path work::

    OTEL_PYTHON_DISTRO=agent-monitor opentelemetry-instrument python run.py

``opentelemetry-instrument`` injects a ``sitecustomize`` that calls
``auto_instrumentation.initialize()``, which does three things: load the distro
named by ``OTEL_PYTHON_DISTRO`` (falling back to ``DefaultDistro``, which
configures nothing at all), call ``distro.configure()``, then load every
``opentelemetry_instrumentor`` entry point. Nothing in that chain registers an
``opentelemetry_configurator`` for a plain SDK install, so *we* have to build
the TracerProvider here -- without it the process keeps a ``ProxyTracerProvider``
and records nothing.

``auto_instrument`` is deliberately left OFF: the instrumentors are loaded right
after us by ``_load_instrumentors()``, and they pick up the provider we just
installed globally. Doing it twice would only race over the same monkey-patches.

The ``monitor()`` context is entered here and kept open until ``atexit``. That
is the part that makes this "works with any agent": ``monitor()`` is re-entrant,
so a user script that calls ``monitor()`` itself degrades to a no-op instead of
fighting over the single global provider this process is allowed to have.

Configuration is environment-only (there is no CLI hook at this level):

==============================  ===============================================
``AGENT_MONITOR_TRACE_FILE``    default ``latest_traces.jsonl``, relative to CWD
``AGENT_MONITOR_SERVICE_NAME``  default ``OTEL_SERVICE_NAME``, else CWD dir name
``AGENT_MONITOR_EXPORTER``      default ``jsonl`` (``console`` also works)
``AGENT_MONITOR_VERBOSE``       ``1``/``true`` to print the resolved config
==============================  ===============================================

There is no root span in this mode: nothing here can wrap the user's ``main()``,
so each framework root run becomes its own trace. Use
``python -m agent_monitor run`` (or a hand-written ``instrument.py``) when one
trace per run is wanted. Use ``OTEL_PYTHON_DISABLED_INSTRUMENTATIONS`` to keep
unrelated instrumentors out of the export.
"""
from __future__ import annotations

import atexit
import os
import sys
from contextlib import ExitStack
from pathlib import Path
from typing import Any

from opentelemetry.instrumentation.distro import BaseDistro

_TRUTHY = {"1", "true", "yes", "on"}

# The ExitStack holding the process-wide monitor() context open. Module level so
# atexit (and a second, redundant configure() call) can find it.
_STACK: ExitStack | None = None


def _flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in _TRUTHY


def _resolve_config() -> dict[str, Any]:
    """Read the AGENT_MONITOR_* environment, filling in sensible defaults."""
    service_name = (
        os.environ.get("AGENT_MONITOR_SERVICE_NAME")
        or os.environ.get("OTEL_SERVICE_NAME")
        or Path.cwd().name
        or "agent"
    )
    return {
        "service_name": service_name,
        "trace_file": os.environ.get("AGENT_MONITOR_TRACE_FILE") or None,
        "exporter": os.environ.get("AGENT_MONITOR_EXPORTER") or "jsonl",
        "verbose": _flag("AGENT_MONITOR_VERBOSE"),
    }


def _shutdown() -> None:
    """Close the monitor() context that has been open since sitecustomize."""
    global _STACK
    stack, _STACK = _STACK, None
    if stack is None:
        return
    try:
        stack.close()
    except Exception as exc:  # pragma: no cover
        print(f"[agent-monitor distro] shutdown failed: {exc}", file=sys.stderr)


class AgentMonitorDistro(BaseDistro):
    """Install agent_monitor's JSONL exporter as the process-wide backend."""

    def _configure(self, **kwargs: Any) -> None:
        global _STACK
        if _STACK is not None:
            return                      # already configured in this process
        # Deferred on purpose: keeps `import agent_monitor` free of any
        # dependency on opentelemetry-instrumentation.
        from .monitor import monitor

        config = _resolve_config()
        config.update({k: v for k, v in kwargs.items() if v is not None})

        stack = ExitStack()
        try:
            stack.enter_context(
                monitor(
                    service_name=config["service_name"],
                    auto_instrument=False,
                    exporter=config["exporter"],
                    trace_file=config["trace_file"],
                    verbose=config["verbose"],
                )
            )
        except BaseException:
            # Never take the user's process down during auto-initialization.
            stack.close()
            raise
        _STACK = stack
        atexit.register(_shutdown)
        if config["verbose"]:
            print(
                "[agent-monitor distro] tracing to "
                f"{config['trace_file'] or 'latest_traces.jsonl'} "
                f"(service.name={config['service_name']})",
                file=sys.stderr,
            )


__all__ = ["AgentMonitorDistro"]