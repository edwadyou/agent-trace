r"""agent_monitor CLI entry point.

Usage::

    python -m agent_monitor init  [--framework auto|<name>] [--out PATH]
                                  [--no-install-deps] [--no-install-streamlit]
    python -m agent_monitor run   [--root-span NAME | --no-root-span]
                                  [--no-auto-detect] [--exporter jsonl|console]
                                  [--service-name NAME] [--trace-file PATH]
                                  SCRIPT.py [SCRIPT ARGS...]
                                       # NOTE: every flag must come BEFORE the
                                       # script path -- anything after it is
                                       # forwarded to the script verbatim.
    python -m agent_monitor detect [--json]
    python -m agent_monitor verify [--trace-file PATH] [--min-spans N]
                                   [--require-kind LLM|CHAIN|...]
    python -m agent_monitor view   [--viewer PATH] [--trace-file PATH]
                                   [--no-launch]

Designed so a new agent user can type four commands and be done:

    cd my-new-agent
    python -m agent_monitor init --framework auto
                                   # detects every installed framework, installs
                                   # combined OpenInference extras, then writes
                                   # instrument.py
    python instrument.py            # writes latest_traces.jsonl
    python -m agent_monitor view    # browser live view

Two ways to trace a script WITHOUT touching it:

    python -m agent_monitor run run.py
                                       # one AGENT root span around the whole run
    OTEL_PYTHON_DISTRO=agent-monitor opentelemetry-instrument python run.py
                                       # zero-code: no root span, one trace per
                                       # framework root run

What `init --framework auto` installs:

  1. one combined agent-monitor extra spec for every detected framework,
     e.g. ``agent-monitor[langchain,openai]``
  2. streamlit + streamlit-autorefresh (for the viewer)
  3. if no framework SDK is installed, LangChain demo dependencies as a
     conservative fallback

Use `--no-install-deps` to skip BOTH the framework SDK and the OI
instrumentor (e.g. CI / air-gapped). Use `--no-install-streamlit` to keep
the framework install but skip the viewer deps.

`view` resolves the trace file relative to CWD (./latest_traces.jsonl by
default) and the viewer path relative to this package, so it works from any
working directory. Pass --no-launch to print the resolved command without
executing streamlit.

NOTE: `agent_monitor` itself must already be importable in the current
Python (e.g. `pip install -e "D:\my-projects\agent-monitor[langchain,openai]"`).
`init` will tell you when it is not.
"""
from __future__ import annotations
import argparse
import json
import os
import runpy
import sys
from pathlib import Path


_TEMPLATE_PATH = Path(__file__).resolve().with_name("templates") / "instrument.py"
_FRAMEWORK_PLACEHOLDER = "__AGENT_MONITOR_FRAMEWORKS__"
_FRAMEWORK_ALIASES = {
    "langchain-openai": ("langchain", "openai"),
    "langchain_openai": ("langchain", "openai"),
    "pure": (),
    "pure-no-framework": (),
    "no-framework": (),
}

# ---------- helpers (used by init --framework auto) -----------------------
def _pip_install(pkgs: list[str], *, label: str, editable: bool = False) -> int:
    """Run ``pip install <pkgs>`` and stream its output. Returns rc."""
    import subprocess
    if not pkgs:
        return 0
    options = ["--editable"] if editable else []
    requirement = " ".join(pkgs)
    prefix = "-e " if editable else ""
    print(f"[init] {label}: pip install {prefix}{requirement}")
    try:
        return subprocess.run(
            [sys.executable, "-m", "pip", "install", *options, *pkgs],
            check=False,
        ).returncode
    except FileNotFoundError:
        print("[init] could not invoke pip. Run manually:")
        print(f"        {sys.executable} -m pip install {prefix}{requirement}")
        return 1


def _local_project_root() -> Path | None:
    """Return this package's source project when running from a checkout."""
    root = Path(__file__).resolve().parent.parent
    if (root / "pyproject.toml").is_file() and (root / "agent_monitor" / "__init__.py").is_file():
        return root
    return None


