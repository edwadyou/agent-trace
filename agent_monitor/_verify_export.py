"""Verify that a JSONL trace export contains useful data.

Designed to be called from CI or immediately after an agent run:

    from agent_monitor._verify_export import verify_export
    ok = verify_export(expected_path="latest_traces.jsonl",
                       min_spans=10, min_traces=1)

Returns True if every check passes, False otherwise. Prints a structured
report regardless of the outcome.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Any

from .jsonl_exporter import SCHEMA_VERSION
from ._schema_migrations import migrate


def verify_export(
    expected_path: str | os.PathLike[str] = "latest_traces.jsonl",
    *,
    min_spans: int = 1,
    min_traces: int = 1,
    max_traces: int | None = None,
    require_kind_in: tuple[str, ...] = (),
    quiet: bool = False,
) -> bool:
    """Run a battery of checks on a JSONL trace file.

    Checks:
        1. File exists and is non-empty.
        2. Every line is valid JSON (UTF-8 BOM is stripped transparently).
        3. Every record has ``trace_id``, ``span_id``, ``start_time``,
           ``end_time``, ``kind``, ``schema_version``.
        4. Span count >= ``min_spans``.
        5. Trace count >= ``min_traces``.
        6. If ``require_kind_in`` is given, at least one span has a kind from
           that set (e.g. ("LLM",) to ensure an LLM call actually happened).
        7. If ``max_traces`` is given, trace count <= ``max_traces``. Use
           ``max_traces=1`` in CI to assert that a whole agent run is ONE tree
           rather than a pile of orphaned sub-traces.

    Args:
        expected_path: JSONL file to inspect.
        min_spans: minimum total span count.
        min_traces: minimum distinct trace_id count.
        max_traces: maximum distinct trace_id count (None disables the check).
        require_kind_in: optional tuple of kinds that MUST appear at least once.
        quiet: if True, only print failures.

    Returns:
        True iff every check passes.
    """
    path = Path(expected_path)
    failures: list[str] = []
    summary: dict[str, Any] = {}

    if not path.is_file():
        failures.append(f"file not found: {path}")
    else:
        spans, errors, trace_ids, kinds_seen = _scan(path)
        summary.update({
            "path":           str(path),
            "size_bytes":     path.stat().st_size,
            "span_count":     len(spans),
            "trace_count":    len(trace_ids),
            "root_count":     sum(1 for s in spans if not s.get("parent_span_id")),
            "kinds_seen":     sorted(kinds_seen),
            "schema_versions":sorted({s.get("schema_version") for s in spans}),
            "json_errors":    len(errors),
        })

        if errors:
            failures.append(f"{len(errors)} invalid JSON line(s)")
        for required in ("trace_id", "span_id", "start_time", "end_time",
                         "kind", "schema_version"):
            missing = [s for s in spans if required not in s]
            if missing:
                failures.append(f"{len(missing)} span(s) missing field {required!r}")

        if len(spans) < min_spans:
            failures.append(f"span count {len(spans)} < min_spans={min_spans}")
        if len(trace_ids) < min_traces:
            failures.append(f"trace count {len(trace_ids)} < min_traces={min_traces}")
        if max_traces is not None and len(trace_ids) > max_traces:
            failures.append(
                f"trace count {len(trace_ids)} > max_traces={max_traces}; one "
                f"agent run should be ONE trace tree, so the extra roots mean "
                f"trace context was lost (see orphan_trace_report)"
            )
        if require_kind_in:
            have = kinds_seen & set(require_kind_in)
            if not have:
                failures.append(
                    f"none of the required kinds {require_kind_in} appeared; "
                    f"only saw {sorted(kinds_seen)}"
                )

    _print_report(summary, failures, quiet=quiet)
    return not failures


def orphan_trace_report(expected_path: str | os.PathLike[str]) -> dict[str, Any]:
    """Summarise the trace TREES in a JSONL export.

    A trace is not a container, it is a tree: every span without a
    ``parent_span_id`` is the root of its own tree. Wrapping a run in a root span
    therefore yields exactly one root; more than one means the context never
    reached part of the run, and the extra roots name the places to look at.

    Returns:
        ``{"path", "span_count", "trace_count", "roots"}`` where ``roots`` is a
        list of ``(trace_id, name, kind, start_time)`` tuples sorted by
        ``start_time``. Missing/unreadable files yield an empty report rather
        than raising, so callers can use this unconditionally after a run.
    """
    path = Path(expected_path)
    if not path.is_file():
        return {"path": str(path), "span_count": 0, "trace_count": 0, "roots": []}
    spans, _errors, trace_ids, _kinds = _scan(path)
    roots = [
        (
            s.get("trace_id", "?"),
            s.get("name", "?"),
            s.get("kind") or "UNKNOWN",
            s.get("start_time") or 0,
        )
        for s in spans
        if not s.get("parent_span_id")
    ]
    roots.sort(key=lambda r: r[3])
    return {
        "path": str(path),
        "span_count": len(spans),
        "trace_count": len(trace_ids),
        "roots": roots,
    }


def _scan(path: Path) -> tuple[list[dict], list[int], set[str], set[str]]:
    spans: list[dict] = []
    errors: list[int] = []
    trace_ids: set[str] = set()
    kinds_seen: set[str] = set()
    # Use utf-8-sig so a UTF-8 BOM (common on Windows-created files,
    # e.g. produced by `powershell Set-Content -Encoding utf8`) is stripped
    # transparently instead of poisoning the first line.
    with path.open("r", encoding="utf-8-sig") as f:
        for lineno, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                errors.append(lineno)
                continue
            rec = migrate(rec)
            spans.append(rec)
            trace_ids.add(rec.get("trace_id", "?"))
            kinds_seen.add(rec.get("kind") or "UNKNOWN")
    return spans, errors, trace_ids, kinds_seen


def _print_report(summary: dict[str, Any], failures: list[str], *, quiet: bool) -> None:
    if not quiet or failures:
        print("=== agent_monitor verify_export ===")
        if summary:
            for k, v in summary.items():
                print(f"  {k:>16}: {v}")
        else:
            print("  (no data)")
        if failures:
            print("\n  FAILURES:")
            for f in failures:
                print(f"    - {f}")
            print("\n  RESULT: FAIL")
        else:
            print("\n  RESULT: OK")