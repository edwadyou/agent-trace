# -*- coding: utf-8 -*-
# This file was split out of the original ``viewer.py`` single-file app.
# Do not edit by hand where avoidable; keep the module boundaries clean.
from __future__ import annotations

import re

import streamlit as st

from viewer.canonical import SPAN_KINDS
from viewer.normalize import span_kind

from .config import _MERMAID_MAX_NODES, _NODE_LABEL_MAX_CHARS, _flowchart_component
from .format import _format_duration_ms, _span_display_name


def _mermaid_safe_id(sid):

    return 'n_' + sid.replace('-', '_')


def _mermaid_label(span):

    attrs = span.get('attributes') or {}

    kind = span_kind(attrs)

    info = SPAN_KINDS.get(kind, SPAN_KINDS['UNKNOWN'])

    icon = info[0]

    name = _span_display_name(span)

    name = re.sub(r'[\"\\#;|]', ' ', name).strip()

    if len(name) > _NODE_LABEL_MAX_CHARS:

        name = name[:_NODE_LABEL_MAX_CHARS - 1] + '...'

    start_ns = int(span.get('start_time', 0))

    end_ns = int(span.get('end_time', 0))

    dur_ms = (end_ns - start_ns) / 1_000_000

    dur = _format_duration_ms(dur_ms)

    return f'<b>{icon} {name}</b><br/><small>{kind} &middot; {dur}</small>'


def _build_mermaid(spans, *, focus=None, hops=2):

    if not spans:

        return 'flowchart TD\n    empty[　（无 span）　]'

    spans_by_id = {s['span_id']: s for s in spans}

    if focus and focus in spans_by_id:

        visible = {focus}

        up, down = {focus}, {focus}

        for _ in range(hops):

            new_up = set()

            for sid in up:

                pid = spans_by_id.get(sid, {}).get('parent_span_id')

                if pid and pid in spans_by_id and pid not in visible:

                    new_up.add(pid)

            visible |= new_up

            up = new_up

            new_down = set()

            for sid in down:

                for s in spans:

                    if s.get('parent_span_id') == sid and s['span_id'] not in visible:

                        new_down.add(s['span_id'])

            visible |= new_down

            down = new_down

    else:

        visible = {s['span_id'] for s in spans}

    visible_spans = [s for s in spans if s['span_id'] in visible]

    if len(visible_spans) > _MERMAID_MAX_NODES and not focus:

        return (

            'flowchart TD\n'

            '    root[<　共 ' + str(len(spans)) + ' 个 span　<br/>'

            '<small>节点数过多，请切回 列表 模式查看</small>]\n'

            '    classDef root fill:#4b5563,color:#fff,stroke:#1f2937;\n'

            '    class root root;')

    visible_spans.sort(key=lambda s: int(s.get('start_time', 0)))

    starts = [int(s.get('start_time', 0)) for s in visible_spans]

    min_start = min(starts) if starts else 0

    out = ['flowchart TD']

    for css in [

        '    classDef llm       fill:#1d4ed8,color:#fff,stroke:#1e3a8a,stroke-width:1px;',

        '    classDef chain     fill:#065f46,color:#fff,stroke:#064e3b,stroke-width:1px;',

        '    classDef tool      fill:#b45309,color:#fff,stroke:#7c2d12,stroke-width:1px;',

        '    classDef agent     fill:#a16207,color:#fff,stroke:#713f12,stroke-width:1px;',

        '    classDef retriever fill:#7e22ce,color:#fff,stroke:#581c87,stroke-width:1px;',

        '    classDef embedding fill:#0e7490,color:#fff,stroke:#164e63,stroke-width:1px;',

        '    classDef reranker  fill:#6d28d9,color:#fff,stroke:#4c1d95,stroke-width:1px;',

        '    classDef prompt    fill:#3f6212,color:#fff,stroke:#365314,stroke-width:1px;',

        '    classDef parser    fill:#4b5563,color:#fff,stroke:#1f2937,stroke-width:1px;',

        '    classDef evaluator fill:#a8a29e,color:#1c1917,stroke:#78716c,stroke-width:1px;',

        '    classDef guardrail fill:#b91c1c,color:#fff,stroke:#7f1d1d,stroke-width:1px;',

        '    classDef unknown   fill:#6b7280,color:#fff,stroke:#374151,stroke-width:1px;',

        '    classDef error     stroke:#ef4444,stroke-width:2px,color:#fff;',

        '    classDef focus     stroke:#facc15,stroke-width:3px;',

        '    linkStyle default stroke:#64748b,stroke-width:1px;']:

        out.append(css)

    children_by_parent = {}

    for s in visible_spans:

        pid = s.get('parent_span_id')

        if pid and pid in visible:

            children_by_parent.setdefault(pid, []).append(s)

    _handled_parents = set()

    for span in visible_spans:

        sid = span['span_id']

        nid = _mermaid_safe_id(sid)

        kind = span_kind(span.get('attributes') or {})

        kind_class = kind.lower() if kind in SPAN_KINDS else 'unknown'

        cls = [kind_class]

        if str(span.get('status', '')).upper() == 'ERROR':

            cls.append('error')

        if sid == focus:

            cls.append('focus')

        start_ns = int(span.get('start_time', 0))

        offset_ms = int((start_ns - min_start) / 1_000_000)

        label = _mermaid_label(span)

        full_label = f"{label}<br/><small>t+{offset_ms}ms</small>"

        safe = re.sub(r'[\"\\#;|]', ' ', full_label).strip()

        out.append(f'    {nid}["{safe}"]')

        out.append(f'    class {nid} {",".join(cls)};')

    for parent_id, kids in children_by_parent.items():

        if len(kids) < 2:

            continue

        sorted_kids = sorted(kids, key=lambda s: int(s.get('start_time', 0)))

        n_kids = len(sorted_kids)

        all_sequential = True

        for i in range(n_kids - 1):

            prev_end = int(sorted_kids[i].get('end_time', 0))

            next_start = int(sorted_kids[i + 1].get('start_time', 0))

            if next_start < prev_end:

                all_sequential = False

                break

        pnid = _mermaid_safe_id(parent_id)

        if all_sequential:

            _handled_parents.add(parent_id)

            first_id = _mermaid_safe_id(sorted_kids[0]['span_id'])

            out.append(f'    {pnid} --> {first_id}')

            for i in range(n_kids - 1):

                a = _mermaid_safe_id(sorted_kids[i]['span_id'])

                b = _mermaid_safe_id(sorted_kids[i + 1]['span_id'])

                out.append(f'    {a} --> {b}')

        else:

            _handled_parents.add(parent_id)

            out.append('    subgraph SG_' + pnid + '["并行分支"]')

            out.append('    direction LR')

            for k in sorted_kids:

                out.append('        ' + _mermaid_safe_id(k['span_id']))

            out.append('    end')

            for k in sorted_kids:

                out.append(f'    {pnid} --> {_mermaid_safe_id(k["span_id"])}')

    for span in visible_spans:

        pid = span.get('parent_span_id')

        if pid and pid in visible and pid not in _handled_parents:

            out.append(f'    {_mermaid_safe_id(pid)} --> {_mermaid_safe_id(span["span_id"])}')

    return '\n'.join(out)


