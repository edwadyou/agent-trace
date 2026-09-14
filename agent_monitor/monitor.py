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

# --- process-wide activation state ------------------------------------------
# OpenTelemetry honours ``set_tracer_provider()`` only ONCE per process; every
# later call just logs "Overriding of current TracerProvider is not allowed"
# and is ignored. A non-re-entrant ``monitor()`` therefore breaks as soon as two
# of them overlap -- which is exactly what happens when the CLI (``run``) or the
# zero-code distro wraps a user script that calls ``monitor()`` itself:
#
#   * the inner provider can never become the global one, so the inner call's
#     own file stays EMPTY and its spans leak into the outer call's file;
#   * the inner ``finally`` un-instruments the OUTER call's monkey-patches,
#     silently killing framework tracing for the rest of the run.
#
# ``_ACTIVE`` turns nesting into a no-op instead: the outermost call owns the
# provider / processor / instrumentors, and every nested call only bumps
# ``depth`` and hands back the very same tracer.
_ACTIVE: dict | None = None
# True once this process has activated (and deactivated) a monitor() at least
# once. Used to warn about *sequential* calls, which cannot get their own
# provider because the global slot is taken for good.
_EVER_ACTIVATED = False


def _warn(message: str) -> None:
    print(message, file=sys.stderr)


def _exporter_label(exporter) -> str:
    """Normalise an ``exporter`` argument to a comparable, printable label."""
    if exporter is None:
        return "jsonl"          # the default, see the resolution step below
    if isinstance(exporter, str):
        return exporter
    return type(exporter).__name__


# Opt-out for the thread-boundary context patch (see ._threadctx). Read on
# every monitor() entry rather than at import time, so a script can still flip it
# before it opens its first monitor().
_THREAD_CONTEXT_ENV = "AGENT_MONITOR_THREAD_CONTEXT"
_THREAD_CONTEXT_OFF = {"0", "false", "no", "off"}


def _thread_context_default() -> bool:
    """Should trace context cross thread boundaries unless told otherwise?"""
    raw = os.environ.get(_THREAD_CONTEXT_ENV)
    if raw is None:
        return True
    return raw.strip().lower() not in _THREAD_CONTEXT_OFF


# Allow-list for instrumentor activation, same shape as the thread-context
# switch: read on every monitor() entry so a script can still change it.
#
# Why this exists: two instrumentors can cover the SAME call. A langchain app
# built on langchain-openai gets an ``LLM`` span from the langchain instrumentor
# (``ChatOpenAI``) and a second one from the openai instrumentor
# (``ChatCompletion``) wrapping the very same HTTP request, so every single call
# shows up twice in the viewer. Neither package suppresses the other, and
# auto-detect has no way to know which one the user wants -- so the user says so.
_INSTRUMENTORS_ENV = "AGENT_MONITOR_INSTRUMENTORS"
_INSTRUMENTORS_UNRESTRICTED = {"", "*", "all", "auto", "any"}


def _instrumentor_allowlist() -> list[str] | None:
    """Names from ``AGENT_MONITOR_INSTRUMENTORS``, or ``None`` if unrestricted."""
    raw = os.environ.get(_INSTRUMENTORS_ENV)
    if raw is None:
        return None
    names = [p.strip() for p in raw.replace(";", ",").split(",")]
    names = [n for n in names if n]
    if not names or any(n.lower() in _INSTRUMENTORS_UNRESTRICTED for n in names):
        return None
    return names


def _restrict_instrumentors(instrumentors, allowlist, *, verbose: bool = False):
    """Intersect a resolved instrumentor list with an explicit allow-list.

    The allow-list is a *filter*, never a substitute: a name it asks for is
    still only activated if this environment actually has that instrumentor.
    ``instrumentors is None`` means "whatever is installed", which is the one
    case where the allow-list has to *become* the list -- ``_auto_instrument``
    then ignores the entry points that are not named, and reports the names that
    are not installed.
    """
    if not allowlist:
        return instrumentors
    from ._detect import _normalize_instrumentor_name as _norm

    wanted = {_norm(n) for n in allowlist}
    if instrumentors is None:
        return list(allowlist)
    kept = [n for n in instrumentors if _norm(n) in wanted]
    if not kept:
        _warn(
            f"[monitor] warning: {_INSTRUMENTORS_ENV}={','.join(allowlist)} "
            "matched none of the instrumentors resolved for this run "
            f"({', '.join(instrumentors) or 'none'}); nothing will be instrumented."
        )
    elif verbose:
        dropped = [n for n in instrumentors if _norm(n) not in wanted]
        if dropped:
            print(f"[monitor] instrumentor allow-list kept {kept}, dropped {dropped}")
    return kept


