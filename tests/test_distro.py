"""Tests for the zero-code OpenTelemetry distro.

The full entry-point path --

    OTEL_PYTHON_DISTRO=agent-monitor opentelemetry-instrument python run.py

-- only works once the distribution is (re)installed, because entry points are
read from the installed dist-info rather than from the source tree. That is
verified manually (see the PR description); what is covered here is the part
that carries the design: ``_configure()`` installs a real provider, keeps
``monitor()`` open for the process lifetime, and turns a user script's own
``monitor()`` into a harmless no-op.

``agent_monitor.distro`` is imported only inside child processes on purpose:
importing it at collection time would make ``opentelemetry-instrumentation`` a
hard dependency of the whole test suite.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = REPO_ROOT / "pyproject.toml"

OVERRIDE_WARNING = "Overriding of current TracerProvider"

DISTRO_APP = '''
import json, os
from agent_monitor.distro import AgentMonitorDistro
from agent_monitor import monitor
from opentelemetry import trace as T

AgentMonitorDistro()._configure()
AgentMonitorDistro()._configure()      # idempotent: must not enter twice

with T.get_tracer("app").start_as_current_span(
    "zero_code_span", attributes={"openinference.span.kind": "CHAIN"}
):
    pass

# A user script that instruments itself must degrade to a no-op instead of
# fighting over the one global provider this process gets.
with monitor(service_name="inner-agent", exporter="jsonl", trace_file="inner.jsonl") as tracer:
    with tracer.start_as_current_span("from_user_monitor"):
        pass

rows = [json.loads(l) for l in open("spans.jsonl", encoding="utf-8") if l.strip()]
print("PROVIDER", type(T.get_tracer_provider()).__name__)
print("ROWS", [(r["name"], r["kind"], r["service_name"]) for r in rows])
print("INNER_EXISTS", os.path.isfile("inner.jsonl"))
'''

RESOLVE_CONFIG = '''
from agent_monitor.distro import _resolve_config
c = _resolve_config()
print("CFG", c["trace_file"], c["exporter"], repr(c["service_name"]))
'''


def _run(code: str, tmp_path: Path, extra_env: dict | None = None) -> subprocess.CompletedProcess:
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT)}
    env.update(extra_env or {})
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


def test_distro_installs_a_real_provider_and_keeps_monitor_open(tmp_path):
    proc = _run(
        DISTRO_APP,
        tmp_path,
        {
            "AGENT_MONITOR_TRACE_FILE": "spans.jsonl",
            "AGENT_MONITOR_SERVICE_NAME": "zero-code-app",
        },
    )
    assert proc.returncode == 0, proc.stderr
    assert OVERRIDE_WARNING not in proc.stderr
    assert "PROVIDER TracerProvider" in proc.stdout
    # Everything -- including the span emitted from inside the user's own,
    # now-nested monitor() -- reached the distro's file, flushed at exit.
    assert (
        "ROWS [('zero_code_span', 'CHAIN', 'zero-code-app'), "
        "('from_user_monitor', 'UNKNOWN', 'zero-code-app')]"
    ) in proc.stdout
    # The inner monitor() asked for its own file and was ignored, as documented.
    assert "INNER_EXISTS False" in proc.stdout
    assert "nested monitor(): ignoring" in proc.stderr


def test_distro_config_defaults_to_cwd_name_and_latest_traces(tmp_path):
    proc = _run(
        RESOLVE_CONFIG,
        tmp_path,
        {
            "AGENT_MONITOR_TRACE_FILE": "",
            "AGENT_MONITOR_SERVICE_NAME": "",
            "OTEL_SERVICE_NAME": "",
            "AGENT_MONITOR_EXPORTER": "",
        },
    )
    assert proc.returncode == 0, proc.stderr
    assert f"CFG None jsonl {tmp_path.name!r}" in proc.stdout


def test_distro_service_name_precedence(tmp_path):
    blank = {"AGENT_MONITOR_TRACE_FILE": "", "AGENT_MONITOR_SERVICE_NAME": ""}

    explicit = _run(
        RESOLVE_CONFIG, tmp_path,
        {**blank, "OTEL_SERVICE_NAME": "from-otel",
         "AGENT_MONITOR_SERVICE_NAME": "from-agent-monitor"},
    )
    assert "CFG None jsonl 'from-agent-monitor'" in explicit.stdout, explicit.stderr

    inherited = _run(RESOLVE_CONFIG, tmp_path, {**blank, "OTEL_SERVICE_NAME": "from-otel"})
    assert "CFG None jsonl 'from-otel'" in inherited.stdout, inherited.stderr


def test_pyproject_registers_the_distro_entry_point():
    """The entry point is what makes `opentelemetry-instrument` pick us up."""
    src = PYPROJECT.read_text(encoding="utf-8")
    assert "[project.entry-points.opentelemetry_distro]" in src
    assert 'agent-monitor = "agent_monitor.distro:AgentMonitorDistro"' in src


@pytest.mark.skipif(sys.version_info < (3, 11), reason="tomllib is 3.11+")
def test_pyproject_declares_opentelemetry_instrumentation_as_core_dependency():
    """`opentelemetry-instrument`, BaseDistro and the sitecustomize hook all come
    from opentelemetry-instrumentation, so the zero-code path must not depend on
    a framework extra dragging it in transitively.
    """
    import tomllib

    with open(PYPROJECT, "rb") as fh:
        data = tomllib.load(fh)

    deps = data["project"]["dependencies"]
    assert any(d.startswith("opentelemetry-instrumentation") for d in deps), deps
    assert (
        data["project"]["entry-points"]["opentelemetry_distro"]["agent-monitor"]
        == "agent_monitor.distro:AgentMonitorDistro"
    )