def _agent_monitor_spec(frameworks: list[str]) -> str:
    extras = ",".join(frameworks)
    root = _local_project_root()
    if root is not None:
        return f"{root}[{extras}]"
    return f"agent-monitor[{extras}]"


def _pip_install_extras(frameworks: list[str]) -> int:
    """Install all requested OpenInference extras in one pip invocation."""
    if not frameworks:
        return 0
    return _pip_install(
        [_agent_monitor_spec(frameworks)],
        label=f"installing OpenInference extras for {frameworks}",
        editable=_local_project_root() is not None,
    )


def _pip_install_framework_sdks(frameworks: list[str]) -> int:
    """Install framework SDKs for an environment with no detected frameworks."""
    from ._detect import framework_sdk_packages

    pkgs: list[str] = []
    for framework in frameworks:
        for package in framework_sdk_packages(framework):
            if package not in pkgs:
                pkgs.append(package)
    return _pip_install(pkgs, label=f"installing framework SDKs for {frameworks}")


def _parse_frameworks(value: str) -> list[str]:
    """Parse a CLI framework value into stable, de-duplicated framework keys."""
    from ._detect import list_supported_frameworks

    tokens = [token.strip().lower() for token in value.split(",") if token.strip()]
    if not tokens:
        raise ValueError("no frameworks specified")
    if "auto" in tokens:
        if len(tokens) != 1:
            raise ValueError("'auto' cannot be combined with explicit frameworks")
        return ["auto"]

    frameworks: list[str] = []
    supported = list_supported_frameworks()
    for token in tokens:
        normalized = token.replace("_", "-")
        expanded = _FRAMEWORK_ALIASES.get(normalized, (normalized,))
        for framework in expanded:
            if framework not in supported:
                raise ValueError(f"unknown framework {framework!r}")
            if framework not in frameworks:
                frameworks.append(framework)

    return [framework for framework in supported if framework in frameworks]


def _pip_install_streamlit() -> int:
    """Install streamlit + streamlit-autorefresh for the viewer."""
    return _pip_install(
        ["streamlit", "streamlit-autorefresh"],
        label="installing viewer deps",
    )


def _render_instrument_template(frameworks: list[str]) -> str:
    """Render the packaged template with an explicit instrumentor list."""
    template = _TEMPLATE_PATH.read_text(encoding="utf-8")
    count = template.count(_FRAMEWORK_PLACEHOLDER)
    if count != 1:
        raise RuntimeError(
            f"instrument template must contain {_FRAMEWORK_PLACEHOLDER!r} exactly once; "
            f"found {count}"
        )
    return template.replace(_FRAMEWORK_PLACEHOLDER, json.dumps(list(frameworks)))


def _agent_monitor_importable() -> bool:
    """True if the `agent_monitor` package is importable in this env."""
    try:
        import agent_monitor  # noqa: F401
        return True
    except ImportError:
        return False


# ---------- subcommands ------------------------------------------------------


