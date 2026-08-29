# -*- coding: utf-8 -*-
"""Replace _render_flowchart_mode with 3-column flowchart explorer."""
import sys, re
sys.stdout.reconfigure(encoding="utf-8")

p = r"D:\my-projects\agent-monitor\viewer.py"
content = open(p, encoding="utf-8").read()

# Find function bounds
start_anchor = "def _render_flowchart_mode(sel_spans, kpi, all_by_id):"
end_anchor = "# LEFT tree renderer"
start_idx = content.find(start_anchor)
end_idx = content.find(end_anchor, start_idx)
assert start_idx > 0 and end_idx > start_idx

# Build the new function body.  Use literal \\uXXXX for Chinese so the file
# remains ASCII-source (no encoding fragility).  \n inside strings stays as
# \n in source so Python parses it as a newline escape at runtime.

NEW_FUNC = '''def _render_flowchart_mode(sel_spans, kpi, all_by_id):
    """3-column flowchart explorer: traces | mermaid TD | span detail.

    Layout:
        col_left   = trace cards list (click to switch trace)
        col_center = current trace as Mermaid `flowchart TD`
        col_right  = selected span detail (Run / Feedback / Metadata)

    Click a flowchart node -> URL becomes `?trace=<tid>&focus=<sid>` -> page
    reloads -> right column shows that span.  URL is bookmarkable.
    """
    # 1) Sync selected_trace from URL (so reloads are bookmarkable)
    _url_trace = st.query_params.get("trace")
    if _url_trace and _url_trace in traces:
        if st.session_state.selected_trace != _url_trace:
            st.session_state.selected_trace = _url_trace
            sel_spans = traces[_url_trace]
            all_by_id = {s["span_id"]: s for s in sel_spans}
            kpi = _aggregate_kpi(sel_spans)
    focus = st.query_params.get("focus")

    col_left, col_center, col_right = st.columns([1.3, 2.2, 1.5])

    with col_left:
        _render_trace_cards_list()
    with col_center:
        _render_flowchart_center(sel_spans)
    with col_right:
        _render_detail_column(sel_spans, all_by_id, focus)


def _render_trace_cards_list():
    """Left column: list each trace as a card.  Click -> switch trace."""
    st.markdown("#### \\U0001F4CB Traces")
    if not traces:
        st.caption("\\u8fd8\\u6ca1\\u6709 trace\\u3002\\u8bf7\\u8fd0\\u884c agent \\u540e\\u5237\\u65b0\\u3002")
        return
    cur_tid = st.session_state.selected_trace
    for tid, spans in traces.items():
        spans_list = spans or []
        kk = _aggregate_kpi(spans_list)
        # Use the existing dropdown formatter for visual consistency
        row = _fmt_trace_option(tid)
        is_cur = (tid == cur_tid)
        btn_type = "primary" if is_cur else "secondary"
        # Card body: top = button (the row), bottom = first-level children preview
        st.markdown(
            "<div class=\"trace-card" + (" trace-card-active" if is_cur else "") + "\">",
            unsafe_allow_html=True,
        )
        st.button(
            row,
            key=f"trace_card_{tid}",
            type=btn_type,
            use_container_width=True,
        )
        # First-level children preview
        if spans_list:
            first_root = next(
                (s for s in spans_list if not s.get("parent_span_id")),
                spans_list[0],
            )
            kids = [
                s for s in spans_list
                if s.get("parent_span_id") == first_root.get("span_id")
            ]
            kids = sorted(kids, key=lambda s: int(s.get("start_time", 0)))
            names = [_span_display_name(k) for k in kids[:3]]
            if names:
                more = "" if len(kids) <= 3 else f" \\u2026 +{len(kids) - 3}"
                preview = " \\u00b7 ".join(names) + more
                st.markdown(
                    f"<div class=\"trace-card-children\">\\u21b3 {preview}</div>",
                    unsafe_allow_html=True,
                )
        st.markdown("</div>", unsafe_allow_html=True)


def _render_flowchart_center(sel_spans):
    """Center column: current trace's span flowchart (TD)."""
    st.markdown("#### \\U0001F500 Agent \\u6d41\\u7a0b\\u56fe")
    st.caption(
        f"\\u5171 {len(sel_spans)} \\u4e2a span\\u3002"
        "\\u70b9\\u51fb\\u8282\\u70b9\\u53ef\\u67e5\\u770b\\u8be6\\u60c5\\uff1b"
        "\\u4e0a\\u65b9\\u4e3a\\u8d77\\u59cb\\u65f6\\u95f4\\u6700\\u65e9\\u7684\\u8282\\u70b9\\u3002"
    )
    _render_mermaid_html(
        _build_mermaid(sel_spans, focus=None),
        height=720,
        key_prefix="explorer",
    )
    # Manual fallback selector (in case Mermaid click is blocked)
    with st.expander(
        "\\u5982\\u679c\\u70b9\\u51fb\\u65e0\\u6548\\uff0c\\u53ef\\u4ee5\\u5728\\u8fd9\\u91cc\\u624b\\u52a8\\u9009\\u62e9\\u4e00\\u4e2a span",
        expanded=False,
    ):
        span_options = [(s["span_id"], _span_display_name(s)) for s in sel_spans]
        labels = [name for _, name in span_options]
        if not labels:
            st.caption("\\u65e0\\u53ef\\u9009 span")
        else:
            picked = st.selectbox(
                "\\u9009\\u62e9 span",
                options=labels,
                key="manual_focus_pick",
                index=0,
            )
            if st.button("\\u805a\\u7126\\u5230\\u8be5 span", key="manual_focus_btn"):
                target_id = next(sid for sid, n in span_options if n == picked)
                _jump_to_span(target_id)


def _render_detail_column(sel_spans, all_by_id, focus):
    """Right column: span detail panel for the focused / selected span."""
    # "Back to overview" clears focus (keeps trace in URL).
    st.markdown("#### \\U0001F50D Span \\u8be6\\u60c5")
    if focus and focus in all_by_id:
        if st.button("\\u2190 \\u8fd4\\u56de\\u5168\\u8c8c", key="back_to_overview"):
            _clear_focus()
        sel_spans_id = focus
        st.session_state.selected_span = focus
    elif st.session_state.selected_span and st.session_state.selected_span in all_by_id:
        sel_spans_id = st.session_state.selected_span
    else:
        # Default to the first root span so the right column never starts empty
        roots = [s for s in sel_spans if not s.get("parent_span_id")]
        sel_spans_id = (roots[0]["span_id"] if roots else sel_spans[0]["span_id"])
        st.session_state.selected_span = sel_spans_id
    _render_detail_panel(sel_spans, by_id_all=all_by_id)
    # If URL has stale focus (span not in current trace), clear it
    if focus and focus not in all_by_id:
        _clear_focus()


def _jump_to_span(span_id):
    """Set focus query param (and preserve trace)."""
    st.query_params["focus"] = span_id
    st.rerun()


def _clear_focus():
    """Clear focus query param, keep trace."""
    if "focus" in st.query_params:
        del st.query_params["focus"]
    st.rerun()


'''

old_block = content[start_idx:end_idx]
content = content[:start_idx] + NEW_FUNC + content[end_idx:]
print("Phase 2: replaced _render_flowchart_mode; old", len(old_block), "new", len(NEW_FUNC))

open(p, "w", encoding="utf-8", newline="\n").write(content)