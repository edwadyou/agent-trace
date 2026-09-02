r"""agent_monitor CLI entry point.

Usage::

    python -m agent_monitor init  [--framework auto|<name>] [--out PATH]
                                  [--no-install-deps] [--no-install-streamlit]
    python -m agent_monitor run   SCRIPT.py [--exporter jsonl|console]
                                       [--service-name NAME] [--auto-detect]
                                       [--trace-file PATH]
    python -m agent_monitor detect [--json]
    python -m agent_monitor verify [--trace-file PATH] [--min-spans N]
                                   [--require-kind LLM|CHAIN|...]
    python -m agent_monitor view   [--viewer PATH] [--trace-file PATH]
                                   [--no-launch]

Designed so a new agent user can type four commands and be done:

    cd my-new-agent
    python -m agent_monitor init --framework auto
                                   # auto-installs FRAMEWORK SDK + openinference
                                   # instrumentor + streamlit + streamlit-autorefresh,
                                   # then writes instrument.py
    python instrument.py            # writes latest_traces.jsonl
    streamlit run D:/my-projects/agent-monitor/viewer.py
                                   # browser live view

What `init --framework auto` installs in one shot:

  1. framework SDK (e.g. langchain / openai / crewai / autogen / ...)
       - picked by sniffing the current env, falling back to langchain
  2. matching OpenInference instrumentor via `agent-monitor[<framework>]`
  3. streamlit + streamlit-autorefresh (for the viewer)

Use `--no-install-deps` to skip BOTH the framework SDK and the OI
instrumentor (e.g. CI / air-gapped). Use `--no-install-streamlit` to keep
the framework install but skip the viewer deps.

`view` resolves the trace file relative to CWD (./latest_traces.jsonl by
default) and the viewer path relative to this package, so it works from any
working directory. Pass --no-launch to print the resolved command without
executing streamlit.

NOTE: `agent_monitor` itself must already be importable in the current
Python (e.g. `pip install -e D:\my-projects\agent-monitor`). `init`
will tell you when it is not.
"""
from __future__ import annotations
import argparse
import json
import os
import runpy
import sys
from pathlib import Path


_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "examples" / "_templates"

# ---------- helpers (used by init --framework auto) -----------------------
def _pip_install(pkgs: list[str], *, label: str) -> int:
    """Run ``pip install <pkgs>`` and stream its output. Returns rc."""
    import subprocess
    if not pkgs:
        return 0
    print(f"[init] {label}: pip install {' '.join(pkgs)}")
    try:
        return subprocess.run(
            [sys.executable, "-m", "pip", "install", *pkgs],
            check=False,
        ).returncode
    except FileNotFoundError:
        print("[init] could not invoke pip. Run manually:")
        print(f"        {sys.executable} -m pip install {' '.join(pkgs)}")
        return 1


def _pip_install_framework(framework: str) -> int:
    """Install the framework SDK AND the matching OpenInference instrumentor.

    Concrete frameworks (e.g. langchain, openai, crewai) get one combined
    pip call:

        pip install <SDK pkgs> agent-monitor[<framework>]

    Composite / unknown template names (e.g. ``langchain_openai``) print a
    hint and return 0 - the user picks which component to install.
    """
    if framework == "auto":
        return 0  # resolved upstream by cmd_init; never called with auto
    from ._detect import framework_sdk_packages, list_supported_frameworks
    if framework not in list_supported_frameworks():
        print(f"[init] {framework!r} is a composite template (no single pip extra).")
        print("        ensure its component frameworks are installed, e.g.:")
        print("        pip install agent-monitor[" + framework.replace("_", "-").split("-")[0] + "]")
        return 0
    extras = framework.replace("_", "-")
    oi_spec = f"agent-monitor[{extras}]"
    pkgs = list(framework_sdk_packages(framework))
    pkgs.append(oi_spec)
    return _pip_install(pkgs, label=f"installing {framework} deps (SDK + OpenInference instrumentor)")


def _pip_install_streamlit() -> int:
    """Install streamlit + streamlit-autorefresh for the viewer."""
    return _pip_install(
        ["streamlit", "streamlit-autorefresh"],
        label="installing viewer deps",
    )


def _agent_monitor_importable() -> bool:
    """True if the `agent_monitor` package is importable in this env."""
    try:
        import agent_monitor  # noqa: F401
        return True
    except ImportError:
        return False


# ---------- subcommands ------------------------------------------------------


