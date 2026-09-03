# -*- coding: utf-8 -*-
# This file was split out of the original ``viewer.py`` single-file app.
# Do not edit by hand where avoidable; keep the module boundaries clean.
from __future__ import annotations

import json

import streamlit as st

from viewer.normalize import canon, span_kind, to_messages
from viewer.visibility import filter_visible_attrs

from . import state
from .data import _aggregate_kpi, _extract_error_info
from .format import (
    _esc, _estimate_cost, _format_duration_ms, _format_tokens,
    _format_ts, _format_ts_ms, _kind_pill_html, _span_display_name,
    _status_label,
)
from .msg import _render_msg
from .structured import _render_input_fallback


def _render_detail_column(sel_spans, all_by_id):

    """Render the span-detail column. ``st.session_state.selected_span`` is the

    single source of truth (updated by flowchart node clicks, no page reload)."""

    st.markdown('#### 🔍 Span 详情')



    sel = st.session_state.selected_span

    roots = [s for s in sel_spans if not s.get('parent_span_id')]

    root_id = roots[0]['span_id'] if roots else None

    if sel and sel in all_by_id:

        if sel != root_id:

            if st.button('← 返回全貌', key='back_to_overview'):

                _clear_focus()

    else:

        if root_id:

            st.session_state.selected_span = root_id



    # Everything below (header card + 3 tabs + every detail-card) goes
    # inside a column-internal scroll container so a long input/output
    # payload does NOT push the page height past the viewport. CSS in
    # config.py gives this key the matching .st-key-detail_scroll rule.
    with st.container(key="detail_scroll", height="stretch"):
        _render_detail_panel(sel_spans, by_id_all=all_by_id)


def _jump_to_span(span_id):

    st.session_state.selected_span = span_id

    if st.query_params.get('focus') != span_id:

        st.query_params['focus'] = span_id

    st.rerun()


def _clear_focus():

    st.session_state.selected_span = None

    if 'focus' in st.query_params:

        del st.query_params['focus']

    st.rerun()


def _select_trace(tid):

    st.session_state.selected_trace = tid

    # Clear URL-carried navigation params so a later node click re-sets them

    # for the newly selected trace (otherwise a stale ?trace= would force the

    # app back to the previous trace after the reload).

    for _k in ('focus', 'trace'):

        if _k in st.query_params:

            del st.query_params[_k]


def _trace_start_ns(tid):

    spans = state.traces.get(tid) or []

    if not spans:

        return 0

    return min(int(s.get('start_time', 0)) for s in spans)


def _render_detail_panel(all_spans: list, *, by_id_all: dict) -> None:

    sel_sid = st.session_state.selected_span

    sel_span = by_id_all.get(sel_sid) if sel_sid else None



    if not sel_span:

        st.markdown(

            '<div class="detail-card" style="text-align:center;color:#9ca3af;'

            'padding:36px 16px;">'

            '<div style="font-size:34px;">👈</div>'

            '<div style="margin-top:6px;">请在左侧树中选中一个节点查看详情。</div>'

            '</div>',

            unsafe_allow_html=True,

        )

        return



    attrs = sel_span.get("attributes") or {}

    kind = span_kind(attrs)

    disp = _span_display_name(sel_span)

    status = str(sel_span.get("status", "")).upper()

    start_ns = int(sel_span.get("start_time", 0))

    end_ns = int(sel_span.get("end_time", 0))

    dur_ms = (end_ns - start_ns) / 1_000_000

    err = _extract_error_info(sel_span) if status == "ERROR" else None

    is_err = bool(err and (err["status_message"] or err["stack"] or err["exception_type"]))



    # Header card

    label, cls = _status_label(status)

    st.markdown(

        f'<div class="detail-card">'

        f'  <div class="detail-head">'

        f'    {_kind_pill_html(kind)}'

        f'    <span>{_esc(disp)}</span>'

        f'    <span style="margin-left:auto">'

        f'      <span class="meta-pill {cls}">{_esc(label)}</span>'

        f'    </span>'

        f'  </div>'

        f'  <div class="detail-sub">'

        f'    {_format_duration_ms(dur_ms)}  ·  span_id={_esc((sel_span.get("span_id","") or "")[:16])}…'

        f'    {("  ·  parent=" + _esc((sel_span.get("parent_span_id") or "")[:16]) + "…") if sel_span.get("parent_span_id") else ""}'

        f'  </div>'

        f'</div>',

        unsafe_allow_html=True,

    )



    tabs = st.tabs(["运行", "反馈", "元数据"])



    # ---- Run tab -----------------------------------------------------------

    with tabs[0]:

        _render_run_tab(sel_span, is_err=is_err, err=err)



    # ---- Feedback tab ------------------------------------------------------

    with tabs[1]:

        _render_feedback_tab(sel_span)



    # ---- Metadata tab ------------------------------------------------------

    with tabs[2]:

        _render_metadata_tab(sel_span)


