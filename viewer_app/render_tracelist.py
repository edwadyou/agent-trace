# -*- coding: utf-8 -*-
# Left-hand trace card list + the label/purpose helpers used by the dropdown.
from __future__ import annotations

import re

import streamlit as st

from . import state
from .data import _aggregate_kpi
from .format import _format_duration_ms
from .render_detail import _select_trace, _trace_start_ns

_PURPOSE_SUFFIX_DROP = {

    "executor", "run", "invoke", "call", "step", "agent", "handler",

    "service", "workflow", "pipeline", "chain", "sequence", "task",

    "node", "func", "function", "method", "process", "runner",

    "controller", "manager", "orchestrator", "wrapper", "adapter",

}


def _short_purpose(name: str) -> str:

    """Convert an arbitrary span name into a 1-4 word Purpose phrase.



    Examples::



        verify_claim_executor  -> "Verify Claim"

        persist_report         -> "Persist Report"

        RecheckNews            -> "Recheck News"

        decompose_claim        -> "Decompose Claim"

        _web_search            -> "Web Search"



    Snake_case is split on underscores; PascalCase / camelCase on

    capital letters. Common "infra" suffixes (_executor, _run,

    _agent, _chain, ...) are stripped. Result is capped at 4 words.

    """

    if not isinstance(name, str):

        return ""

    s = name.strip().lstrip("_")

    if not s:

        return ""

    if "_" in s or "-" in s:

        parts = re.split(r"[_-]+", s)

    else:

        # split PascalCase / camelCase: capital letter is a boundary

        parts = re.split(r"(?=[A-Z])", s)

        parts = [p for p in parts if p]

    # drop trailing generic suffixes

    while parts and parts[-1].lower() in _PURPOSE_SUFFIX_DROP:

        parts.pop()

    if not parts:

        # all words were suffixes -> keep the raw cleaned name

        return " ".join(w.capitalize() for w in re.split(r"[_-]+", s))[:40]

    pretty = [w.capitalize() if w.islower() else w for w in parts]

    if len(pretty) > 4:

        pretty = pretty[:4]

    return " ".join(pretty)


def _trace_label(spans: list) -> str:

    """Derive a 2-4 word purpose label for the dropdown.



    Goal: the dropdown row should answer "what does this trace DO?"

    without the user having to click into it. We deliberately avoid

    dumping user input content here (it bloats rows; content varies

    across iterations of the same agent).



    Resolution:

      1. If the root name is a meaningful business name (not a

         generic LangChain wrapper), shorten it via _short_purpose.

      2. Pattern-match LangChain internals:

         - RunnableParallel<tools...>  -> "多任务并行（n）"

         - RunnableSequence with TOOL child spans -> "工具型智能体"

         - RunnableSequence with RETRIEVER child spans -> "检索链"

         - RunnableSequence (Prompt -> LLM -> Parser) -> "LLM 调用链"

         - RunnableSequence (just LLM) -> "大模型调用"

      3. Friendly name via viewer.naming on the root name.

      4. Last resort: "(unnamed)".

    """

    if not spans:

        return "(empty trace)"

    root = next(

        (s for s in spans if not s.get("parent_span_id")),

        spans[0],

    )

    root_id = root.get("span_id")

    root_name = root.get("name") or ""

    root_kind = (root.get("kind") or "").upper()

    children = [

        s for s in spans

        if s.get("parent_span_id") == root_id

    ]

    child_kinds = {c.get("kind", "").upper() for c in children}

    child_names = {c.get("name", "") for c in children}



    # ---- 1) Real business name on root? ----

    if root_name and not root_name.startswith("Runnable"):

        p = _short_purpose(root_name)

        if p:

            return p



    # ---- 2) LangChain wrapper patterns ----

    if root_name.startswith("RunnableParallel"):

        m = re.match(r"^RunnableParallel<(.+)>$", root_name)

        if m:

            tools = [t.strip() for t in m.group(1).split(",") if t.strip()]

            n = len(tools)

            if n == 0:

                return "Parallel Branches"

            if n == 1:

                return f"Parallel: {_short_purpose(tools[0]) or tools[0]}"

            if n == 2:

                a = _short_purpose(tools[0]) or tools[0]

                b = _short_purpose(tools[1]) or tools[1]

                return f"Parallel: {a} + {b}"

            return f"Parallel Search ({n})"

        return "Parallel Branches"



    if root_name.startswith("RunnableSequence"):

        # LangChain instruments ChatPromptTemplate, OutputParser,

        # StrOutputParser, etc. all as kind=CHAIN. So we must

        # detect Prompt/Parser/LLM by NAME patterns - not just by

        # span_kind - otherwise everything classifies as "LLM Call".

        child_names_l = list(child_names)

        child_names_lc = [n.lower() for n in child_names_l]



        has_tool = (

            "TOOL" in child_kinds

            or any(n.endswith("Tool") or "tool" in n.lower() for n in child_names_l)

        )

        has_retriever = (

            "RETRIEVER" in child_kinds

            or any("retriever" in n.lower() for n in child_names_lc)

        )

        has_parser = any(

            n.endswith("OutputParser") or n.endswith("Parser")

            or "OutputParser" in n for n in child_names_l

        )

        has_prompt = any(

            n.endswith("PromptTemplate") or n.endswith("Prompt")

            or "PromptTemplate" in n for n in child_names_l

        )

        has_llm = (

            "LLM" in child_kinds

            or any(n.startswith("Chat") and "Prompt" not in n for n in child_names_l)

        )



        if has_tool:

            return "Tool Agent"

        if has_retriever:

            return "Retrieval Chain"

        if has_llm:

            if has_prompt and has_parser:

                return "LLM Chain"

            if has_prompt:

                return "LLM Call (templated)"

            return "LLM Call"

        # No LLM detected - try to surface a meaningful child name

        for c in children:

            cn = c.get("name") or ""

            if cn and not cn.startswith("Runnable") and not cn.startswith("_"):

                p = _short_purpose(cn)

                if p:

                    return p

        return "Chain Step"



    # ---- 3) friendly_name fallthrough ----

    try:

        from viewer.naming import friendly_name as _fn

        display, _ = _fn(root_name, root_kind)

        if display and display != root_name:

            short = _short_purpose(display) or display

            if short:

                return short[:40]

    except Exception:

        pass



    # ---- 4) raw name shortener ----

    p = _short_purpose(root_name)

    if p:

        return p[:40]

    return "(unnamed)"


