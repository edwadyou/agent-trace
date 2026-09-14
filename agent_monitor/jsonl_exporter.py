"""Streaming JSONL exporter for OpenTelemetry spans.

Writes one JSON object per span to a file as soon as the span is exported.
Unlike :class:`agent_monitor.console_exporter.ConsoleSpanExporter` (which
buffers until the root span ends and writes a nested tree), this exporter is
**streaming-friendly**: a Streamlit viewer polling the file will see partial
traces update live as child spans complete.

Schema version 1.1.0 record shape::

    {
      "schema_version": "1.1.0",       # NEW: enables safe consumer migration
      "service_name":   "my-agent",    # NEW: OTel resource.service.name
      "trace_id":       "0" * 32 hex,
      "span_id":        "0" * 16 hex,
      "parent_span_id": "0" * 16 hex or null,
      "name":           "ChatOpenAI",
      "start_time":     1234567890123456789,   # ns since epoch
      "end_time":       1234567891123456789,
      "duration_ms":    1000.0,
      "status":         "OK" / "ERROR" / "UNSET",
      "kind":           "LLM" / "CHAIN" / ...   # openinference.span.kind
      "attributes":     { ... },                # raw OTel attrs + flattened llm.*
      "events":         [ {name, attributes, time}, ... ]
    }

Backward compatibility: 1.0.0 records missing ``schema_version`` /
``service_name`` are accepted by the SDK migrator (see
``agent_monitor._schema_migrations``).
"""
from __future__ import annotations
import json
import os
import threading
from pathlib import Path
from typing import Any

from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult

SCHEMA_VERSION = "1.1.0"

# Process-level registry of files already truncated by JsonlFileExporter in
# this Python process. Keyed by os.path.realpath so that symlinks and
# relative paths collapse to the same entry. Prevents nested monitor()
# contexts (or two `monitor()` calls in one process) from erasing each
# other`s historical traces on the second-and-later construction.
_TRUNCATED_FILES: set[str] = set()

# Process-wide lock serializing JSONL writes. Module level rather than per
# instance because two exporter objects can point at the same file (e.g. a
# monitor() reactivated after an outer one released it).
_WRITE_LOCK = threading.Lock()


def _already_truncated(path: Path) -> bool:
    try:
        key = str(Path(os.path.realpath(path)).resolve())
    except OSError:
        key = str(Path(path).absolute())
    return key in _TRUNCATED_FILES


def _mark_truncated(path: Path) -> None:
    try:
        key = str(Path(os.path.realpath(path)).resolve())
    except OSError:
        key = str(Path(path).absolute())
    _TRUNCATED_FILES.add(key)

# LLM/OpenInference attribute keys we flatten from nested ``output.value``
# into top-level ``attributes`` for easier consumer access.
_FLATTEN_KEYS = (
    "llm.model_name",
    "llm.provider",
    "llm.system",
    "llm.token_count.prompt",
    "llm.token_count.completion",
    "llm.token_count.total",
)


class JsonlFileExporter(SpanExporter):
    """Append each span as a JSON line to a file.

    Args:
        file_path: output file. Defaults to ``./latest_traces.jsonl``.
        truncate_on_init: if True, clear the file at exporter construction so
            each program run starts fresh. Set to False for long-running
            services that want to append forever.
        ensure_ascii: pass-through to ``json.dumps`` (False keeps CJK readable).
        service_name: optional OTel resource ``service.name`` written onto every
            record. If not provided, the SDK monitor() will inject it.
    """

    def __init__(
        self,
        file_path: str | os.PathLike[str] = "latest_traces.jsonl",
        *,
        truncate_on_init: bool = False,
        ensure_ascii: bool = False,
        service_name: str | None = None,
    ) -> None:
        self.file_path = Path(file_path)
        self._ensure_ascii = ensure_ascii
        self._service_name = service_name
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        # Idempotent per process: only clear on the FIRST construction for a
        # given path. Subsequent exports (nested monitor() / same-process
        # re-use of the same file) append so prior spans survive.
        if truncate_on_init and not _already_truncated(self.file_path):
            self.file_path.write_text("", encoding="utf-8")
            _mark_truncated(self.file_path)

    def export(self, spans: list[ReadableSpan]) -> SpanExportResult:
        if not spans:
            return SpanExportResult.SUCCESS
        # Serialize the whole batch to bytes BEFORE touching the file, then
        # emit it with one write() under a process-wide lock.
        #
        # Why: monitor() installs a SimpleSpanProcessor, so export() runs
        # synchronously on whichever thread ends a span. A ThreadPoolExecutor
        # fan-out therefore calls export() concurrently from many threads, and
        # the old text-mode append handle let BufferedWriter flush a record in
        # several chunks -- two interleaving threads produced a physical line
        # spliced mid-record, i.e. unparsable JSONL. Binary mode additionally
        # stops Windows from translating "\n" into "\r\n".
        payload = b"".join(
            json.dumps(
                _span_to_record(span, default_service_name=self._service_name),
                ensure_ascii=self._ensure_ascii,
            ).encode("utf-8") + b"\n"
            for span in spans
        )
        with _WRITE_LOCK:
            with self.file_path.open("ab") as f:
                f.write(payload)
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        return None

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return True