def _render_run_tab(span: dict, *, is_err: bool, err: dict | None) -> None:

    """The primary span view: collapsible Input + Output + Flow state."""

    attrs = span.get("attributes") or {}

    kind = span_kind(attrs)



    # Always-on: ancestor breadcrumb

    # (ancestry shown via parent chip in header)



    # --- Input / Output side-by-side (headers aligned; each side scrolls independently) --

    c_in, c_out = st.columns(2, gap="medium")



    with c_in:

        st.markdown('<div class="io-col-head in-head">⬇  输入</div>', unsafe_allow_html=True)

        if kind == "LLM":

            msgs = to_messages(canon(attrs, "messages.input"))

            if msgs:

                for m in msgs:

                    role = (m.get("role") or "user").lower()

                    content_val = m.get("content") or ""

                    _render_msg(m)

                    for tc in m.get("tool_calls") or []:

                        nm = tc.get("name") or "tool"

                        with st.expander(f"🔧 {nm}"):

                            st.json(tc.get("arguments"))

            else:

                _render_input_fallback(attrs, "input.value")

        elif kind == "TOOL":

            tp = canon(attrs, "tool.parameters")

            st.markdown("**工具参数：**")

            if tp is None:

                st.caption("（未捕获参数）")

            elif isinstance(tp, str):

                try:

                    st.json(json.loads(tp))

                except (json.JSONDecodeError, TypeError):

                    st.code(tp)

            else:

                st.json(tp)

        else:

            _render_input_fallback(attrs, "input.value")



    with c_out:

        st.markdown('<div class="io-col-head out-head">⬆  输出</div>', unsafe_allow_html=True)

        if kind == "LLM":

            msgs = to_messages(canon(attrs, "messages.output"))

            if msgs:

                for m in msgs:

                    role = (m.get("role") or "assistant").lower()

                    content_val = m.get("content") or ""

                    _render_msg(m)

            else:

                _render_input_fallback(attrs, "output.value")

        elif kind == "TOOL":

            tout = canon(attrs, "tool.output")

            if tout is None:

                st.caption("（未捕获返回结果）")

            elif isinstance(tout, (dict, list)):

                st.json(tout)

            elif isinstance(tout, str):

                try:

                    parsed = json.loads(tout)

                    if isinstance(parsed, (dict, list)):

                        st.json(parsed)

                    else:

                        st.code(str(parsed))

                except (json.JSONDecodeError, TypeError):

                    if len(tout) > 6000:

                        st.code(tout[:6000] + "...truncated")

                    else:

                        st.code(tout)

            else:

                st.code(str(tout))

        else:

            _render_input_fallback(attrs, "output.value")



    # --- Token breakdown (LLM) ----------------------------------------------

    if kind == "LLM":

        items = [

            ("输入 token",      canon(attrs, "tokens.input")),

            ("输出 token",     canon(attrs, "tokens.output")),

            ("总计 token",      canon(attrs, "tokens.total")),

            ("缓存读取 token", canon(attrs, "tokens.cache_read")),

            ("思考 token",  canon(attrs, "tokens.reasoning")),

        ]

        shown = [(k, v) for k, v in items if v is not None]

        if shown:

            cols = st.columns(min(5, len(shown)))

            for col, (k, v) in zip(cols, shown):

                col.metric(k, _format_tokens(v))

        cost = _estimate_cost(span)

        if cost is not None:

            st.caption(f"💰 estimated cost (this span): **${cost:.4f}**")



    # --- Flow state (events log) --------------------------------------------

    events = span.get("events") or []

    with st.expander(f"⏱  Flow state ({len(events)} event(s))", expanded=False):

        if not events:

            st.caption("（未记录 span 事件）")

        else:

            for i, evt in enumerate(events):

                if not isinstance(evt, dict):

                    continue

                ename = evt.get("name", "(event)")

                ets = int(evt.get("time", 0))

                eattrs = evt.get("attributes") or {}

                with st.container():

                    st.markdown(

                        f'<div style="font-size:12px;color:#9ca3af;margin-bottom:4px">' +

                        f'<b style="color:#e5e7eb">{_esc(ename)}</b>  ·  ' +

                        f'{_esc(_format_ts_ms(ets)) if ets else ""}</div>',

                        unsafe_allow_html=True,

                    )

                    if eattrs:

                        st.json(eattrs)



    # --- Error block (only if span errored) ---------------------------------

    if is_err and err:

        st.markdown("#### ⚠ 错误")

        head_bits = []

        if err["exception_type"]:

            head_bits.append(f"<b>{_esc(err['exception_type'])}</b>")

        if err["status_message"]:

            head_bits.append(_esc(err["status_message"]))

        st.markdown(

            f'<div class="callout-err">'

            f'<div>{" &nbsp;·&nbsp; ".join(head_bits) or "(no message)"}</div></div>',

            unsafe_allow_html=True,

        )

        if err["stack"]:

            st.markdown("**堆栈信息：**")

            st.code(err["stack"], language="text")