def _activation_config_warning(state: dict, *, service_name: str,
                               exporter, trace_file,
                               thread_context=None) -> None:
    """Report -- and then ignore -- config a nested ``monitor()`` tried to set.

    A process has one global TracerProvider, so only the outermost call gets to
    choose where spans go. Stay quiet about values that were not really asked
    for: ``service_name`` defaults to ``"agent"``, ``exporter``/``trace_file``
    default to ``None``, and ``thread_context`` defaults to ``None`` (meaning
    "whatever the environment says").
    """
    ignored = []
    if service_name != "agent" and service_name != state["service_name"]:
        ignored.append(
            f"service_name={service_name!r} (keeping {state['service_name']!r})"
        )
    if trace_file is not None:
        requested = os.fspath(trace_file)
        if requested != state["trace_file"]:
            ignored.append(f"trace_file={requested!r} (keeping {state['trace_file']!r})")
    if exporter is not None:
        requested = _exporter_label(exporter)
        if requested != state["exporter"]:
            ignored.append(f"exporter={requested!r} (keeping {state['exporter']!r})")
    if thread_context is not None and thread_context != state["thread_context"]:
        ignored.append(
            f"thread_context={thread_context!r} "
            f"(keeping {state['thread_context']!r})"
        )
    if ignored:
        _warn(
            "[monitor] nested monitor(): ignoring " + ", ".join(ignored) + ".\n"
            "[monitor]   A process has exactly one global TracerProvider (OpenTelemetry\n"
            "[monitor]   allows set_tracer_provider() once), so the OUTERMOST monitor()\n"
            "[monitor]   decides where spans go. Nested calls are no-ops by design."
        )


def _activate(*, service_name: str, exporter, exporter_spec: str,
              trace_file_spec: str, auto_instrument: bool, instrumentors,
              verbose: bool, thread_context: bool) -> dict:
    """Build the one TracerProvider this process is allowed to have."""
    processor = SimpleSpanProcessor(exporter)
    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(processor)
    # First call in the process wins; later ones are ignored by the API (see
    # _ACTIVE above), which is why nested monitor() calls never get here.
    otel_trace.set_tracer_provider(provider)
    instrumented = []
    if auto_instrument:
        instrumented = _auto_instrument(
            tracer_provider=provider,
            instrumentors=instrumentors,
            verbose=verbose,
        )
    # Thread-boundary context propagation. Without it every task handed to a
    # ThreadPoolExecutor -- or to a bare threading.Thread -- runs with an empty
    # OTel context and starts its OWN trace, so an agent that fans out over
    # threads produces dozens of orphan trees no matter how carefully the root
    # span was injected. install() is per-task copy_context(), the same trick
    # langchain's ContextThreadPoolExecutor uses.
    threadctx_installed = False
    if thread_context:
        from ._threadctx import install
        try:
            threadctx_installed = install()
        except Exception as exc:  # pragma: no cover
            _warn(f"[monitor] thread-context patch failed: {exc}")
        if verbose and threadctx_installed:
            print("  [monitor] Thread context propagation: ON "
                  "(ThreadPoolExecutor.submit, threading.Thread.start)")
    return {
        "provider": provider,
        "processor": processor,
        "tracer": otel_trace.get_tracer(service_name),
        "instrumentors": instrumented,
        "depth": 1,
        "service_name": service_name,
        "trace_file": trace_file_spec,
        "exporter": exporter_spec,
        "thread_context": thread_context,
        "threadctx_installed": threadctx_installed,
    }


