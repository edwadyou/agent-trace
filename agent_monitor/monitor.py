from __future__ import annotations
import json
import os
from contextlib import contextmanager
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Generator, Optional
from opentelemetry import trace as otel_trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from .console_exporter import ConsoleSpanExporter


def _load_dotenv() -> None:
    """Load the active project's .env without overriding real environment vars."""
    env_path = Path.cwd() / ".env"
    if not env_path.is_file():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and not os.environ.get(key, "").strip():
            os.environ[key] = value


_load_dotenv()

@contextmanager
def monitor(service_name="agent", *, auto_instrument=False, instrumentors=None, verbose=False):
    exporter = ConsoleSpanExporter(service_name=service_name)
    processor = SimpleSpanProcessor(exporter)
    provider = TracerProvider()
    provider.add_span_processor(processor)
    _instrumented = []
    try:
        otel_trace.set_tracer_provider(provider)
        if auto_instrument:
            _instrumented = _auto_instrument(tracer_provider=provider, instrumentors=instrumentors, verbose=verbose)
        yield otel_trace.get_tracer(service_name)
    finally:
        for inst in _instrumented:
            try: inst.uninstrument()
            except Exception: pass
        processor.force_flush()
        processor.shutdown()
        provider.shutdown()

def trace(service_name="agent", *, auto_instrument=False, instrumentors=None, verbose=False):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            with monitor(service_name=service_name, auto_instrument=auto_instrument, instrumentors=instrumentors, verbose=verbose):
                return func(*args, **kwargs)
        return wrapper
    return decorator

def span(name, *, kind="UNKNOWN", capture_input=True, capture_output=True, attributes=None):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            tracer = otel_trace.get_tracer(__name__)
            span_attrs = {"openinference.span.kind": kind.upper()}
            if attributes:
                span_attrs.update(attributes)
            with tracer.start_as_current_span(name, attributes=span_attrs) as s:
                if capture_input and args:
                    val = args[0] if len(args) == 1 else args
                    s.set_attribute("input.value", _safe_serialize(val))
                if capture_output:
                    result = func(*args, **kwargs)
                    if result is not None:
                        s.set_attribute("output.value", _safe_serialize(result))
                    return result
                return func(*args, **kwargs)
        return wrapper
    return decorator

def _safe_serialize(obj):
    if isinstance(obj, str):
        return obj
    try:
        return json.dumps(obj, ensure_ascii=False, default=str)
    except Exception:
        return str(obj)

def _auto_instrument(*, tracer_provider, instrumentors=None, verbose=False):
    from importlib.metadata import entry_points
    installed = []
    try:
        eps = entry_points(group="openinference_instrumentor")
    except TypeError:
        eps = entry_points().get("openinference_instrumentor", [])
    for ep in eps:
        if instrumentors is not None and ep.name not in instrumentors:
            continue
        try:
            inst_cls = ep.load()
            inst = inst_cls()
            inst.instrument(tracer_provider=tracer_provider)
            installed.append(inst)
            if verbose:
                print(f"  [monitor] Auto-instrumented: {ep.name}")
        except Exception as e:
            if verbose:
                print(f"  [monitor] Skipped {ep.name}: {e}")
    if verbose and not installed:
        print("  [monitor] No OpenInference instrumentors found")
    return installed