def cmd_init(args: argparse.Namespace) -> int:
    """One-stop init: pick a framework, install EVERYTHING needed, write
    ``instrument.py`` into CWD.

    Default behaviour (no flags):

        1. autodetect framework (or use --framework <name>)
        2. pip install framework SDK packages
                       + agent-monitor[<framework>] (OpenInference instrumentor)
                       + streamlit + streamlit-autorefresh
        3. write instrument.py from the matching template

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

    framework = args.framework
    if framework == "auto":
        # Try 3 levels, in order:
        #   (1) fully ready     -> compatible = SDK + OI instrumentor
        #   (2) SDK present     -> installed  = SDK only, OI missing
        #   (3) fresh env       -> neither; default to langchain
        from ._detect import detect_compatible, detect_installed_frameworks
        compat    = detect_compatible()
        installed = detect_installed_frameworks()
        if compat:
            framework = compat[0]
            print(f"[init] auto: OI-ready frameworks = {compat} -> using {framework!r}")
        elif installed:
            framework = installed[0]
            print(
                f"[init] auto: SDK detected for {installed} but OI instrumentor missing;"
                f" will install extras for {framework!r}"
            )
        else:
            framework = "langchain"
            print(
                f"[init] auto: no framework SDK detected in this env."
                f" Falling back to {framework!r} (most common)."
            )

    # Install framework SDK + OpenInference instrumentor (unless opted out)
    if not args.no_install_deps:
        rc = _pip_install_framework(framework)
        if rc != 0:
            return rc
        # Install viewer deps (streamlit + streamlit-autorefresh)
        if not args.no_install_streamlit:
            rc = _pip_install_streamlit()
            if rc != 0:
                return rc

    template = _resolve_template(framework)
    if template is None:
        print(f"[init] no template for framework {framework!r}")
        return 2
    out = Path(args.out)
    out.write_text(template.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"[init] wrote {out.resolve()}  ({out.stat().st_size} bytes)")
    print(f"[init] next: python {out.name}     # writes latest_traces.jsonl")
    if not args.no_install_streamlit:
        print(f"[init] then: streamlit run D:/my-projects/agent-monitor/viewer.py")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    """Wrap a user script in monitor() and exec it."""
    script = Path(args.script)
    if not script.is_file():
        print(f"[run] script not found: {script}", file=sys.stderr)
        return 2

    # Defer heavy imports until we actually need them.
    from .monitor import monitor

    sys.argv = [str(script), *args.script_args]
    kwargs = {"service_name": args.service_name, "auto_instrument": True,
              "exporter": args.exporter, "trace_file": args.trace_file}
    if args.auto_detect:
        kwargs["auto_detect"] = True
    with monitor(**kwargs):
        runpy.run_path(str(script), run_name="__main__")
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
        help="autodetect framework, install FRAMEWORK SDK + OpenInference "
             "instrumentor + streamlit, and write instrument.py in cwd "
             "(use --no-install-deps / --no-install-streamlit to skip parts).",
    )
    p_init.add_argument(
        "--framework", default="auto",
        help="framework key (langchain, openai, langchain_openai, "
             "llama-index, crewai, dspy, autogen, haystack, smolagents, "
             "anthropic, google-genai, groq, bedrock, litellm, pure, "
             "or 'auto' to detect; default 'auto').",
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
    p_run.add_argument("script", help="user script to run")
    p_run.add_argument("--exporter", default="jsonl",
                       choices=["jsonl", "console"],
                       help="exporter alias (default jsonl)")
    p_run.add_argument("--trace-file", default=None,
                       help="output path when exporter=jsonl")
    p_run.add_argument("--service-name", default=None,
                       help="override service.name (else use script filename)")
    p_run.add_argument("--auto-detect", action="store_true",
                       help="let agent_monitor sniff instrumentors at runtime")
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


def _resolve_template(framework: str) -> Path | None:
    """Find the right instrument_<X>.py template.

    Special-cased names map to a non-default template:
        - 'langchain_openai' -> instrument_langchain_openai.py
    """
    candidates = []
    if framework in {"langchain_openai", "langchain-openai"}:
        candidates.append("instrument_langchain_openai.py")
    candidates.append(f"instrument_{framework.replace('-', '_')}.py")
    candidates.append(f"instrument_{framework.replace('_', '-')}.py")
    for name in candidates:
        path = _TEMPLATES_DIR / name
        if path.is_file():
            return path
    return None


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())