def cmd_init(args: argparse.Namespace) -> int:
    """One-stop init: detect frameworks, install deps, write
    ``instrument.py`` into CWD.

    Default behaviour (no flags):

        1. use every installed framework (or --framework <name,...>)
        2. pip install agent-monitor[<framework,...>] OpenInference extras
                       + streamlit + streamlit-autorefresh
        3. write a generic instrument.py with an explicit INSTRUMENTORS list

    Flags:
        --no-install-deps       skip the framework SDK + OI instrumentor
        --no-install-streamlit  skip the viewer deps, keep the framework install
    """

    if not _agent_monitor_importable():
        print("[init] agent_monitor is not importable in this Python environment.")
        print("        install it first, e.g.:")
        print("        pip install -e D:/my-projects/agent-monitor")
        print("        (or:  pip install agent-monitor)")
        return 1

    try:
        requested = _parse_frameworks(args.framework)
    except ValueError as exc:
        print(f"[init] {exc}")
        return 2

    fresh_environment = False
    if requested == ["auto"]:
        from ._detect import detect_installed_frameworks, list_supported_frameworks
        detected = detect_installed_frameworks()
        supported = list_supported_frameworks()
        requested = [framework for framework in supported if framework in detected]
        if requested:
            print(
                f"[init] auto: detected framework SDKs = {requested}; "
                "will install combined OpenInference extras"
            )
        else:
            requested = ["langchain"]
            fresh_environment = True
            print(
                "[init] auto: no framework SDK detected in this env. "
                f"Falling back to {requested[0]!r} demo dependencies."
            )

    if not args.no_install_deps:
        if fresh_environment:
            rc = _pip_install_framework_sdks(requested)
            if rc != 0:
                return rc

        if requested:
            rc = _pip_install_extras(requested)
            if rc != 0:
                return rc

        if not args.no_install_streamlit:
            rc = _pip_install_streamlit()
            if rc != 0:
                return rc

        from ._detect import detect_compatible
        compatible = detect_compatible(candidates=requested)
        if compatible != requested:
            missing = [framework for framework in requested if framework not in compatible]
            print(
                f"[init] these frameworks are still not ready: {missing}. "
                "Check the pip output above; no instrument.py was written."
            )
            return 1

    out = Path(args.out)
    try:
        content = _render_instrument_template(requested)
        out.write_text(content, encoding="utf-8", newline="\n")
    except (OSError, RuntimeError) as exc:
        print(f"[init] could not write template: {exc}", file=sys.stderr)
        return 1
    print(f"[init] wrote {out.resolve()}  ({out.stat().st_size} bytes)")
    print(f"[init] next: edit ROOT_SPAN + the entry-point import in {out.name}")
    print(f"[init] then: python {out.name}     # writes latest_traces.jsonl")
    if not args.no_install_streamlit:
        print("[init] view: python -m agent_monitor view")
    return 0


def _report_orphan_traces(trace_path: Path, root_name: str) -> None:
    """Warn when a run that got a root span still produced several trace trees.

    A trace is a tree, not a container: every span without a parent is the root
    of its own tree. One injected root span should adopt every top-level call
    the script makes, so extra roots mean the context never reached part of the
    run. Diagnostics only -- this never raises and never changes the exit code.
    """
    try:
        from ._verify_export import orphan_trace_report
        report = orphan_trace_report(trace_path)
    except Exception:  # pragma: no cover - a broken report must not break a run
        return
    roots = report.get("roots") or []
    if len(roots) <= 1:
        return
    orphans = [r for r in roots if r[1] != root_name] or roots[1:]
    shown = orphans[:10]
    print(
        f"[run] warning: this run produced {report['trace_count']} separate "
        f"traces ({report['span_count']} spans), not one.",
        file=sys.stderr,
    )
    print(f"[run]   expected root {root_name!r}, found {len(orphans)} "
          f"orphan root(s):", file=sys.stderr)
    for trace_id, name, kind, _start in shown:
        print(f"[run]     - {name!r} ({kind}) trace {trace_id[:8]}",
              file=sys.stderr)
    if len(orphans) > len(shown):
        print(f"[run]     ... and {len(orphans) - len(shown)} more",
              file=sys.stderr)
    print(
        "[run]   Orphan roots mean trace context was lost. Usual causes:\n"
        "[run]     * a thread or pool worker started before monitoring was active;\n"
        "[run]     * multiprocessing / Celery -- contextvars cannot cross processes;\n"
        "[run]     * --no-thread-context, or AGENT_MONITOR_THREAD_CONTEXT=0.\n"
        "[run]   Re-run without those to get a single tree.",
        file=sys.stderr,
    )


def _parse_instrumentors(raw):
    """``"langchain, openai"`` -> ``["langchain", "openai"]``.

    ``None`` (or an explicit ``all`` / ``auto`` / ``*``) means "no restriction":
    both mean the same thing downstream, where the allow-list is applied as a
    filter over whatever the run resolved on its own.
    """
    if not raw:
        return None
    names = [p.strip() for p in str(raw).replace(";", ",").split(",")]
    names = [n for n in names if n]
    if not names or any(n.lower() in {"*", "all", "auto", "any"} for n in names):
        return None
    return names