def _fmt_trace_option(t: str) -> str:

    """Self-explaining dropdown label.



    Layout:  <status_icon> <label>  <spans>sp <duration>  <tid8>



    The status icon is the first column so users can scan ERROR

    traces from a long list in one glance. The label gives the

    trace's purpose (user input or root span name). The trace_id

    suffix is the disambiguator when many traces share a label.

    """

    spans = state.traces[t] or []

    kk = _aggregate_kpi(spans)

    label = _trace_label(spans)

    if kk.final_status == "ERROR":

        ico = "❌"  # 红色叉（错误）

    elif kk.final_status == "OK":

        ico = "✅"  # 绿色勾（成功）

    else:

        ico = "⏳"  # 沙漏（未完成）

    return (

        f"{ico}  {label}  "

        f"·  {kk.n_spans} spans  "

        f"·  {_format_duration_ms(kk.dur_ms)}  "

        f"·  {t[:8]}"

    )


def _render_trace_cards_list():

    st.markdown('#### 📋 Traces')

    if not state.traces:

        st.caption('还没有 trace。请运行 agent 后刷新。')

        return

    cur_tid = st.session_state.selected_trace

    sorted_tids = sorted(state.traces.keys(), key=_trace_start_ns)

    # Outer scrollable wrapper. CSS targets `.st-key-trace_list_scroll`

    # with `max-height: calc(100vh - 200px); overflow-y: auto;` so the

    # trace list scrolls internally and the page body (center agent flow

    # + right span detail) stays fixed in place. Each trace button below

    # gets key `trace_card_<tid>`, which Streamlit turns into the

    # wrapper class `st-key-trace_card_<sanitized_tid>` we style as a

    # compact card.

    with st.container(key="trace_list_scroll", height="stretch"):

        for tid in sorted_tids:

            row = _fmt_trace_option(tid)

            is_cur = (tid == cur_tid)

            btn_type = 'primary' if is_cur else 'secondary'

            st.button(

                row,

                key=f'trace_card_{tid}',

                type=btn_type,

                use_container_width=True,

                on_click=_select_trace,

                args=(tid,),

            )

__all__ = [_render_trace_cards_list, _fmt_trace_option, _trace_label, _short_purpose, _PURPOSE_SUFFIX_DROP]
