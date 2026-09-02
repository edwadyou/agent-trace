"""Regression tests for monitor() global state behaviour."""
from __future__ import annotations
from pathlib import Path

from agent_monitor import jsonl_exporter
from agent_monitor.monitor import monitor


def test_two_monitors_same_file_dont_truncate_twice(tmp_path):
    "Two consecutive monitor() calls do NOT re-truncate a file already truncated."
    f = str(tmp_path / "shared.jsonl")
    with monitor(service_name="first", exporter="jsonl", trace_file=f):
        pass
    with monitor(service_name="second", exporter="jsonl", trace_file=f, verbose=False):
        pass
    matching = [k for k in jsonl_exporter._TRUNCATED_FILES if k.endswith("shared.jsonl")]
    assert len(matching) == 1


def test_monitor_no_crash_on_simple_span(tmp_path):
    "Smoke test: monitor() with a real span does not crash."
    from opentelemetry import trace as otel_trace
    f = str(tmp_path / "smoke.jsonl")
    with monitor(service_name="smoke", exporter="jsonl", trace_file=f):
        tracer = otel_trace.get_tracer("smoke")
        with tracer.start_as_current_span("foo"):
            pass