def _render_feedback_tab(span: dict) -> None:

    """Feedback scores.



    The agent_monitor SDK does not yet record feedback scores; this tab is a

    placeholder that follows the LangSmith / Langfuse UX convention. Any

    feedback captured under ``metadata.feedback`` / ``feedback.*`` attrs is

    surfaced; otherwise we show the empty state.

    """

    attrs = span.get("attributes") or {}

    feedback: list = []

    # Common conventions:

    fb = attrs.get("feedback") or attrs.get("feedbacks")

    if isinstance(fb, list):

        feedback = [x for x in fb if isinstance(x, dict)]

    elif isinstance(fb, dict):

        feedback = [fb]

    # Legacy single-score attrs

    if not feedback:

        score = attrs.get("feedback.score") or attrs.get("score")

        if score is not None:

            feedback.append({"name": "score", "value": score})

    if not feedback:

        st.markdown(

            '<div class="detail-card" style="text-align:center;color:#9ca3af;'

            'padding:30px 16px;">'

            '<div style="font-size:30px;">⭐</div>'

            '<div style="margin-top:6px;">尚未记录反馈分数。</div>'

            '<div style="margin-top:4px;font-size:11px;">'

            '一旦对该运行评分，分数会自动出现在这里。'

            '</div></div>',

            unsafe_allow_html=True,

        )

        return

    for fb in feedback:

        with st.container():

            st.markdown(

                f'<div class="detail-card">'

                f'<b>{_esc(fb.get("name", "feedback"))}</b>  '

                f'<span style="color:#9ca3af">{_esc(fb.get("comment", ""))}</span>'

                f'</div>',

                unsafe_allow_html=True,

            )

            cols = st.columns(3)

            cols[0].metric("Score", str(fb.get("value", "-")))

            cols[1].metric("Source", str(fb.get("source", "-")))

            cols[2].metric("At", _format_ts(fb.get("timestamp") or 0))


