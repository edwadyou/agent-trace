# -*- coding: utf-8 -*-
"""Tests for the instrumentor allow-list (``--instrumentors`` / env var).

Why this exists: two instrumentors can cover the *same* call.  A langchain app
built on langchain-openai emits an LLM span from the langchain instrumentor
(``ChatOpenAI``) and a second one from the openai instrumentor
(``ChatCompletion``) around the very same request -- on the real 195-span trace
that was 28 duplicate spans, and 28 extra siblings hanging off the root, which
was a large part of why the activity diagram was unreadable.  Neither package
suppresses the other, so the user gets a switch.
"""
from __future__ import annotations

import importlib
import os
import subprocess
import sys
from pathlib import Path

import pytest

import agent_monitor.__main__ as cli

# `agent_monitor.monitor` is shadowed by the re-exported function of the same
# name, so reach the module through importlib to inspect its private state.
monitor_mod = importlib.import_module("agent_monitor.monitor")

REPO_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# parsing: CLI flag and environment variable
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("raw,expected", [
    (None, None),
    ("", None),
    ("all", None),
    ("auto", None),
    ("*", None),
    ("langchain", ["langchain"]),
    ("langchain, openai", ["langchain", "openai"]),
    (" langchain ;; openai ", ["langchain", "openai"]),
])
def test_cli_flag_parsing(raw, expected):
    assert cli._parse_instrumentors(raw) == expected


@pytest.mark.parametrize("value,expected", [
    (None, None),
    ("", None),
    ("all", None),
    ("langchain", ["langchain"]),
    ("langchain,openai", ["langchain", "openai"]),
])
def test_env_allowlist(monkeypatch, value, expected):
    if value is None:
        monkeypatch.delenv(monitor_mod._INSTRUMENTORS_ENV, raising=False)
    else:
        monkeypatch.setenv(monitor_mod._INSTRUMENTORS_ENV, value)
    assert monitor_mod._instrumentor_allowlist() == expected


# ---------------------------------------------------------------------------
# filtering
# ---------------------------------------------------------------------------

def test_restrict_keeps_only_allowed_names():
    assert monitor_mod._restrict_instrumentors(
        ["langchain", "openai"], ["langchain"]) == ["langchain"]
    # order follows the resolved list, not the allow-list
    assert monitor_mod._restrict_instrumentors(
        ["langchain", "openai"], ["openai", "langchain"]) == ["langchain", "openai"]
    # no allow-list at all -> untouched
    assert monitor_mod._restrict_instrumentors(
        ["langchain", "openai"], None) == ["langchain", "openai"]


def test_restrict_turns_the_install_everything_case_into_the_allowlist():
    """``instrumentors is None`` means "all installed" -- the one case the
    allow-list has to *become* the list rather than filter it."""
    assert monitor_mod._restrict_instrumentors(None, ["langchain"]) == ["langchain"]


def test_restrict_warns_when_it_matches_nothing(capsys):
    assert monitor_mod._restrict_instrumentors(["langchain"], ["openai"]) == []
    err = capsys.readouterr().err
    assert "matched none of the instrumentors" in err
    assert "openai" in err
    assert "nothing will be instrumented" in err


# ---------------------------------------------------------------------------
# integration: monitor() actually narrows what it activates
# ---------------------------------------------------------------------------

def _capture_auto_instrument(monkeypatch, seen):
    def fake(*, tracer_provider, instrumentors=None, verbose=False):
        seen["instrumentors"] = instrumentors
        return []
    monkeypatch.setattr(monitor_mod, "_auto_instrument", fake)


def test_allowlist_narrows_the_auto_detected_set(monkeypatch, tmp_path):
    seen = {}
    _capture_auto_instrument(monkeypatch, seen)
    monkeypatch.setattr("agent_monitor._detect.detect_compatible",
                        lambda *a, **k: ["langchain", "openai"])
    monkeypatch.setenv(monitor_mod._INSTRUMENTORS_ENV, "langchain")

    with monitor_mod.monitor(service_name="allowlist-test", auto_instrument=True,
                             auto_detect=True, exporter="jsonl",
                             trace_file=str(tmp_path / "t.jsonl")):
        pass

    assert seen["instrumentors"] == ["langchain"], seen


def test_allowlist_narrows_the_instrument_everything_fallback(monkeypatch, tmp_path):
    """With auto-detect off, ``instrumentors=None`` means every installed
    instrumentor; the allow-list must still win."""
    seen = {}
    _capture_auto_instrument(monkeypatch, seen)
    monkeypatch.setenv(monitor_mod._INSTRUMENTORS_ENV, "langchain")

    with monitor_mod.monitor(service_name="allowlist-test", auto_instrument=True,
                             exporter="jsonl",
                             trace_file=str(tmp_path / "t.jsonl")):
        pass

    assert seen["instrumentors"] == ["langchain"], seen


def test_no_allowlist_leaves_the_resolved_set_alone(monkeypatch, tmp_path):
    seen = {}
    _capture_auto_instrument(monkeypatch, seen)
    monkeypatch.delenv(monitor_mod._INSTRUMENTORS_ENV, raising=False)

    with monitor_mod.monitor(service_name="allowlist-test", auto_instrument=True,
                             exporter="jsonl",
                             trace_file=str(tmp_path / "t.jsonl")):
        pass

    assert seen["instrumentors"] is None, seen


def test_an_explicit_instrumentors_argument_is_also_filtered(monkeypatch, tmp_path):
    seen = {}
    _capture_auto_instrument(monkeypatch, seen)
    monkeypatch.setenv(monitor_mod._INSTRUMENTORS_ENV, "langchain")

    with monitor_mod.monitor(service_name="allowlist-test", auto_instrument=True,
                             instrumentors=["langchain", "openai"],
                             exporter="jsonl",
                             trace_file=str(tmp_path / "t.jsonl")):
        pass

    assert seen["instrumentors"] == ["langchain"], seen


# ---------------------------------------------------------------------------
# CLI end to end
# ---------------------------------------------------------------------------

def test_cli_run_announces_the_allowlist_and_skips_auto_detect(tmp_path):
    script = tmp_path / "tiny.py"
    script.write_text("print('wrapped ok')\n", encoding="utf-8")
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT)}
    trace = tmp_path / "t.jsonl"

    proc = subprocess.run(
        [sys.executable, "-m", "agent_monitor", "run",
         "--instrumentors", "langchain",
         "--trace-file", str(trace), str(script)],
        cwd=tmp_path, env=env, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=180, check=False,
    )

    assert proc.returncode == 0, proc.stderr
    assert "wrapped ok" in proc.stdout
    assert "instrumentor allow-list: langchain" in proc.stderr
    # an explicit list makes detection moot, so its advice must not be printed
    assert "auto-detect" not in proc.stderr
    assert trace.is_file()
