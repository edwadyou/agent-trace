
"""Custom SpanExporter that writes traces as JSON files.

When a trace's root span ends, the buffered spans are assembled into a tree and
written to the ``traces/`` directory as ``trace-<timestamp>-<trace>.json``.
The output mirrors the shape used by the previous terminal renderer, but as
structured data suitable for later inspection, diffing, or archival.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult

from .trace_renderer import build_span_tree


class ConsoleSpanExporter(SpanExporter):
    """Collects spans per trace and writes each completed trace as a JSON file."""

    def __init__(
        self,
        output_dir: str | Path | None = None,
        service_name: str | None = None,
    ) -> None:
        self._output_dir = Path(output_dir) if output_dir else Path.cwd() / "traces"
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._service_name = _safe_filename(service_name) if service_name else "agent"
        self._spans: dict[str, list[ReadableSpan]] = defaultdict(list)
        self._written: set[str] = set()

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        for span in spans:
            trace_id = _trace_id_hex(span)
            self._spans[trace_id].append(span)
        for tid, trace_spans in list(self._spans.items()):
            if tid in self._written:
                continue
            root = next((s for s in trace_spans if s.parent is None), None)
            if root is not None:
                self._write_trace(tid, trace_spans)
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        for tid, trace_spans in list(self._spans.items()):
            if trace_spans:
                self._write_trace(tid, trace_spans)
        self._spans.clear()
        self._written.clear()

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return True

    def _write_trace(self, trace_id: str, trace_spans: list[ReadableSpan]) -> None:
        tree = build_span_tree(trace_spans)
        payload = _trace_to_dict(tree)
        timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
        file_path = self._output_dir / f"trace-{self._service_name}-{timestamp}-{trace_id[:8]}.json"
        file_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self._written.add(trace_id)
        self._spans.pop(trace_id, None)


def _trace_id_hex(span: ReadableSpan) -> str:
    ctx = span.get_span_context()
    return f"{ctx.trace_id:032x}"


def _trace_to_dict(tree) -> dict[str, Any]:
    return {
        "trace_id": tree.trace_id,
        "root": _node_to_dict(tree.root),
    }


def _node_to_dict(node) -> dict[str, Any]:
    duration_ms = max(0.0, (node.end_time - node.start_time).total_seconds() * 1000.0)
    return {
        "name": node.name,
        "span_id": node.span_id,
        "parent_id": node.parent_id,
        "span_kind": node.span_kind,
        "start_time": node.start_time.isoformat(),
        "end_time": node.end_time.isoformat(),
        "duration_ms": round(duration_ms, 3),
        "status": node.status,
        "status_message": node.status_message,
        "attributes": dict(node.attributes),
        "children": [_node_to_dict(child) for child in node.children],
    }

def _safe_filename(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-") or "agent"