def _render_flowchart_component(sel_spans, *, focus=None, trace_id=''):

    """Render the mermaid flowchart inside a bidirectional component.



    Clicking a span node makes the frontend send the span_id back via the

    component protocol -> Streamlit reruns in-place (NO full-page reload) ->

    ``st.session_state.selected_span`` is updated -> the right-hand detail

    column switches to that span.  The URL is only synced for deep-linking;

    it is never used to navigate the page.

    """

    if _flowchart_component is None:

        st.warning('未找到 flowchart_component/，无法渲染流程图。')

        return

    sel_ids = {s['span_id'] for s in sel_spans}

    # Always render the FULL flowchart (no click-to-zoom).  Clicking a node

    # only highlights it and switches the right-hand detail; the middle column

    # keeps showing every span node as the user expects.

    mermaid_src = _build_mermaid(sel_spans, focus=None)

    clicked = _flowchart_component(

        mermaid_src=mermaid_src,

        focus=focus or '',

        trace_id=trace_id or '',

        default=None,

        key=f'flowchart_{trace_id or "default"}',

    )

    if isinstance(clicked, dict) and clicked.get('span_id'):

        # The component keeps the last sent value across reruns.  Deduplicate

        # with the per-click timestamp so a *stale* value never re-selects a

        # span (e.g. right after "back to overview"), while a *new* click on

        # the same span still works.

        ts = clicked.get('ts')

        if ts is not None and ts != st.session_state.get('_last_flow_click_ts'):

            st.session_state._last_flow_click_ts = ts

            sid = str(clicked['span_id'])

            if sid in sel_ids:

                st.session_state.selected_span = sid

                # Sync URL for deep-linking only — st.query_params updates go

                # through the frontend history API and do NOT reload the page.

                if st.query_params.get('focus') != sid:

                    st.query_params['focus'] = sid

                if trace_id and st.query_params.get('trace') != trace_id:

                    st.query_params['trace'] = trace_id


def _render_flowchart_center(sel_spans, *, focus=None, trace_id=''):

    """Render the Mermaid flowchart. Pass focus=<span_id> to highlight the matching node (yellow border via the focus classDef)."""

    st.markdown('#### 🔀 Agent 流程图')

    st.caption(

        f'共 {len(sel_spans)} 个 span。'

        '点击节点查看详情；'

        '上方为起始时间最早的节点。'

    )

    _render_flowchart_component(sel_spans, focus=focus, trace_id=trace_id)


__all__ = ['_mermaid_safe_id', '_mermaid_label', '_build_mermaid', '_render_flowchart_component', '_render_flowchart_center']