def cmd_run(args: argparse.Namespace) -> int:
    """Wrap a user script in monitor() and exec it."""
    script = Path(args.script)
    if not script.is_file():
        print(f"[run] script not found: {script}", file=sys.stderr)
        return 2

    # Defer heavy imports until we actually need them.
    from .monitor import DEFAULT_TRACE_FILE, monitor
    from opentelemetry.trace import Status, StatusCode

    sys.argv = [str(script), *args.script_args]
    # --service-name is documented as "else use script filename": passing None
    # produced an invalid OTel resource attribute (NoneType) plus a
    # "get_tracer called with missing module name" warning.
    service_name = args.service_name or script.stem
    kwargs = {"service_name": service_name, "auto_instrument": True,
              "exporter": args.exporter, "trace_file": args.trace_file,
              "thread_context": args.thread_context}
    allowlist = _parse_instrumentors(args.instrumentors)
    if allowlist:
        # An explicit list makes auto-detect moot: monitor() documents that
        # `instrumentors` wins over `auto_detect`, so running detection anyway
        # would only print advice about a decision already made.
        kwargs["instrumentors"] = allowlist
        print(f"[run] instrumentor allow-list: {', '.join(allowlist)}",
              file=sys.stderr)
    if "instrumentors" not in kwargs and args.auto_detect:
        # auto-detect is the default for `run`: it activates exactly the
        # instrumentors whose framework is importable, instead of every
        # installed instrumentor. If it finds nothing to go on (framework not
        # in our map, or none installed) fall back to the old behaviour rather
        # than silently instrumenting nothing at all.
        from ._detect import detect_compatible, detect_installed_instrumentors
        try:
            detected = detect_compatible()
        except Exception as exc:  # pragma: no cover
            detected = []
            print(f"[run] auto-detect failed ({exc}); instrumenting every "
                  "installed instrumentor instead", file=sys.stderr)
        if detected:
            kwargs["auto_detect"] = True
        elif detect_installed_instrumentors():
            # Instrumentors are installed but their framework SDK is not (or the
            # framework is not one we know how to detect). Fall back to the old
            # "try everything" behaviour -- each missing SDK reports its own
            # DependencyConflict -- and say so, since it is not what the default
            # advertises.
            print("[run] auto-detect found no framework+instrumentor pair; "
                  "instrumenting every installed instrumentor instead",
                  file=sys.stderr)

    # One AGENT root span for the whole run: without it every top-level call the
    # script makes becomes its own trace, and the viewer lists one row per call
    # instead of one row per run. Framework root runs adopt it as their parent
    # (OpenInference passes context=None for a run without a parent_run_id, so
    # the SDK falls back to the ambient span).
    root_name = args.root_span or script.stem
    with monitor(**kwargs) as tracer:
        if args.root_span_enabled:
            # Ordinary exceptions are NOT caught: start_as_current_span records
            # them and sets ERROR status, then the traceback propagates exactly
            # as before. SystemExit is the one exception -- see below.
            with tracer.start_as_current_span(
                root_name,
                attributes={"openinference.span.kind": "AGENT"},
            ) as root:
                try:
                    runpy.run_path(str(script), run_name="__main__")
                except SystemExit as exc:
                    # ``raise SystemExit(main())`` is how a normal CLI entry
                    # point ends, and OpenTelemetry deliberately records only
                    # Exception -- never BaseException -- so a script that exits
                    # this way used to leave the root span UNSET, i.e. every
                    # viewer showed the run as "unfinished" and the line below
                    # was simply unreachable. Exit 0 (or None) is success and
                    # falls through to the shared set_status; any other code is
                    # a real failure, so record it and keep propagating it.
                    if exc.code not in (None, 0):
                        root.set_status(
                            Status(StatusCode.ERROR, f"SystemExit: {exc.code}")
                        )
                        raise
                root.set_status(Status(StatusCode.OK))
        else:
            # --no-root-span: the script's own framework (FastAPI / Celery /
            # LangGraph ...) already emits a root, and a second one would just
            # add an empty wrapper row in the viewer.
            runpy.run_path(str(script), run_name="__main__")

    # monitor() has flushed and shut the exporter down by now, so the file is
    # complete. Only meaningful when WE synthesised the root: with
    # --no-root-span (or a non-file exporter) several trees are expected.
    if args.root_span_enabled and args.exporter == "jsonl":
        _report_orphan_traces(Path(args.trace_file or DEFAULT_TRACE_FILE),
                              root_name)
    return 0


