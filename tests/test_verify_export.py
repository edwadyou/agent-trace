"""Tests for the trace-tree checks in ``_verify_export``.

``min_traces`` answers "did anything get exported?". It cannot answer the
question that actually matters after wrapping a run in a root span: "is this ONE
tree, or did the run fall apart?" -- because a fragmented run has *more* traces,
never fewer. ``max_traces`` and ``orphan_trace_report`` cover that gap.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from agent_monitor._verify_export import orphan_trace_report, verify_export
from agent_monitor.jsonl_exporter import SCHEMA_VERSION

REPO_ROOT = Path(__file__).resolve().parent.parent

TRACE_A = "a" * 32
TRACE_B = "b" * 32


def _rec(trace_id, span_id, parent, name, kind, start):
    return {
        "schema_version": SCHEMA_VERSION,
        "service_name": "svc",
        "trace_id": trace_id,
        "span_id": span_id,
        "parent_span_id": parent,
        "name": name,
        "kind": kind,
        "start_time": start,
        "end_time": start + 1_000_000,
        "attributes": {},
    }


def _write(path: Path, records: list[dict]) -> Path:
    path.write_text(
        "".join(json.dumps(r) + "\n" for r in records),
        encoding="utf-8",
        newline="\n",
    )
    return path


def _one_tree(path: Path) -> Path:
    """root -> two children, all in a single trace."""
    return _write(path, [
        _rec(TRACE_A, "0000000000000001", None, "run", "AGENT", 300),
        _rec(TRACE_A, "0000000000000002", "0000000000000001", "chain", "CHAIN", 100),
        _rec(TRACE_A, "0000000000000003", "0000000000000001", "llm", "LLM", 200),
    ])


def _fragmented(path: Path) -> Path:
    """The shape a lost thread context produces: two independent roots."""
    return _write(path, [
        _rec(TRACE_A, "0000000000000001", None, "run", "AGENT", 300),
        _rec(TRACE_A, "0000000000000002", "0000000000000001", "chain", "CHAIN", 100),
        _rec(TRACE_B, "000000000000000b", None, "sub_task", "TOOL", 50),
    ])


# ---------------------------------------------------------------------------
# max_traces
# ---------------------------------------------------------------------------

def test_max_traces_passes_on_a_single_tree(tmp_path, capsys):
    path = _one_tree(tmp_path / "t.jsonl")

    # quiet=True suppresses the report when everything passes, so ask for it.
    assert verify_export(path, max_traces=1) is True
    out = capsys.readouterr().out
    assert "trace_count: 1" in out
    assert "root_count: 1" in out


def test_max_traces_fails_when_the_run_fragmented(tmp_path, capsys):
    path = _fragmented(tmp_path / "t.jsonl")

    assert verify_export(path, max_traces=1, quiet=True) is False
    out = capsys.readouterr().out
    assert "max_traces=1" in out
    # 2 of the 3 spans are roots: the AGENT root and the orphaned sub_task.
    assert "root_count: 2" in out


def test_max_traces_none_disables_the_check(tmp_path):
    path = _fragmented(tmp_path / "t.jsonl")
    assert verify_export(path, max_traces=None, quiet=True) is True


def test_max_traces_and_min_traces_are_independent(tmp_path):
    path = _one_tree(tmp_path / "t.jsonl")
    assert verify_export(path, min_traces=1, max_traces=1, quiet=True) is True
    assert verify_export(path, min_traces=2, max_traces=5, quiet=True) is False


# ---------------------------------------------------------------------------
# orphan_trace_report
# ---------------------------------------------------------------------------

def test_orphan_trace_report_returns_roots_sorted_by_start_time(tmp_path):
    path = _fragmented(tmp_path / "t.jsonl")

    report = orphan_trace_report(path)
    assert report["trace_count"] == 2
    assert report["span_count"] == 3
    # (trace_id, name, kind, start_time) -- start 50 before start 300
    assert report["roots"] == [
        (TRACE_B, "sub_task", "TOOL", 50),
        (TRACE_A, "run", "AGENT", 300),
    ]


def test_orphan_trace_report_single_tree_has_exactly_one_root(tmp_path):
    report = orphan_trace_report(_one_tree(tmp_path / "t.jsonl"))
    assert report["trace_count"] == 1
    assert [r[1] for r in report["roots"]] == ["run"]


def test_orphan_trace_report_missing_file_is_empty_not_fatal(tmp_path):
    report = orphan_trace_report(tmp_path / "nope.jsonl")
    assert report == {
        "path": str(tmp_path / "nope.jsonl"),
        "span_count": 0,
        "trace_count": 0,
        "roots": [],
    }


def test_orphan_trace_report_tolerates_a_missing_kind(tmp_path):
    rec = _rec(TRACE_A, "0000000000000001", None, "run", None, 10)
    report = orphan_trace_report(_write(tmp_path / "t.jsonl", [rec]))
    assert report["roots"] == [(TRACE_A, "run", "UNKNOWN", 10)]


# ---------------------------------------------------------------------------
# CLI plumbing
# ---------------------------------------------------------------------------

def _cli(tmp_path: Path, *args: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT)}
    return subprocess.run(
        [sys.executable, "-m", "agent_monitor", "verify", *args],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
        check=False,
    )


def test_cli_verify_max_traces_is_ci_usable(tmp_path):
    _one_tree(tmp_path / "good.jsonl")
    _fragmented(tmp_path / "bad.jsonl")

    ok = _cli(tmp_path, "--trace-file", "good.jsonl", "--max-traces", "1")
    assert ok.returncode == 0, ok.stdout + ok.stderr

    bad = _cli(tmp_path, "--trace-file", "bad.jsonl", "--max-traces", "1")
    assert bad.returncode == 1
    assert "max_traces=1" in bad.stdout

    # Without --max-traces the same fragmented file still passes (back-compat).
    legacy = _cli(tmp_path, "--trace-file", "bad.jsonl")
    assert legacy.returncode == 0, legacy.stdout