def _deactivate(state: dict) -> None:
    """Tear the outermost activation down. Only ever called at depth 0."""
    for inst in state["instrumentors"]:
        try:
            inst.uninstrument()
        except Exception as exc:  # pragma: no cover
            print(f"[monitor] uninstrument failed: {exc}", file=sys.stderr)
    # Undo the stdlib thread patch only at depth 0 -- a nested monitor() must
    # not un-patch the outer one, exactly like it must not un-instrument it.
    if state.get("threadctx_installed"):
        from ._threadctx import uninstall
        try:
            uninstall()
        except Exception as exc:  # pragma: no cover
            print(f"[monitor] thread-context unpatch failed: {exc}",
                  file=sys.stderr)
    processor = state["processor"]
    # Flush then shut down our own processor/provider. Swallow
    # transient I/O errors so a single failure does not skip the
    # downstream cleanup steps.
    try:
        processor.force_flush()
    except Exception as exc:  # pragma: no cover
        print(f"[monitor] force_flush failed: {exc}", file=sys.stderr)
    processor.shutdown()
    state["provider"].shutdown()
    # Deliberately NOT restoring the previous global tracer provider: OTel
    # ignores every set_tracer_provider() after the first, so the old "restore"
    # only produced a spurious "Overriding ... is not allowed" warning and
    # changed nothing. Consequence: a *sequential* second monitor() cannot get
    # its own provider -- warned about below and listed under Known limitations.


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
    thread_context: bool | None = None,
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
                        auto_detect if both are set. The comma-separated
                        ``AGENT_MONITOR_INSTRUMENTORS`` env var narrows this
                        list -- and narrows auto_detect's result -- so one env
                        var can drop a redundant instrumentor process-wide.
        verbose:        print which instrumentors were activated.
        exporter:       a ``SpanExporter`` instance, or one of the named
                        aliases ``"jsonl"`` / ``"console"``. Defaults to
                        ``JsonlFileExporter`` writing ``trace_file``.
        trace_file:     output path when exporter is the JSONL alias or the
                        default. Ignored for other exporters.
        thread_context: propagate trace context across thread boundaries
                        (``ThreadPoolExecutor.submit`` / ``threading.Thread``),
                        so tasks handed to a pool stay in THIS trace instead of
                        each starting their own. ``None`` (the default) reads
                        ``AGENT_MONITOR_THREAD_CONTEXT`` and is on unless that
                        is 0/false/no/off.

    Re-entrancy:
        ``monitor()`` is safe to nest. The outermost call owns this process's
        single global ``TracerProvider``; a nested call reuses it and yields the
        same tracer instead of building a second provider that OpenTelemetry
        would refuse to install (and instead of un-instrumenting the outer
        call's patches on exit). A nested call asking for a different
        ``service_name`` / ``trace_file`` / ``exporter`` gets one stderr warning
        and is otherwise ignored. Running two ``monitor()`` blocks one AFTER
        another is still limited: the second cannot redirect spans away from the
        first, because the global provider cannot be replaced.

    Thread propagation:
        ``contextvars`` cannot cross a *process* boundary, so ``multiprocessing``
        and Celery workers still start their own traces no matter what this flag
        says. That needs ``TRACEPARENT`` propagation and is a documented limit.
    """
    global _ACTIVE, _EVER_ACTIVATED

    # ---- 0) re-entrant fast path --------------------------------------------
    if _ACTIVE is not None:
        state = _ACTIVE
        state["depth"] += 1
        _activation_config_warning(state, service_name=service_name,
                                   exporter=exporter, trace_file=trace_file,
                                   thread_context=thread_context)
        if verbose:
            print(f"[monitor] reusing the active tracer provider "
                  f"(depth {state['depth']})")
        try:
            yield state["tracer"]
        finally:
            # Leave the provider AND the instrumentors alone: tearing them down
            # here is what used to break the outer monitor().
            state["depth"] -= 1
        return

    if _EVER_ACTIVATED:
        _warn(
            "[monitor] warning: an earlier monitor() already installed this process's\n"
            "[monitor]   one-and-only global TracerProvider and OpenTelemetry refuses to\n"
            "[monitor]   replace it, so spans keep going to the FIRST monitor()'s\n"
            "[monitor]   destination. Nest the calls, or use a single monitor() for the\n"
            "[monitor]   whole process (see `python -m agent_monitor run`)."
        )

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

    # ---- 1b) apply the instrumentor allow-list -------------------------------
    # Runs AFTER auto-detect on purpose: the allow-list narrows whatever this
    # run would otherwise have activated, so `--auto-detect --instrumentors
    # langchain` means "the frameworks you detected, minus the ones I did not
    # name". See _restrict_instrumentors for the None case.
    allowlist = _instrumentor_allowlist()
    if allowlist:
        instrumentors = _restrict_instrumentors(
            instrumentors, allowlist, verbose=verbose
        )

    # ---- 2) resolve exporter -------------------------------------------------
    trace_file_spec = (
        os.fspath(trace_file) if trace_file is not None else DEFAULT_TRACE_FILE
    )
    # Captured BEFORE the alias is resolved into a concrete SpanExporter, so a
    # nested `exporter="jsonl"` compares equal to the outer one instead of being
    # reported as a change.
    exporter_spec = _exporter_label(exporter)
    if exporter is None:
        # truncate_on_init defaults to False inside the exporter; we re-enable
        # it HERE so the first monitor() in this process clears a stale file.
        # The exporter's module-level _TRUNCATED_FILES registry ensures a
        # nested / second monitor() to the same path does NOT re-truncate.
        exporter = JsonlFileExporter(file_path=trace_file_spec, truncate_on_init=True)
    elif isinstance(exporter, str):
        exporter = _resolve_named_exporter(exporter, service_name=service_name,
                                           trace_file=trace_file)

    # ---- 2b) resolve the thread-context default from the environment ---------
    if thread_context is None:
        thread_context = _thread_context_default()

    # ---- 3) activate, yield, and clean up only at depth 0 --------------------
    state = _activate(
        service_name=service_name,
        exporter=exporter,
        exporter_spec=exporter_spec,
        trace_file_spec=trace_file_spec,
        auto_instrument=auto_instrument,
        instrumentors=instrumentors,
        verbose=verbose,
        thread_context=thread_context,
    )
    _ACTIVE = state
    _EVER_ACTIVATED = True
    try:
        yield state["tracer"]
    finally:
        _ACTIVE = None
        _deactivate(state)


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
            # An instrumentor whose framework SDK is missing logs a
            # DependencyConflict and returns WITHOUT instrumenting anything.
            # Tracking it anyway only buys us an "Attempting to uninstrument
            # while already uninstrumented" warning on exit.
            if getattr(inst, "is_instrumented_by_opentelemetry", True):
                installed.append(inst)
                if verbose:
                    print(f"  [monitor] Auto-instrumented: {ep.name}")
            elif verbose:
                print(f"  [monitor] Skipped {ep.name}: dependency conflict")
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