def cmd_detect(args: argparse.Namespace) -> int:
    from ._detect import detect_all
    info = detect_all()
    if args.json:
        print(json.dumps(info, ensure_ascii=False, indent=2))
    else:
        for k, v in info.items():
            print(f"  {k:>24}: {v}")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    from ._verify_export import verify_export
    require = tuple(args.require_kind) if args.require_kind else ()
    ok = verify_export(
        expected_path=args.trace_file,
        min_spans=args.min_spans,
        min_traces=args.min_traces,
        max_traces=args.max_traces,
        require_kind_in=require,
        quiet=args.quiet,
    )
    return 0 if ok else 1


def cmd_view(args: argparse.Namespace) -> int:
    """Launch the Streamlit viewer pointing at the right trace file.

    Resolves the trace file relative to CWD (default ./latest_traces.jsonl)
    and the viewer path relative to *this* package so the user does not have
    to know the absolute path of either. Pass ``--no-launch`` to print the
    resolved command without launching streamlit (useful in tests / docs).
    """
    import subprocess

    trace_path = (
        Path(args.trace_file).resolve()
        if args.trace_file
        else (Path.cwd() / "latest_traces.jsonl").resolve()
    )
    default_viewer = Path(__file__).resolve().parent.parent / "viewer.py"
    viewer_path = (
        Path(args.viewer).resolve() if args.viewer else default_viewer
    )

    if not viewer_path.is_file():
        print(f"[view] viewer not found: {viewer_path}")
        print("       pass --viewer <path-to-viewer.py>")
        return 2

    cmd = ["streamlit", "run", str(viewer_path)]
    print(f"[view] TRACE_FILE = {trace_path}")
    print(f"[view] viewer     = {viewer_path}")
    print(f"[view] running:   {' '.join(cmd)}")
    if args.no_launch:
        return 0

    env = {**os.environ, "TRACE_FILE": str(trace_path)}
    try:
        return subprocess.run(cmd, env=env, check=False).returncode
    except FileNotFoundError:
        print(
            "[view] could not find `streamlit` on PATH.\n"
            "       install with: pip install streamlit streamlit-autorefresh"
        )
        return 127