def _span_to_record(span: ReadableSpan, *, default_service_name: str | None = None) -> dict[str, Any]:
    ctx = span.get_span_context()
    trace_id = f"{ctx.trace_id:032x}"
    span_id = f"{ctx.span_id:016x}"
    parent_span_id = f"{span.parent.span_id:016x}" if span.parent else None

    start_ns = span.start_time or 0
    end_ns = span.end_time or start_ns
    duration_ms = max(0.0, (end_ns - start_ns) / 1_000_000.0)

    status_code = "UNSET"
    try:
        status_code = span.status.status_code.name  # type: ignore[union-attr]
    except AttributeError:
        status_code = str(span.status.status_code)

    attributes = dict(span.attributes or {})
    attributes = _flatten_llm_attrs(attributes)
    kind = (
        attributes.get("openinference.span.kind")
        or attributes.get("gen_ai.span.kind")
        or "UNKNOWN"
    )

    service_name = _extract_service_name(span, default=default_service_name)

    events: list[dict[str, Any]] = []
    for evt in (span.events or []):
        events.append({
            "name": evt.name,
            "time": evt.timestamp,
            "attributes": dict(evt.attributes or {}),
        })

    return {
        "schema_version": SCHEMA_VERSION,
        "service_name": service_name,
        "trace_id": trace_id,
        "span_id": span_id,
        "parent_span_id": parent_span_id,
        "name": span.name,
        "start_time": start_ns,
        "end_time": end_ns,
        "duration_ms": round(duration_ms, 3),
        "status": status_code,
        "kind": kind,
        "attributes": attributes,
        "events": events,
    }


def _extract_service_name(span: ReadableSpan, *, default: str | None) -> str | None:
    """Pull service.name from the span's resource, falling back to a default."""
    try:
        resource = span.resource
        if resource and getattr(resource, "attributes", None):
            sn = resource.attributes.get("service.name")
            if isinstance(sn, str) and sn:
                return sn
    except Exception:
        pass
    return default


def _flatten_llm_attrs(attributes: dict[str, Any]) -> dict[str, Any]:
    """If attributes is missing standard llm.* keys but ``output.value`` contains
    them inside a serialized JSON, lift them to top-level attributes.

    This only ADDS keys; never overwrites existing top-level entries.
    """
    out = dict(attributes)
    raw = out.get("output.value")
    if not isinstance(raw, str) or not raw.startswith("{"):
        return out
    if all(k in out for k in _FLATTEN_KEYS):
        return out
    try:
        parsed = json.loads(raw)
    except (ValueError, TypeError):
        return out
    # Search recursively for the well-known keys. Most output.value payloads
    # from openinference store model_name under response_metadata.model_name
    # and token_usage under usage_metadata. We do a shallow DFS.
    found: dict[str, Any] = {}
    _collect_llm_fields(parsed, found, depth=0)
    for k, v in found.items():
        out.setdefault(k, v)
    return out


def _collect_llm_fields(obj: Any, out: dict[str, Any], *, depth: int) -> None:
    if depth > 8:
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in _FLATTEN_KEYS and k not in out:
                out[k] = v
            else:
                _collect_llm_fields(v, out, depth=depth + 1)
    elif isinstance(obj, (list, tuple)):
        for item in obj:
            _collect_llm_fields(item, out, depth=depth + 1)