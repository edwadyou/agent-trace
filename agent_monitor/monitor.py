from __future__ import annotations
import json
import os
import sys
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
        if key and not os.environ.get(key):
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
        # truncate_on_init defaults to False inside the exporter; we re-enable
        # it HERE so the first monitor() in this process clears a stale file.
        # The exporter's module-level _TRUNCATED_FILES registry ensures a
        # nested / second monitor() to the same path does NOT re-truncate.
        exporter = JsonlFileExporter(file_path=path, truncate_on_init=True)
    elif isinstance(exporter, str):
        exporter = _resolve_named_exporter(exporter, service_name=service_name,
                                           trace_file=trace_file)

    processor = SimpleSpanProcessor(exporter)
    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(processor)
    _instrumented = []
    # Push: remember whoever set the global tracer provider before us so
    # the `finally` block can restore it. Without this, nested `monitor()`
    # calls inside the same process would all share / overwrite each
    # other, and the outermost shutdown would tear down a provider the
    # caller still needs.
    _prev_provider = otel_trace.get_tracer_provider()
    _we_set_global = False
    try:
        otel_trace.set_tracer_provider(provider)
        _we_set_global = True
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
            except Exception as exc:  # pragma: no cover
                import sys as _sys_m
                print(f"[monitor] uninstrument failed: {exc}", file=_sys_m.stderr)
        # Flush then shut down our own processor/provider. Swallow
        # transient I/O errors so a single failure does not skip the
        # downstream cleanup steps.
        try:
            processor.force_flush()
        except Exception as exc:  # pragma: no cover
            import sys as _sys_m
            print(f"[monitor] force_flush failed: {exc}", file=_sys_m.stderr)
        processor.shutdown()
        provider.shutdown()
        # Pop: restore the previous tracer provider so nested or
        # consecutive monitor() calls do not see a stale, shut-down
        # global provider.
        if _we_set_global:
            try:
                otel_trace.set_tracer_provider(_prev_provider)
            except Exception:  # pragma: no cover
                pass


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
    from ._detect import _normalize_instrumentor_name

    installed = []
    eps = entry_points()
    try:
        group = eps.select(group="openinference_instrumentor")
    except AttributeError:
        group = eps.get("openinference_instrumentor", [])

    available = {_normalize_instrumentor_name(ep.name) for ep in group}
    if instrumentors is None:
        requested = None
    else:
        requested = {_normalize_instrumentor_name(name) for name in instrumentors}

    for ep in group:
        if requested is not None and _normalize_instrumentor_name(ep.name) not in requested:
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

    if requested:
        missing = requested - available
        if missing:
            print(
                "[monitor] warning: requested instrumentors not installed: "
                + ", ".join(sorted(missing)),
                file=sys.stderr,
            )
    if verbose and not installed:
        print("  [monitor] No OpenInference instrumentors found")
    return installed


def _resolve_named_exporter(name: str, *, service_name: str,
                            trace_file: str | os.PathLike[str] | None = None) -> SpanExporter:
    """Translate short names like ``"jsonl"`` into concrete exporter instances."""
    name = name.lower().strip()
    if name in {"jsonl", "json", "file", "stream", "local"}:
        path = os.fspath(trace_file) if trace_file is not None else DEFAULT_TRACE_FILE
        return JsonlFileExporter(file_path=path, truncate_on_init=True)
    if name in {"console", "tree"}:
        return ConsoleSpanExporter(service_name=service_name)
    raise ValueError(
        f"Unknown exporter alias: {name!r}. "
        f"Use 'console', 'jsonl', or pass a SpanExporter instance."
    )
