"""Regression tests covering the v1.1.1 fixes that aren't exercised by unit tests
of the helpers themselves: text/source-level checks for the viewer.py edits and
pyproject extras."""
from __future__ import annotations
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
VIEWER_PY = ROOT / "viewer.py"
PYPROJECT = ROOT / "pyproject.toml"


def test_viewer_truncate_block_simple_replace():
    src = VIEWER_PY.read_text(encoding="utf-8")
    assert "val = attrs.get(key)" in src
    assert "val = canon(attrs, key)" in src


def test_viewer_sp_id_slicing_is_post_escape():
    src = VIEWER_PY.read_text(encoding="utf-8")
    assert re.search(
        r"span_id=\{_esc\(\(sel_span\.get\(\"span_id\",\"\"\) or \"\"\)\[:16\]\)\}",
        src,
    ), "span_id slicing should happen before _esc"
    assert "_esc(sel_span.get(\"span_id\",\"\"))[:16]" not in src


def test_viewer_css_secondary_button_color_is_light():
    src = VIEWER_PY.read_text(encoding="utf-8")
    m = re.search(
        r"button\[data-testid=\"stBaseButton-secondary\"\]\s*\{[^}]*color:\s*(#[0-9a-fA-F]+)",
        src,
    )
    assert m is not None, "secondary button CSS block must define color"
    color = m.group(1).lower()
    assert color != "#111827", f"secondary button color regressed to {color}"


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
    import inspect
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


def test_estimate_cost_signature_is_single_arg():
    src = VIEWER_PY.read_text(encoding="utf-8")
    assert re.search(r"^def _estimate_cost\(span: dict\) -> float \| None:", src, re.M)
    assert 'attr_key + ".tokens.input"' not in src


def test_normalize_no_duplicate_reconstruct_indexed_list():
    src = (ROOT / "viewer" / "normalize.py").read_text(encoding="utf-8")
    n = len(re.findall(r"^def _reconstruct_indexed_list\(attrs, prefix\):", src, re.M))
    assert n == 1, f"_reconstruct_indexed_list defined {n} times; expected 1"


def test_normalize_canon_has_no_duplicate_block():
    src = (ROOT / "viewer" / "normalize.py").read_text(encoding="utf-8")
    n = src.count("# 3) Flat-indexed reconstruction")
    assert n == 1, f"duplicated comment+block still present; found {n}"


def test_viewer_no_autokind_variable():
    src = VIEWER_PY.read_text(encoding="utf-8")
    assert "_autokind" not in src


def test_viewer_no_redundant_components_import():
    src = VIEWER_PY.read_text(encoding="utf-8")
    n = src.count("import streamlit.components.v1 as components")
    assert n == 1, f"expected exactly 1 import; found {n}"


def test_viewer_duplicate_meta_comment_removed():
    src = VIEWER_PY.read_text(encoding="utf-8")
    # The duplicated CSS section header was two consecutive identical comments.
    assert "/* ----- right metadata panel ----- */\n/* ----- right metadata panel ----- */" not in src
