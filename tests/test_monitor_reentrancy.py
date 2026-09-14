"""Re-entrancy tests for ``monitor()``.

OpenTelemetry lets a process install its global ``TracerProvider`` exactly once,
so a nested ``monitor()`` used to be actively harmful: its own file stayed
empty, its spans leaked into the outer file, and its exit un-instrumented the
outer call's monkey-patches. These tests pin the fixed behaviour.

The in-process tests only touch agent_monitor's own bookkeeping (``_ACTIVE``)
and the OTel warning log, so they pass regardless of whether this pytest process
already installed a provider. Everything that asserts on *exported spans* runs
in a subprocess, because the provider slot is a one-shot, process-wide resource.
"""
from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

import importlib

from agent_monitor.monitor import monitor

# `agent_monitor.monitor` is shadowed by the re-exported function of the same
# name, so reach the module through importlib to inspect its private state.
monitor_mod = importlib.import_module("agent_monitor.monitor")

REPO_ROOT = Path(__file__).resolve().parent.parent

OVERRIDE_WARNING = "Overriding of current TracerProvider"
SEQUENTIAL_WARNING = "one-and-only global TracerProvider"


def _run(code: str, tmp_path: Path) -> subprocess.CompletedProcess:
    """Run a snippet as a child process that gets a fresh provider slot."""
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT)}
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
        check=False,
    )


def _overriding(caplog) -> int:
    return len([r for r in caplog.records if OVERRIDE_WARNING in r.getMessage()])


def test_nested_monitor_reuses_the_outer_activation(caplog, capsys, tmp_path):
    "A nested monitor() is a no-op: same tracer, no second provider, loud config."
    caplog.set_level(logging.WARNING, logger="opentelemetry.trace")
    outer_file = tmp_path / "outer.jsonl"
    inner_file = tmp_path / "inner.jsonl"

    with monitor(service_name="outer", exporter="jsonl", trace_file=str(outer_file)) as outer_tracer:
        assert monitor_mod._ACTIVE is not None
        assert monitor_mod._ACTIVE["depth"] == 1
        before = _overriding(caplog)

        with monitor(service_name="inner", exporter="jsonl", trace_file=str(inner_file)) as inner_tracer:
            assert monitor_mod._ACTIVE["depth"] == 2
            # The inner call hands back the very same tracer ...
            assert inner_tracer is outer_tracer
            # ... and never asks OTel to replace the global provider.
            assert _overriding(caplog) == before

        assert monitor_mod._ACTIVE["depth"] == 1
        assert _overriding(caplog) == before

    assert monitor_mod._ACTIVE is None

    err = capsys.readouterr().err
    # Asking for a different service_name / trace_file inside a nested call is
    # reported, not silently swallowed.
    assert "nested monitor(): ignoring" in err
    assert "service_name='inner'" in err
    # The inner exporter was never constructed, so its file does not exist.
    assert not inner_file.exists()


def test_plain_nested_monitor_is_quiet(capsys, tmp_path):
    "`with monitor():` inside a monitor() must not warn about anything."
    shared = tmp_path / "shared.jsonl"

    with monitor(service_name="outer", exporter="jsonl", trace_file=str(shared)):
        with monitor():
            pass

    err = capsys.readouterr().err
    assert "nested monitor(): ignoring" not in err


NESTED = '''
import json, os
from agent_monitor import monitor

with monitor(service_name="outer", exporter="jsonl", trace_file="outer.jsonl") as tracer:
    with tracer.start_as_current_span("before_nested"):
        pass
    with monitor(service_name="inner", exporter="jsonl", trace_file="inner.jsonl") as inner:
        with inner.start_as_current_span("inside_nested"):
            pass
    with tracer.start_as_current_span("after_nested"):
        pass

rows = [json.loads(l) for l in open("outer.jsonl", encoding="utf-8") if l.strip()]
print("NAMES", [r["name"] for r in rows])
print("INNER_EXISTS", os.path.isfile("inner.jsonl"))
'''


def test_nested_monitor_exports_everything_to_the_outer_file(tmp_path):
    """The regression this whole design exists for.

    Before: the inner file was created but stayed empty, its spans landed in the
    outer file anyway, and the inner exit tore down the outer call's patches --
    so ``after_nested`` was the span that went missing.
    """
    proc = _run(NESTED, tmp_path)
    assert proc.returncode == 0, proc.stderr
    assert OVERRIDE_WARNING not in proc.stderr
    assert SEQUENTIAL_WARNING not in proc.stderr
    assert "NAMES ['before_nested', 'inside_nested', 'after_nested']" in proc.stdout
    assert "INNER_EXISTS False" in proc.stdout


SEQUENTIAL = '''
import json, os
from agent_monitor import monitor
from opentelemetry import trace as T

with monitor(service_name="first", exporter="jsonl", trace_file="first.jsonl"):
    with T.get_tracer("t").start_as_current_span("one"):
        pass
with monitor(service_name="second", exporter="jsonl", trace_file="second.jsonl"):
    with T.get_tracer("t").start_as_current_span("two"):
        pass

def names(p):
    if not os.path.isfile(p):
        return "MISSING"
    return [json.loads(l)["name"] for l in open(p, encoding="utf-8") if l.strip()]

print("FIRST", names("first.jsonl"))
print("SECOND", names("second.jsonl"))
'''


def test_sequential_monitor_says_the_second_cannot_redirect_spans(tmp_path):
    """Two blocks one AFTER another still share one provider -- now loudly.

    OTel cannot replace a global provider, so the second block's file stays
    empty. That is a documented limitation, not a supported layout; the point of
    this test is that we say so instead of failing silently.
    """
    proc = _run(SEQUENTIAL, tmp_path)
    assert proc.returncode == 0, proc.stderr
    assert SEQUENTIAL_WARNING in proc.stderr
    assert "FIRST ['one', 'two']" in proc.stdout
    assert "SECOND []" in proc.stdout