def _render_metadata_tab(span: dict) -> None:

    start_ns = int(span.get("start_time", 0))

    end_ns = int(span.get("end_time", 0))

    dur_ms = (end_ns - start_ns) / 1_000_000

    attrs = span.get("attributes") or {}



    st.markdown(

        '<div class="detail-card"><div class="detail-head">基本信息</div>',

        unsafe_allow_html=True,

    )

    rows = [

        ("Trace ID", span.get("trace_id", "")),

        ("Span ID", span.get("span_id", "")),

        ("父 Span ID", span.get("parent_span_id") or "(根 span)"),

        ("服务", span.get("service_name") or "-"),

        ("法案版本", str(span.get("schema_version", "-"))),

        ("Name", span.get("name", "-")),

    ]

    sid = canon(attrs, "session.id")

    uid = canon(attrs, "user.id")

    model = canon(attrs, "model")

    provider = canon(attrs, "model.provider")

    tags = canon(attrs, "tags")

    if sid:

        rows.append(("会话 / 主题", sid))

    if uid:

        rows.append(("用户", uid))

    if model:

        rows.append(("Model", f"{model}" + (f"  ({provider})" if provider else "")))

    if tags:

        if isinstance(tags, list):

            rows.append(("标签", ", ".join(str(t) for t in tags)))

        else:

            rows.append(("标签", str(tags)))

    kv = '<div class="detail-kv">'

    for k, v in rows:

        kv += f'<div class="k">{_esc(k)}</div><div class="v">{_esc(v)}</div>'

    kv += "</div>"

    st.markdown(kv, unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)



    st.markdown(

        '<div class="detail-card"><div class="detail-head">Timing</div>',

        unsafe_allow_html=True,

    )

    m1, m2, m3, m4 = st.columns(4)

    m1.metric("总时长", _format_duration_ms(dur_ms))

    m2.metric("Start", _format_ts(start_ns))

    m3.metric("End", _format_ts(end_ns))

    m4.metric("Span ID", (span.get("span_id", "") or "")[:8] + "…")

    st.markdown("</div>", unsafe_allow_html=True)



    st.markdown(

        '<div class="detail-card"><div class="detail-head">全部属性（过滤后）</div>',

        unsafe_allow_html=True,

    )

    st.json(filter_visible_attrs(attrs, show_raw=False))

    with st.expander("Raw attributes (unfiltered)"):

        st.json(attrs)

    st.markdown("</div>", unsafe_allow_html=True)



    if span.get("events"):

        st.markdown(

            '<div class="detail-card"><div class="detail-head">Span 事件</div>',

            unsafe_allow_html=True,

        )

        st.json(span.get("events"))

        st.markdown("</div>", unsafe_allow_html=True)


def _render_span_meta(span: dict) -> None:

    attrs = span.get("attributes") or {}

    kind = span_kind(attrs)

    name = _span_display_name(span)

    status = str(span.get("status", "")).upper()

    label, cls = _status_label(status)

    start_ns = int(span.get("start_time", 0))

    end_ns = int(span.get("end_time", 0))

    dur_ms = (end_ns - start_ns) / 1_000_000

    tin = canon(attrs, "tokens.input")

    tout = canon(attrs, "tokens.output")

    ttot = canon(attrs, "tokens.total") or (

        (tin + tout) if isinstance(tin, int) and isinstance(tout, int) else None

    )

    model = canon(attrs, "model") or "-"

    provider = canon(attrs, "model.provider") or ""

    cost = _estimate_cost(span)



    rows = [

        ("名称", name),

        ("类型", kind),

        ("Model", f"{model}" + (f"  ({provider})" if provider else "")),

        ("Status", ""),

        ("Start", _format_ts_ms(start_ns)),

        ("End",   _format_ts_ms(end_ns)),

        ("耗时", _format_duration_ms(dur_ms)),

    ]

    st.markdown(

        f'<div style="margin-bottom:6px">'

        f'<span class="meta-pill {cls}">{_esc(label)}</span>'

        f'</div>',

        unsafe_allow_html=True,

    )

    for k, v in rows:

        if k == "Status":

            continue  # already shown above

        st.markdown(

            f'<div class="meta-kv strong">'

            f'<div class="k">{_esc(k)}</div><div class="v">{_esc(v)}</div>'

            f'</div>',

            unsafe_allow_html=True,

        )

    # Tokens

    if ttot is not None:

        st.markdown(

            f'<div class="meta-kv strong">'

            f'<div class="k">Tokens</div><div class="v">{_esc(_format_tokens(ttot))}</div>'

            f'</div>',

            unsafe_allow_html=True,

        )

    elif tin is not None or tout is not None:

        st.markdown(

            f'<div class="meta-kv strong">'

            f'<div class="k">输入 / 输出</div>'

            f'<div class="v">{_esc(_format_tokens(tin))} / {_esc(_format_tokens(tout))}</div>'

            f'</div>',

            unsafe_allow_html=True,

        )

    # Cost (LLM)

    if cost is not None:

        st.markdown(

            f'<div class="meta-kv strong">'

            f'<div class="k">Cost</div><div class="v">${cost:.4f}</div>'

            f'</div>',

            unsafe_allow_html=True,

        )


__all__ = ['_render_detail_column', '_jump_to_span', '_clear_focus', '_select_trace', '_trace_start_ns', '_render_detail_panel', '_render_run_tab', '_render_feedback_tab', '_render_metadata_tab', '_render_span_meta']
