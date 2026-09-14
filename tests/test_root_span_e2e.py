"""End-to-end test for the root span in the generated ``instrument.py``.

The root span is what turns "one trace per LLM call" into "one trace per agent
run", so it is asserted end to end: render the template, run it as a real
process, and inspect the JSONL it produced.

A subprocess is used on purpose. OpenTelemetry allows ``set_tracer_provider()``
only once per process, so calling ``monitor()`` from several tests inside the
same pytest process would silently keep pointing at the first (already shut
down) provider.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import agent_monitor.__main__ as cli

REPO_ROOT = Path(__file__).resolve().parent.parent

# A stand-in for the user's own ``run.py``: no framework needed, the child span
# comes from the SDK's own @span decorator.
RUN_PY = '''\
from agent_monitor import span


@span("child_tool", kind="TOOL")
def do_work():
    return "ok"


def main():
    return do_work()
'''


def _render(tmp_path: Path, frameworks=()) -> str:
    content = cli._render_instrument_template(list(frameworks))
    (tmp_path / "instrument.py").write_text(content, encoding="utf-8", newline="\n")
    return content


def _env() -> dict:
    """Point children at this working tree, not at any installed copy."""
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT)}
    # Keep the thread-context default under the tests' control, not the shell's.
    env.pop("AGENT_MONITOR_THREAD_CONTEXT", None)
    return env


def _run(tmp_path: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "instrument.py"],
        cwd=tmp_path,
        env=_env(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
        check=False,
    )


def _run_cli(tmp_path: Path, *args: str) -> subprocess.CompletedProcess:
    """`python -m agent_monitor run ...` in a child process."""
    return subprocess.run(
        [sys.executable, "-m", "agent_monitor", "run", *args],
        cwd=tmp_path,
        env=_env(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
        check=False,
    )


def _load(tmp_path: Path) -> list:
    trace_file = tmp_path / "latest_traces.jsonl"
    if not trace_file.is_file():
        return []
    return [
        json.loads(line)
        for line in trace_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _quoted(text: str, name: str) -> str:
    """Read a ``NAME = "value"`` constant back out of the rendered template."""
    match = re.search(name + r'\s*=\s*"([^"]+)"', text)
    assert match, f"{name} not found in the rendered template"
    return match.group(1)


def test_generated_instrument_wraps_the_run_in_one_agent_root_span(tmp_path):
    content = _render(tmp_path)
    root_span = _quoted(content, "ROOT_SPAN")
    service_name = _quoted(content, "SERVICE_NAME")
    (tmp_path / "run.py").write_text(RUN_PY, encoding="utf-8")

    proc = _run(tmp_path)
    assert proc.returncode == 0, proc.stderr

    spans = _load(tmp_path)
    assert spans, "the generated instrument.py produced no spans"

    # The whole run is one trace, not one trace per call.
    assert len({s["trace_id"] for s in spans}) == 1

    roots = [s for s in spans if not s.get("parent_span_id")]
    assert len(roots) == 1, "expected exactly one root span"
    root = roots[0]
    assert root["name"] == root_span
    assert root["kind"] == "AGENT"
    assert root["attributes"]["openinference.span.kind"] == "AGENT"
    assert root["service_name"] == service_name
    # A finished run must report OK, otherwise the viewer shows an hourglass.
    assert root["status"] == "OK"

    # The child span really is nested inside it.
    children = [s for s in spans if s.get("parent_span_id") == root["span_id"]]
    assert children, "no child span was attached to the root span"
    assert {c["trace_id"] for c in children} == {root["trace_id"]}


def test_generated_instrument_runs_without_an_entry_point(tmp_path):
    "An unedited instrument.py must exit 0 instead of raising ImportError."
    _render(tmp_path)

    proc = _run(tmp_path)

    assert proc.returncode == 0, proc.stderr
    assert "edit instrument.py" in proc.stdout
    assert _load(tmp_path) == []


CLI_SCRIPT = """\
from agent_monitor import span


@span("child_tool", kind="TOOL")
def do_work():
    return "ok"


do_work()
"""

SELF_INSTRUMENTING_SCRIPT = """\
from agent_monitor import monitor, span


@span("child_tool", kind="TOOL")
def do_work():
    return "ok"


with monitor(service_name="inner", exporter="jsonl", trace_file="inner.jsonl") as tracer:
    with tracer.start_as_current_span("user_span"):
        do_work()
