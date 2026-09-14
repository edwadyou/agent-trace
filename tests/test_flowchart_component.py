"""Static contracts for the browser half of the Mermaid component."""
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
COMPONENT = ROOT / "flowchart_component" / "index.html"


def _source() -> str:
    return COMPONENT.read_text(encoding="utf-8")


def test_component_has_complete_viewport_toolbar():
    src = _source()
    for action in ("zoom-out", "zoom-in", "fit", "actual"):
        assert f'data-action="{action}"' in src
    assert 'id="zoom-readout"' in src
    assert 'id="diagram-viewport"' in src
    assert 'id="diagram-canvas"' in src


def test_component_uses_a_fixed_frame_not_svg_scroll_height():
    src = _source()
    assert "frame.getBoundingClientRect()" in src
    assert 'frame.closest(".st-key-activity_panel")' in src
    assert 'setHeight(clamp(Math.round(height), 360, 900))' in src
    assert "document.documentElement.scrollHeight" not in src
    assert "container.scrollHeight" not in src


def test_component_bounds_zoom_and_supports_pan_and_modified_wheel():
    src = _source()
    assert "var MIN_SCALE = 0.15" in src
    assert "var MAX_SCALE = 3.0" in src
    assert 'addEventListener("pointerdown"' in src
    assert 'addEventListener("pointermove"' in src
    assert 'addEventListener("wheel"' in src
    assert "event.ctrlKey || event.metaKey" in src


def test_pointer_capture_starts_only_after_the_drag_threshold():
    src = _source()
    pointerdown = src.split('viewport.addEventListener("pointerdown"', 1)[1]
    pointerdown = pointerdown.split('viewport.addEventListener("pointermove"', 1)[0]
    assert "setPointerCapture" not in pointerdown
    assert src.index("DRAG_THRESHOLD") < src.index("setPointerCapture")
    assert 'window.addEventListener("pointerup", endDrag)' in src


def test_activity_names_wrap_without_visual_truncation():
    src = _source()
    rule = src.split(".activity-name {", 1)[1].split("}", 1)[0]
    assert "white-space: normal" in rule
    assert "overflow-wrap: anywhere" in rule
    assert "overflow: visible" in rule
    assert "text-overflow" not in rule


def test_component_preserves_manual_view_across_live_source_updates():
    src = _source()
    assert "graphCenterSnapshot" in src
    assert "restoreSnapshot(snapshot)" in src
    assert 'src === currentSrc && container.querySelector("svg")' in src
    assert "if(fitMode)" in src


def test_component_keeps_click_back_and_focus_without_redraw():
    src = _source()
    assert 'setValue({span_id:sid, trace_id:traceId || "", ts:Date.now()})' in src
    assert "applyFocus(focus)" in src
    assert "revealFocusIfNeeded(focus)" in src
    assert 'send("streamlit:componentReady", {apiVersion:1})' in src


def test_page_uses_an_explicit_high_contrast_dark_theme_without_panel_cards():
    theme = (ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8")
    assert 'base = "dark"' in theme
    assert 'backgroundColor = "#0B1120"' in theme
    assert 'textColor = "#F1F5F9"' in theme

    app = (ROOT / "viewer_app" / "__init__.py").read_text(encoding="utf-8")
    assert 'key="activity_panel", border=False' in app
    assert 'key="detail_panel", border=False' in app

    css = (ROOT / "viewer_app" / "config.py").read_text(encoding="utf-8")
    panel_rule = css.split(".st-key-activity_panel,", 1)[1].split("}", 1)[0]
    assert "background: transparent" in panel_rule
    assert "border: 0" in panel_rule


def test_activity_click_forces_one_consistent_python_rerun():
    src = (ROOT / "viewer_app" / "render_activity.py").read_text(encoding="utf-8")
    click_tail = src.split("st.session_state.selected_span = sid", 1)[1]
    click_tail = click_tail.split("def _render_activity_center", 1)[0]
    assert "st.query_params['focus'] = sid" in click_tail
    assert "st.rerun()" in click_tail
