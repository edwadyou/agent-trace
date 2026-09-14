# -*- coding: utf-8 -*-
# Main entry for the agent-monitor viewer (layout "B": activity diagram + detail).
# Originally the single-file ``viewer.py``; now assembled from the
# ``viewer_app`` package. Run with:  streamlit run viewer.py
from __future__ import annotations

import streamlit as st

from . import state
from .config import _CSS, _dbg
from .data import _discover_trace_sources, _latest_start, load_traces
from .format import _format_duration_ms, _kind_pill_html, _span_display_name
from .render_detail import (
    _clear_focus, _jump_to_span, _render_detail_column, _render_detail_panel,
    _select_trace, _trace_start_ns, _render_run_tab, _render_feedback_tab,
    _render_metadata_tab, _render_span_meta,
)
from .render_activity import _render_activity_center

from viewer.normalize import span_kind


def _render_activity_mode(all_spans, all_by_id, *, n_traces=1):
    """Layout "B": one activity diagram (every span, every trace) + the span
    detail column.

    The old three-column body rendered a per-trace card list on the left and a
    single-trace Mermaid flowchart in the middle, and refused to draw more than
    80 nodes. This view replaces both with one tree rooted at the trace root
    span, so a 100+ span run is shown in full.
    """
    # Deep-link focus: applied once per session (right after a reload). The URL
    # is only READ here, never navigated to, so it cannot cause a page jump.
    if not st.session_state.get('_url_focus_applied'):

        f = st.query_params.get('focus')

        if f and f in all_by_id:

            st.session_state.selected_span = f

        st.session_state._url_focus_applied = True

    cur_sel = st.session_state.selected_span

    if cur_sel and cur_sel not in all_by_id:

        st.session_state.selected_span = None

        cur_sel = None

    # Diagram-first desktop layout.  The detail panel remains fully usable at
    # 35% because its input/output row stacks via a container query when the
    # column is narrow; the CSS also turns this row into a vertical layout on
    # sub-960px viewports.
    col_main, col_right = st.columns([13, 7], gap="small")

    with col_main:
        with st.container(key="activity_panel", border=False, height="stretch"):
            _render_activity_center(
                all_spans, focus=cur_sel or None, n_traces=n_traces
            )

    with col_right:
        with st.container(key="detail_panel", border=False, height="stretch"):
            _render_detail_column(all_spans, all_by_id)


def run():
    """Execute the full viewer page (called by ``streamlit run viewer.py``)."""
    st.markdown(_CSS, unsafe_allow_html=True)
    st.session_state.setdefault("trace_source", None)
    st.session_state.setdefault("selected_trace", None)
    st.session_state.setdefault("selected_span", None)
    sources = _discover_trace_sources()

    _dbg(f"discovered {len(sources)} source(s)")

    for _lbl, _p in sources:

        _dbg(f"  source: {_p}  ({_p.stat().st_size // 1024} KB)")



    if not sources:

        st.markdown(

            """

            <div style="padding: 60px 20px; text-align: center; color: #9ca3af;">

                <div style="font-size: 48px;">🔎</div>

                <h2 style="margin-top: 8px; color: #e5e7eb;">No trace files found</h2>

                <p>The viewer looked in:</p>

                <ul style="display: inline-block; text-align: left;">

                    <li><code>$TRACE_FILE</code> env var</li>

                    <li><code>./latest_traces.jsonl</code> (cwd)</li>

                    <li><code>D:/agent/complex-agent-langchain/latest_traces.jsonl</code></li>

                    <li><code>D:/my-projects/agent-monitor/latest_traces.jsonl</code></li>

                </ul>

                <p>Start your agent with

                  <code style="background: rgba(255,255,255,0.06); padding: 4px 8px; border-radius: 4px;">

                    monitor(..., exporter="jsonl")

                  </code>

                and refresh.

                </p>

            </div>

            """,

            unsafe_allow_html=True,

        )

        st.stop()







    # Pick the most-recently-modified file by default

    if st.session_state.trace_source is None or str(st.session_state.trace_source) not in [str(p) for _, p in sources]:

        st.session_state.trace_source = str(sources[0][1])



    active_label, active_path = next(

        ((lbl, p) for lbl, p in sources if str(p) == st.session_state.trace_source),

        sources[0],

    )

    state.traces, dropped = load_traces(str(active_path))
    _dbg(f"loaded {len(state.traces)} trace(s), {sum(len(s) for s in state.traces.values())} span(s), {dropped} dropped from {active_path}")
    _sort_key = lambda t: (len(state.traces[t]), _latest_start(t))

    trace_ids = sorted(state.traces.keys(), key=_sort_key, reverse=True)

    _dbg(f"BEFORE: {len(trace_ids)} trace id(s); selected_trace = {st.session_state.selected_trace!r}; in state.traces = {st.session_state.selected_trace in state.traces}")

    # Always ensure a valid selection

    if not trace_ids:

        _dbg("ABORT: no trace_ids loaded")

    elif st.session_state.selected_trace is None or st.session_state.selected_trace not in state.traces:

        _old = st.session_state.selected_trace

        st.session_state.selected_trace = trace_ids[0]

        st.session_state.selected_span = None

        _dbg(f"FIX: selected_trace was {_old!r}, now SET to {st.session_state.selected_trace!r}")

    else:

        _dbg(f"KEEP: selected_trace = {st.session_state.selected_trace!r} (valid)")
    hdr_l, hdr_m = st.columns([3, 2])

    with hdr_l:

        st.markdown("## 🔎 Agent 链路监控", unsafe_allow_html=True)

        st.caption(

            f"**{len(state.traces)}** traces / **{sum(len(s) for s in state.traces.values())}** spans"

            + (f"  ·  _dropped {dropped} malformed rows_" if dropped else "")

        )

    with hdr_m:

        if len(sources) > 1:

            try:

                cur_idx = [str(p) for _, p in sources].index(str(active_path))

            except ValueError:

                cur_idx = 0

            new_path_str = st.selectbox(

                "数据源",

                options=[str(p) for _, p in sources],

                index=cur_idx,

                format_func=lambda s: next(lbl for lbl, p in sources if str(p) == s),

                label_visibility="collapsed",

            )

            if new_path_str != str(active_path):

                st.session_state.trace_source = new_path_str

                st.session_state.selected_trace = None

                st.session_state.selected_span = None

                for _k in ('focus', 'trace'):

                    if _k in st.query_params:

                        del st.query_params[_k]

                st.rerun()

        else:

            pass  # single-source mode: do not render the raw path caption
    # -------------------------------------------------------------------------
    # Layout "B" body: every span of every trace in the source, as one tree.
    # -------------------------------------------------------------------------
    all_spans = [s for tid in trace_ids for s in state.traces[tid]]

    if not all_spans:

        st.info("当前数据源中没有 span，请运行你的 agent 后刷新。")

        st.stop()

    all_by_id = {s["span_id"]: s for s in all_spans}

    _dbg(f"BODY: {len(all_spans)} span(s) over {len(trace_ids)} trace(s)")

    _render_activity_mode(

        all_spans,

        all_by_id,

        n_traces=len(trace_ids),

    )
