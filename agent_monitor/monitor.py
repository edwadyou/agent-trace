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
from opentelemetry.sdk.resources import Resource
from .console_exporter import ConsoleSpanExporter
from opentelemetry.sdk.trace.export import SpanExporter
from .jsonl_exporter import JsonlFileExporter


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

DEFAULT_TRACE_FILE = "latest_traces.jsonl"


@contextmanager
def monitor(
    service_name: str = "agent",
    *,
    auto_instrument: bool = False,
    auto_detect: bool = False,
    instrumentors=None,
    verbose: bool = False,
    exporter: SpanExporter | str | None = None,
    trace_file: str | os.PathLike[str] | None = None,
):
    """Open a traced context. Yields an OTel tracer.

    Args:
        service_name: identifier attached to every span.
        auto_instrument: if True, activate OpenInference instrumentors.
        auto_detect:    if True AND ``instrumentors`` is None, sniff which
                        frameworks are importable + have instrumentors installed,
                        then activate exactly those. No-op if ``instrumentors``
                        is passed explicitly.
        instrumentors:  explicit list of OpenInference instrumentor names to
                        activate (e.g. ["langchain","openai"]). Overrides
                        auto_detect if both are set.
        verbose:        print which instrumentors were activated.
        exporter:       a ``SpanExporter`` instance, or one of the named
                        aliases ``"jsonl"`` / ``"console"``. Defaults to
                        ``JsonlFileExporter`` writing ``trace_file``.
        trace_file:     output path when exporter is the JSONL alias or the
                        default. Ignored for other exporters.
    """
    # ---- 1) resolve instrumentors from auto_detect ---------------------------
    if auto_detect and not instrumentors:
        try:
            from ._detect import detect_compatible
            instrumentors = detect_compatible()
            if verbose:
                print(f"[monitor] auto-detected instrumentors: {instrumentors}")
        except Exception as exc:  # pragma: no cover
            if verbose:
                print(f"[monitor] auto_detect failed: {exc}")
            instrumentors = None

    # ---- 2) resolve exporter -------------------------------------------------
    if exporter is None:
        path = os.fspath(trace_file) if trace_file is not None else DEFAULT_TRACE_FILE
        exporter = JsonlFileExporter(file_path=path)
    elif isinstance(exporter, str):
        exporter = _resolve_named_exporter(exporter, service_name=service_name,
                                           trace_file=trace_file)

    processor = SimpleSpanProcessor(exporter)
    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(processor)
    _instrumented = []
    try:
        otel_trace.set_tracer_provider(provider)
        if auto_instrument:
            _instrumented = _auto_instrument(
                tracer_provider=provider,
                instrumentors=instrumentors,
                verbose=verbose,
            )
        yield otel_trace.get_tracer(service_name)
    finally:
        for inst in _instrumented:
            try:
                inst.uninstrument()
            except Exception:
                pass
        processor.force_flush()
        processor.shutdown()
        provider.shutdown()


def trace(service_name="agent", *, auto_instrument=False, auto_detect=False,
          instrumentors=None, verbose=False):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            with monitor(service_name=service_name, auto_instrument=auto_instrument,
                         auto_detect=auto_detect, instrumentors=instrumentors,
                         verbose=verbose):
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
    eps = entry_points()
    try:
        group = eps.select(group="openinference_instrumentor")
    except AttributeError:
        group = eps.get("openinference_instrumentor", [])
    for ep in group:
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


def _resolve_named_exporter(name: str, *, service_name: str,
                            trace_file: str | os.PathLike[str] | None = None) -> SpanExporter:
    """Translate short names like ``"jsonl"`` into concrete exporter instances."""
    name = name.lower().strip()
    if name in {"jsonl", "json", "file", "stream", "local"}:
        path = os.fspath(trace_file) if trace_file is not None else DEFAULT_TRACE_FILE
        return JsonlFileExporter(file_path=path)
    if name in {"console", "tree"}:
        return ConsoleSpanExporter(service_name=service_name)
    raise ValueError(
        f"Unknown exporter alias: {name!r}. "
        f"Use 'console', 'jsonl', or pass a SpanExporter instance."
    )