"""


def test_cli_run_wraps_the_script_in_one_agent_root_span(tmp_path):
    "`run` needs no code in the script and still produces one trace per run."
    (tmp_path / "my_agent.py").write_text(CLI_SCRIPT, encoding="utf-8")

    proc = _run_cli(tmp_path, "my_agent.py")
    assert proc.returncode == 0, proc.stderr

    spans = _load(tmp_path)
    assert len({s["trace_id"] for s in spans}) == 1

    roots = [s for s in spans if not s.get("parent_span_id")]
    assert len(roots) == 1, "expected exactly one root span"
    root = roots[0]
    assert root["name"] == "my_agent"          # default: the script stem
    assert root["kind"] == "AGENT"
    assert root["status"] == "OK"
    assert root["service_name"] == "my_agent"  # --service-name falls back too
    assert {s["name"] for s in spans} == {"my_agent", "child_tool"}


def test_cli_run_root_span_name_can_be_overridden(tmp_path):
    (tmp_path / "my_agent.py").write_text(CLI_SCRIPT, encoding="utf-8")

    proc = _run_cli(tmp_path, "--root-span", "claim_verification", "my_agent.py")
    assert proc.returncode == 0, proc.stderr

    roots = [s for s in _load(tmp_path) if not s.get("parent_span_id")]
    assert [r["name"] for r in roots] == ["claim_verification"]


def test_cli_run_no_root_span_leaves_the_script_rooted(tmp_path):
    """For frameworks that already emit a root: --no-root-span adds no wrapper."""
    (tmp_path / "my_agent.py").write_text(CLI_SCRIPT, encoding="utf-8")

    proc = _run_cli(tmp_path, "--no-root-span", "my_agent.py")
    assert proc.returncode == 0, proc.stderr

    spans = _load(tmp_path)
    assert [s["name"] for s in spans] == ["child_tool"]
    assert not spans[0].get("parent_span_id")


def test_cli_run_tolerates_a_script_that_instruments_itself(tmp_path):
    """The point of monitor() being re-entrant.

    The CLI can wrap a script that already calls monitor() without either side
    breaking the other: one trace, one root, and the inner call's own file is
    never created.
    """
    (tmp_path / "self_traced.py").write_text(SELF_INSTRUMENTING_SCRIPT, encoding="utf-8")

    proc = _run_cli(tmp_path, "self_traced.py")
    assert proc.returncode == 0, proc.stderr
    assert "Overriding of current TracerProvider" not in proc.stderr

    spans = _load(tmp_path)
    assert len({s["trace_id"] for s in spans}) == 1
    roots = [s for s in spans if not s.get("parent_span_id")]
    assert [r["name"] for r in roots] == ["self_traced"]
    assert {s["name"] for s in spans} == {"self_traced", "user_span", "child_tool"}
    assert not (tmp_path / "inner.jsonl").exists()
    assert "nested monitor(): ignoring" in proc.stderr


def test_cli_run_forwards_arguments_written_after_the_script(tmp_path):
    """Everything after the script path belongs to the script (nargs=REMAINDER).

    This is also why every `run` flag has to be written BEFORE the script.
    """
    (tmp_path / "echo_args.py").write_text(
        "import sys\n"
        "from agent_monitor import span\n"
        "\n"
        "@span('echo', kind='TOOL')\n"
        "def go():\n"
        "    return sys.argv[1:]\n"
        "\n"
        "print('ARGV', go())\n",
        encoding="utf-8",
    )

    proc = _run_cli(tmp_path, "--root-span", "echo_root", "echo_args.py", "--flag", "value")
    assert proc.returncode == 0, proc.stderr
    assert "ARGV ['--flag', 'value']" in proc.stdout

    roots = [s for s in _load(tmp_path) if not s.get("parent_span_id")]
    assert [r["name"] for r in roots] == ["echo_root"]


POOL_SCRIPT = """\
from concurrent.futures import ThreadPoolExecutor

from agent_monitor import span


@span("sub_task", kind="TOOL")
def sub(i):
    return i


with ThreadPoolExecutor(max_workers=2) as ex:
    list(ex.map(sub, range(3)))