# ---------- argparse wiring -------------------------------------------------
def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="agent_monitor",
                                description="Local agent trace toolkit.")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser(
        "init",
        help="detect every installed framework, install combined OpenInference "
             "extras and viewer deps, then write a generic instrument.py "
             "(use --no-install-deps / --no-install-streamlit to skip parts).",
    )
    p_init.add_argument(
        "--framework", default="auto",
        help="comma-separated framework keys (for example langchain,openai), "
             "'pure' for an empty instrumentor list, or 'auto' to detect all "
             "installed frameworks (default 'auto').",
    )
    p_init.add_argument(
        "--out", default="instrument.py",
        help="output filename (default instrument.py)",
    )
    p_init.add_argument(
        "--no-install-deps", action="store_true",
        help="skip pip install (framework SDK + OI instrumentor). "
             "Only writes instrument.py (for CI or air-gapped use).",
    )
    p_init.add_argument(
        "--no-install-streamlit", action="store_true",
        help="skip the `streamlit + streamlit-autorefresh` install; "
             "framework deps are still installed.",
    )
    p_init.set_defaults(func=cmd_init)

    p_run = sub.add_parser("run", help="wrap a script in monitor() and execute")
    # Every flag is declared BEFORE `script`: `script_args` uses
    # nargs=REMAINDER, so anything written after the script path is forwarded to
    # the script verbatim instead of being parsed here.
    p_run.add_argument("--root-span", default=None,
                       help="name of the single AGENT root span wrapped around "
                            "the whole run (default: the script filename stem)")
    p_run.add_argument("--no-root-span", dest="root_span_enabled",
                       action="store_false",
                       help="do not wrap the run in a root span; use this when "
                            "the script's framework already emits its own root "
                            "(FastAPI / Celery / LangGraph), otherwise you get "
                            "a double root")
    p_run.set_defaults(root_span_enabled=True)
    p_run.add_argument("--no-thread-context", dest="thread_context",
                       action="store_false",
                       help="do NOT propagate trace context into threads. It is "
                            "propagated by default (ThreadPoolExecutor.submit / "
                            "threading.Thread), which is what keeps pool tasks "
                            "inside this run's trace instead of one orphan trace "
                            "per task; turn it off only if the patch conflicts "
                            "with your own")
    p_run.set_defaults(thread_context=True)
    p_run.add_argument("--auto-detect", action=argparse.BooleanOptionalAction,
                       default=True,
                       help="activate exactly the instrumentors whose framework "
                            "is importable (default: on; --no-auto-detect "
                            "instruments every installed instrumentor instead)")
    p_run.add_argument("--exporter", default="jsonl",
                       choices=["jsonl", "console"],
                       help="exporter alias (default jsonl)")
    p_run.add_argument("--instrumentors", default=None,
                       help="comma-separated allow-list of instrumentor "
                            "framework keys to activate, e.g. 'langchain' or "
                            "'openai,anthropic' ('all'/'auto' = no restriction). "
                            "Use 'langchain' on a langchain-openai app to drop "
                            "the duplicate ChatCompletion span the openai "
                            "instrumentor adds to every LLM call")
    p_run.add_argument("--trace-file", default=None,
                       help="output path when exporter=jsonl")
    p_run.add_argument("--service-name", default=None,
                       help="override service.name (else use script filename)")
    p_run.add_argument("script", help="user script to run")
    p_run.add_argument("script_args", nargs=argparse.REMAINDER,
                       help="arguments forwarded to the user script")
    p_run.set_defaults(func=cmd_run)

    p_det = sub.add_parser("detect",
                           help="list frameworks + instrumentors visible to this env")
    p_det.add_argument("--json", action="store_true",
                       help="emit JSON instead of human-readable text")
    p_det.set_defaults(func=cmd_detect)

    p_ver = sub.add_parser("verify",
                           help="validate that a JSONL trace export is well-formed")
    p_ver.add_argument("--trace-file", default="latest_traces.jsonl")
    p_ver.add_argument("--min-spans", type=int, default=1)
    p_ver.add_argument("--min-traces", type=int, default=1)
    p_ver.add_argument("--max-traces", type=int, default=None,
                       help="fail when the export holds more than this many "
                            "distinct traces; use --max-traces 1 in CI to assert "
                            "that one agent run is one trace tree")
    p_ver.add_argument("--require-kind", action="append", default=[],
                       help="repeatable; require at least one span with this kind")
    p_ver.add_argument("--quiet", action="store_true")
    p_ver.set_defaults(func=cmd_verify)

    p_view = sub.add_parser(
        "view",
        help="launch the Streamlit viewer against ./latest_traces.jsonl",
    )
    p_view.add_argument(
        "--viewer", default=None,
        help="absolute path to viewer.py "
             "(default: <this-package>/../viewer.py, ie the repo root)",
    )
    p_view.add_argument(
        "--trace-file", default=None,
        help="trace JSONL to watch (default: ./latest_traces.jsonl, ie CWD)",
    )
    p_view.add_argument(
        "--no-launch", action="store_true",
        help="print the resolved command but do not actually launch streamlit",
    )
    p_view.set_defaults(func=cmd_view)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())


