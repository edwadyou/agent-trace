"""Thread-boundary context propagation (``agent_monitor._threadctx``).

Why this file exists: a run that WAS wrapped in a root span still produced 56
separate traces. The cause was not the root span -- it was a bare
``ThreadPoolExecutor``. ``submit()`` does not copy contextvars, and OpenTelemetry
keeps the current span in a contextvar, so every task handed to a long-lived pool
worker started its own trace tree. ``_threadctx`` copies the context at *submit*
time instead, exactly like ``langchain_core``'s ``ContextThreadPoolExecutor``.

Structural assertions run in-process. Everything that inspects *exported spans*
runs in a subprocess, because OpenTelemetry allows one global TracerProvider per
process and this pytest process may already have spent its.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from agent_monitor import _threadctx
from agent_monitor.monitor import _thread_context_default

REPO_ROOT = Path(__file__).resolve().parent.parent

ENV_VAR = "AGENT_MONITOR_THREAD_CONTEXT"


@pytest.fixture(autouse=True)
def _clean_threadctx():
    """Never leak the stdlib patch into another test."""
    _threadctx.uninstall()
    yield
    _threadctx.uninstall()


def _run(code: str, tmp_path: Path, **env_extra: str) -> subprocess.CompletedProcess:
    """Run a snippet as a child process that gets a fresh provider slot."""
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT)}
    env.pop(ENV_VAR, None)
    env.update(env_extra)
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


def _load(tmp_path: Path, name: str = "t.jsonl") -> list:
    path = tmp_path / name
    if not path.is_file():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


# ---------------------------------------------------------------------------
# install() / uninstall() bookkeeping -- no provider needed
# ---------------------------------------------------------------------------

def test_install_patches_both_primitives_and_is_idempotent():
    original_submit = ThreadPoolExecutor.submit
    original_start = threading.Thread.start

    assert _threadctx.install() is True
    patched_submit = ThreadPoolExecutor.submit
    patched_start = threading.Thread.start
    assert patched_submit is not original_submit
    assert patched_start is not original_start
    assert getattr(patched_submit, "_agent_monitor_patched", False) is True
    assert getattr(patched_start, "_agent_monitor_patched", False) is True
    assert _threadctx.is_installed() is True

    # A second install must NOT wrap the first one (that would copy twice).
    assert _threadctx.install() is False
    assert ThreadPoolExecutor.submit is patched_submit
    assert threading.Thread.start is patched_start

    _threadctx.uninstall()
    assert ThreadPoolExecutor.submit is original_submit
    assert threading.Thread.start is original_start
    assert _threadctx.is_installed() is False


def test_uninstall_without_install_is_a_noop():
    original_submit = ThreadPoolExecutor.submit
    _threadctx.uninstall()
    _threadctx.uninstall()
    assert ThreadPoolExecutor.submit is original_submit
    assert _threadctx.is_installed() is False


def test_install_does_not_stack_on_a_foreign_patch():
    """If another library already owns submit(), leave it alone -- and keep it."""
    original_submit = ThreadPoolExecutor.submit

    def foreign(self, fn, *args, **kwargs):
        return original_submit(self, fn, *args, **kwargs)

    foreign._agent_monitor_patched = True
    ThreadPoolExecutor.submit = foreign
    try:
        assert _threadctx.install() is False
        assert ThreadPoolExecutor.submit is foreign
        _threadctx.uninstall()          # must not clobber somebody else's patch
        assert ThreadPoolExecutor.submit is foreign
    finally:
        ThreadPoolExecutor.submit = original_submit


@pytest.mark.parametrize(
    "value,expected",
    [
        (None, True), ("", True), ("1", True), ("true", True), ("TRUE", True),
        ("yes", True), ("on", True), ("banana", True),
        ("0", False), ("false", False), ("FALSE", False), ("no", False),
        ("No", False), ("off", False), (" 0 ", False),
    ],
)
def test_thread_context_default_reads_the_env(monkeypatch, value, expected):
    if value is None:
        monkeypatch.delenv(ENV_VAR, raising=False)
    else:
        monkeypatch.setenv(ENV_VAR, value)
    assert _thread_context_default() is expected


# ---------------------------------------------------------------------------
# Real span nesting -- subprocess only
# ---------------------------------------------------------------------------

FANOUT = '''\
import threading
from concurrent.futures import ThreadPoolExecutor

from agent_monitor.monitor import monitor


def child(tracer, tag):
    with tracer.start_as_current_span(
        "task_" + tag, attributes={"openinference.span.kind": "TOOL"}
    ):
        pass


with monitor(service_name="fanout", exporter="jsonl", trace_file="t.jsonl") as tracer:
    with tracer.start_as_current_span(
        "root", attributes={"openinference.span.kind": "AGENT"}
    ):
        with ThreadPoolExecutor(max_workers=3) as ex:
            list(ex.map(lambda tag: child(tracer, tag), ["a", "b", "c"]))
            ex.submit(child, tracer, "submit").result()
        th = threading.Thread(target=child, args=(tracer, "thread"))
        th.start()
        th.join()
'''


def test_pool_and_thread_tasks_stay_in_the_callers_trace(tmp_path):
    proc = _run(FANOUT, tmp_path)
    assert proc.returncode == 0, proc.stderr

    spans = _load(tmp_path)
    assert {s["name"] for s in spans} == {
        "root", "task_a", "task_b", "task_c", "task_submit", "task_thread"
    }
    # One tree, not one per task.
    assert len({s["trace_id"] for s in spans}) == 1

    roots = [s for s in spans if not s.get("parent_span_id")]
    assert [r["name"] for r in roots] == ["root"]
    for s in spans:
        if s["name"].startswith("task_"):
            assert s["parent_span_id"] == roots[0]["span_id"], s["name"]


def test_env_var_off_reproduces_the_orphan_traces(tmp_path):
    """The control that proves the patch -- not luck -- is what merges the trees."""
    proc = _run(FANOUT, tmp_path, **{ENV_VAR: "0"})
    assert proc.returncode == 0, proc.stderr

    spans = _load(tmp_path)
    # root + 5 tasks, each its own trace, because the workers saw an empty context
    assert len({s["trace_id"] for s in spans}) == 6
    assert len([s for s in spans if not s.get("parent_span_id")]) == 6


KWARG_OFF = FANOUT.replace(
    'trace_file="t.jsonl") as tracer',
    'trace_file="t.jsonl", thread_context=False) as tracer',
)


def test_thread_context_false_kwarg_disables_the_patch(tmp_path):
    assert "thread_context=False" in KWARG_OFF
    proc = _run(KWARG_OFF, tmp_path)
    assert proc.returncode == 0, proc.stderr
    assert len({s["trace_id"] for s in _load(tmp_path)}) == 6


LIFECYCLE = '''\
import threading
from concurrent.futures import ThreadPoolExecutor

from agent_monitor import _threadctx
from agent_monitor.monitor import monitor

submit0 = ThreadPoolExecutor.submit
start0 = threading.Thread.start

with monitor(service_name="lc", exporter="jsonl", trace_file="t.jsonl"):
    print("inside", _threadctx.is_installed(),
          ThreadPoolExecutor.submit is not submit0,
          threading.Thread.start is not start0)
    with monitor(service_name="lc", exporter="jsonl", trace_file="t.jsonl"):
        print("nested", _threadctx.is_installed())
    print("after_nested", _threadctx.is_installed(),
          ThreadPoolExecutor.submit is not submit0)
print("after_outer", _threadctx.is_installed(),
      ThreadPoolExecutor.submit is submit0, threading.Thread.start is start0)
'''


def test_monitor_installs_on_enter_and_uninstalls_only_at_depth_zero(tmp_path):
    proc = _run(LIFECYCLE, tmp_path)
    assert proc.returncode == 0, proc.stderr
    lines = proc.stdout.split()
    assert lines == ["inside", "True", "True", "True",
                     "nested", "True",
                     "after_nested", "True", "True",
                     "after_outer", "False", "True", "True"]


NESTED_CONFLICT = '''\
from agent_monitor.monitor import monitor

with monitor(service_name="outer", exporter="jsonl", trace_file="t.jsonl"):
    with monitor(service_name="outer", exporter="jsonl", trace_file="t.jsonl",
                 thread_context=False):
        pass
'''


def test_nested_monitor_warns_when_it_disagrees_about_thread_context(tmp_path):
    proc = _run(NESTED_CONFLICT, tmp_path)
    assert proc.returncode == 0, proc.stderr
    assert "nested monitor(): ignoring" in proc.stderr
    assert "thread_context=False (keeping True)" in proc.stderr
    # The outer call still owns the process, so the patch is still in place.
    assert "Overriding of current TracerProvider" not in proc.stderr