"""


def test_cli_run_keeps_thread_pool_tasks_in_one_trace(tmp_path):
    """The regression behind "184 spans but 56 traces".

    ``ThreadPoolExecutor.submit()`` does not copy contextvars and OTel keeps the
    current span in one, so every task used to start its own trace even though
    the CLI had injected a root span on the calling thread. monitor() now patches
    submit(), so the whole run is a single tree.
    """
    (tmp_path / "pool_agent.py").write_text(POOL_SCRIPT, encoding="utf-8")

    proc = _run_cli(tmp_path, "--root-span", "fanout_root", "pool_agent.py")
    assert proc.returncode == 0, proc.stderr
    assert "separate traces" not in proc.stderr   # no orphan-root warning

    spans = _load(tmp_path)
    assert len({s["trace_id"] for s in spans}) == 1

    roots = [s for s in spans if not s.get("parent_span_id")]
    assert [r["name"] for r in roots] == ["fanout_root"]
    tasks = [s for s in spans if s["name"] == "sub_task"]
    assert len(tasks) == 3
    for task in tasks:
        assert task["parent_span_id"] == roots[0]["span_id"]


def test_cli_run_no_thread_context_reproduces_orphans_and_warns(tmp_path):
    """Control for the test above, and the escape hatch's contract.

    ``--no-thread-context`` must both restore the old (broken) shape AND say so,
    instead of leaving the user to wonder where 4 traces came from.
    """
    (tmp_path / "pool_agent.py").write_text(POOL_SCRIPT, encoding="utf-8")

    proc = _run_cli(
        tmp_path, "--no-thread-context", "--root-span", "fanout_root", "pool_agent.py"
    )
    assert proc.returncode == 0, proc.stderr

    spans = _load(tmp_path)
    assert len({s["trace_id"] for s in spans}) == 4      # root + 3 orphan tasks
    assert len([s for s in spans if not s.get("parent_span_id")]) == 4

    assert "4 separate traces" in proc.stderr
    assert "fanout_root" in proc.stderr
    assert "sub_task" in proc.stderr
    assert "--no-thread-context" in proc.stderr


def test_cli_run_thread_flag_must_precede_the_script(tmp_path):
    """nargs=REMAINDER swallows anything written after the script path."""
    (tmp_path / "pool_agent.py").write_text(POOL_SCRIPT, encoding="utf-8")

    proc = _run_cli(tmp_path, "pool_agent.py", "--no-thread-context")
    assert proc.returncode == 0, proc.stderr

    # The flag went to the script (which ignores argv), so context still
    # propagated and the run is still a single trace.
    assert len({s["trace_id"] for s in _load(tmp_path)}) == 1


EXIT_SCRIPT = """\
import sys

from agent_monitor import span


@span("child_tool", kind="TOOL")
def do_work():
    return "ok"


def main():
    do_work()
    return {code}


if __name__ == "__main__":
    raise SystemExit(main())
"""


def test_cli_run_treats_a_cli_style_sys_exit_as_success(tmp_path):
    """`raise SystemExit(main())` must not leave the root span UNSET.

    Found by running a real agent (its run.py ends with exactly that line):
    OpenTelemetry records Exception but deliberately never BaseException, so
    the root span ended UNSET -- and every viewer renders UNSET as "still
    running". The run is a success and has to say so.
    """
    (tmp_path / "cli_agent.py").write_text(
        EXIT_SCRIPT.format(code=0), encoding="utf-8"
    )

    proc = _run_cli(tmp_path, "--root-span", "cli_root", "cli_agent.py")
    assert proc.returncode == 0, proc.stderr

    roots = [s for s in _load(tmp_path) if not s.get("parent_span_id")]
    assert [r["name"] for r in roots] == ["cli_root"]
    assert roots[0]["kind"] == "AGENT"
    assert roots[0]["status"] == "OK"


def test_cli_run_marks_a_nonzero_exit_as_error(tmp_path):
    """The other half: a real failure keeps its exit code and says ERROR."""
    (tmp_path / "failing_agent.py").write_text(
        EXIT_SCRIPT.format(code=3), encoding="utf-8"
    )

    proc = _run_cli(tmp_path, "--root-span", "cli_root", "failing_agent.py")
    assert proc.returncode == 3, proc.stderr

    roots = [s for s in _load(tmp_path) if not s.get("parent_span_id")]
    assert [r["status"] for r in roots] == ["ERROR"]
