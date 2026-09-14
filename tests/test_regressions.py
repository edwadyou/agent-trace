"""Regression tests covering the v1.1.1 fixes that aren't exercised by unit tests
of the helpers themselves: text/source-level checks for the viewer edits and
pyproject extras.

NOTE: the viewer used to be a single ``viewer.py``; it now lives in the
``viewer_app`` package and ``viewer.py`` is only a launcher. These tests were
repointed at the module that actually owns each construct.
"""
from __future__ import annotations
import inspect
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
VIEWER_PY = ROOT / "viewer.py"
VIEWER_APP = ROOT / "viewer_app"
PYPROJECT = ROOT / "pyproject.toml"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _fn_src(module, name: str) -> str:
    """Source of a single function, independent of file formatting."""
    return inspect.getsource(getattr(module, name))


def test_viewer_launcher_still_imports_run():
    src = _read(VIEWER_PY)
    assert "from viewer_app import run" in src
    assert src.rstrip().endswith("run()")


def test_viewer_truncate_block_simple_replace():
    from viewer_app import structured

    src = _fn_src(structured, "_render_input_fallback")
    assert "val = attrs.get(key)" in src
    assert "val = canon(attrs, key)" in src


def test_viewer_sp_id_slicing_is_post_escape():
    from viewer_app import render_detail

    src = _fn_src(render_detail, "_render_detail_panel")
    assert re.search(
        r"span_id=\{_esc\(\(sel_span\.get\(\"span_id\",\"\"\) or \"\"\)\[:16\]\)\}",
        src,
    ), "span_id slicing should happen before _esc"
    assert '_esc(sel_span.get("span_id",""))[:16]' not in src


def test_viewer_css_secondary_button_color_is_light():
    from viewer_app.config import _CSS

    m = re.search(
        r"button\[data-testid=\"stBaseButton-secondary\"\]\s*\{[^}]*?color:\s*([^;]+);",
        _CSS,
    )
    assert m is not None, "secondary button CSS block must define color"
    color = m.group(1).strip().lower()
    # The card text must follow the theme instead of a hard-coded dark gray,
    # which was nearly invisible on a dark page background.
    assert "#111827" not in color, f"secondary button color regressed to {color}"
    assert color.startswith("var(--text-color"), (
        f"secondary button color must follow the theme; got {color}"
    )


def test_viewer_kpi_aggregates_agent_spans():
    """TraceKPI must stay a real dataclass.

    When the `@dataclass` decorator was dropped during the viewer_app split,
    `agent_names` fell back to the raw `dataclasses.Field` object and
    `_aggregate_kpi` raised ``TypeError: argument of type 'Field' is not
    iterable`` for ANY trace containing an AGENT span.
    """
    from viewer_app.data import TraceKPI, _aggregate_kpi

    assert TraceKPI().agent_names == []

    spans = [
        {
            "trace_id": "t" * 32, "span_id": "a" * 16, "parent_span_id": None,
            "name": "AgentExecutor", "start_time": 1, "end_time": 2,
            "status": "OK", "kind": "AGENT",
            "attributes": {"openinference.span.kind": "AGENT"},
        },
        {
            "trace_id": "t" * 32, "span_id": "b" * 16, "parent_span_id": "a" * 16,
            "name": "ChatOpenAI", "start_time": 1, "end_time": 2,
            "status": "OK", "kind": "LLM",
            "attributes": {"openinference.span.kind": "LLM"},
        },
    ]
    kpi = _aggregate_kpi(spans)
    assert kpi.n_spans == 2
    assert kpi.n_agent == 1
    assert kpi.agent_names == ["AgentExecutor"]


def test_pyproject_has_viewer_and_test_extras():
    src = PYPROJECT.read_text(encoding="utf-8")
    # Both extras must declare their dep list inside the [project.optional-dependencies] table.
    assert "viewer = [" in src
    assert "test = [" in src
    assert "streamlit" in src.lower()
    assert "pytest" in src.lower()


def test_naming_no_bak_file():
    bak = ROOT / "viewer" / "naming" / "langchain.py.bak"
    assert not bak.exists(), f"stale file: {bak}"
    src = (ROOT / "viewer" / "naming" / "langchain.py").read_text(encoding="utf-8")
    # The dedup target: no Chat(.*|Fireworks|.*Fireworks|.*) alternation containing duplicates.
    chat_re = re.compile(r"^Chat\([^)]+\)\b.*", re.M)
    for line in src.splitlines():
        if chat_re.match(line):
            # Extract everything between Chat( and \b
            inner = re.search(r"^Chat\(([^)]+)\)", line).group(1)
            alts = [a.strip() for a in inner.split("|")]
            assert len(alts) == len(set(alts)), f"duplicate alts in: {inner}"


def test_jsonl_exporter_truncate_default_is_false():
    from agent_monitor.jsonl_exporter import JsonlFileExporter
    sig = inspect.signature(JsonlFileExporter.__init__)
    assert sig.parameters["truncate_on_init"].default is False


def test_monitor_uses_force_flush_with_swallow():
    src = (ROOT / "agent_monitor" / "monitor.py").read_text(encoding="utf-8")
    assert "processor.force_flush()" in src
    idx = src.index("processor.force_flush()")
    tail = src[idx:idx + 200]
    assert "except" in tail


def test_load_dotenv_preserves_zero_value():
    """_load_dotenv uses os.environ.get(key) without .strip() so '0' is kept."""
    src = (ROOT / "agent_monitor" / "monitor.py").read_text(encoding="utf-8")
    # The new predicate strips the .strip() call.
    assert "not os.environ.get(key):" in src, (
        "_load_dotenv predicate must read os.environ.get(key) without .strip()"
    )
    # And the literal old '.strip()' must not survive.
    assert 'os.environ.get(key, "").strip()' not in src


def test_main_module_imports_at_top():
    src = (ROOT / "agent_monitor" / "__main__.py").read_text(encoding="utf-8")
    lines = src.splitlines()
    last_import_line = -1
    for i, line in enumerate(lines):
        if line.startswith("import ") or line.startswith("from "):
            last_import_line = i
    first_def_line = -1
    for i, line in enumerate(lines):
        if line.startswith("def ") or line.startswith("class "):
            first_def_line = i
            break
    assert last_import_line < first_def_line, (
        f"imports must precede defs; got import@{last_import_line} vs def@{first_def_line}"
    )


def test_cli_run_defaults_service_name_to_script_stem():
    """`run --service-name` is documented to fall back to the script filename.

    Passing None instead produced an invalid OTel resource attribute
    (NoneType for 'service.name') and a "get_tracer called with missing
    module name" warning on every CLI run without --service-name.
    """
    from agent_monitor.__main__ import _build_parser

    args = _build_parser().parse_args(["run", "my_agent.py"])
    assert args.service_name is None  # the CLI default stays None ...
    src = (ROOT / "agent_monitor" / "__main__.py").read_text(encoding="utf-8")
    # ... and cmd_run is responsible for the documented fallback.
    assert "service_name = args.service_name or script.stem" in src


def test_estimate_cost_signature_is_single_arg():
    from viewer_app import format as fmt

    assert re.search(
        r"^def _estimate_cost\(span: dict\) -> float \| None:", _fn_src(fmt, "_estimate_cost"), re.M
    )
    assert 'attr_key + ".tokens.input"' not in _read(VIEWER_APP / "format.py")


def test_normalize_no_duplicate_reconstruct_indexed_list():
    src = (ROOT / "viewer" / "normalize.py").read_text(encoding="utf-8")
    n = len(re.findall(r"^def _reconstruct_indexed_list\(attrs, prefix\):", src, re.M))
    assert n == 1, f"_reconstruct_indexed_list defined {n} times; expected 1"


def test_normalize_canon_has_no_duplicate_block():
    src = (ROOT / "viewer" / "normalize.py").read_text(encoding="utf-8")
    n = src.count("# 3) Flat-indexed reconstruction")
    assert n == 1, f"duplicated comment+block still present; found {n}"


def test_viewer_no_autokind_variable():
    for path in VIEWER_APP.rglob("*.py"):
        assert "_autokind" not in _read(path), f"_autokind still present in {path}"


def test_viewer_no_redundant_components_import():
    src = _read(VIEWER_APP / "config.py")
    n = src.count("import streamlit.components.v1 as components")
    assert n == 1, f"expected exactly 1 import; found {n}"


def test_viewer_component_declared_exactly_once():
    """The split accidentally duplicated the whole _COMPONENT_DIR /
    declare_component block, registering the same component twice."""
    src = _read(VIEWER_APP / "config.py")
    assert src.count("_COMPONENT_DIR = Path(") == 1
    assert src.count("components.declare_component(") == 1


def test_viewer_all_is_strings():
    """__all__ must contain names, not the objects themselves (a split-time
    typo left render_tracelist.__all__ as a list of function objects, which
    breaks ``from module import *``)."""
    import importlib

    for mod_name in (
        "viewer_app.data", "viewer_app.format", "viewer_app.msg",
        "viewer_app.structured", "viewer_app.render_detail",
        "viewer_app.render_flowchart", "viewer_app.render_tracelist",
        "viewer_app.render_activity",
    ):
        mod = importlib.import_module(mod_name)
        names = getattr(mod, "__all__", [])
        assert names, f"{mod_name} has an empty __all__"
        for entry in names:
            assert isinstance(entry, str), (
                f"{mod_name}.__all__ contains {type(entry).__name__} ({entry!r}); "
                "expected str"
            )


def test_viewer_duplicate_meta_comment_removed():
    from viewer_app.config import _CSS

    # The duplicated CSS section header was two consecutive identical comments.
    assert "/* ----- right metadata panel ----- */\n/* ----- right metadata panel ----- */" not in _CSS
