# -*- coding: utf-8 -*-
"""UML-activity-diagram view of a whole agent run.

Layout "B": the old left-hand trace-card list and the centre single-trace
flowchart are replaced by ONE activity diagram that shows *every* span of the
selected trace source as a single tree, rooted at the trace's root span (a
normal agent run now produces exactly one root - see the v1.1.1 thread-context
fix).  The right-hand span-detail column is unchanged.

Why a separate module instead of adding flags to ``render_flowchart``:

* ``render_flowchart._build_mermaid`` deliberately caps the graph at
  ``_MERMAID_MAX_NODES`` (80) and can only draw the *currently selected* trace.
  Both behaviours are exactly what this view must not do, so the activity
  diagram gets its own tree walker rather than piling flags onto the old one.
* The two views can then coexist and be swapped back without one silently
  changing the other's output.

How the parts map onto activity-diagram notation
------------------------------------------------
======================  ==================================================
initial node            ``adstart(["▶ 开始"])``
final node              ``adend(["■ 结束"])``
activity                ``n_<sid>("label")`` - one rounded rectangle per span
activity group (root)   ``n_<sid>(["label"])`` - the root span of a trace
fork bar                ``adfork<i>{{"并行 · n"}}`` - before parallel branches
join bar                ``adjoin<i>{{"汇聚"}}`` - after parallel branches
virtual root            ``adroot{{"◆ 全部 traces · n"}}`` - only when the
                        source contains more than one root span
over-limit notice       ``adinfo[...]`` - only when the source has more spans
                        than ``_ACTIVITY_MAX_NODES``
======================  ==================================================

Mermaid node-id contract
------------------------
The mermaid id of a span is **exactly** ``n_<span_id with '-' -> '_'>``
(``render_flowchart._mermaid_safe_id``), because
``flowchart_component/index.html`` recovers the span id from the node id with
``/(n_[A-Za-z0-9_]+)/`` and posts it back to Streamlit.  Every *synthetic* node
id must therefore avoid the substring ``n_`` -- an id such as ``adjo_in`` would
read as a click on span ``o-in``.  See ``_SYNTHETIC_ID_PREFIXES`` and the
matching assertion in ``tests/test_activity_diagram.py``.

Emphasis (error / focus / root) is applied with a per-node ``style`` statement
instead of extra CSS classes, so a node never needs more than one class and the
kind fill colour defined by ``classDef`` always survives.
"""
from __future__ import annotations

import re
from collections import OrderedDict, defaultdict, namedtuple

import streamlit as st

from viewer.canonical import SPAN_KINDS
from viewer.normalize import span_kind

from .config import _flowchart_component
from .format import _format_duration_ms, _span_display_name
from .render_flowchart import _mermaid_safe_id

# ---------------------------------------------------------------------------
# Synthetic (non-span) mermaid node ids.  MUST NOT contain "n_" - see the
# module docstring.  Keep them in sync with _SYNTHETIC_ID_PREFIXES below.
# ---------------------------------------------------------------------------
_START_ID = 'adstart'
_END_ID = 'adend'
_VROOT_ID = 'adroot'
_ROOT_JOIN_ID = 'adrootjoin'
_INFO_ID = 'adinfo'
_FORK_FMT = 'adfork{0}'
_JOIN_FMT = 'adjoin{0}'

_SYNTHETIC_ID_PREFIXES = (
    'adstart', 'adend', 'adroot', 'adrootjoin', 'adinfo', 'adfork', 'adjoin',
)

# Browser-safety valve, NOT a display preference.  The whole point of this view
# is to drop the old 80-node cap, but a few thousand mermaid nodes would lock
# the browser tab up, so we stop far above any realistic agent run (a 185-span
# run renders fine) and say why instead of silently truncating.
_ACTIVITY_MAX_NODES = 2000

# Per-diagram mermaid config.  ``useMaxWidth: false`` keeps the diagram at its
# natural size so the labels stay readable for a 100+ node tree (the component's
# global setting fits the SVG to the column width, which shrinks a big graph
# into unreadable mush); the container then scrolls.
_INIT = (
    '%%{init: {"flowchart": {"curve": "linear", "useMaxWidth": false, '
    '"htmlLabels": true, "nodeSpacing": 20, "rankSpacing": 30}}}%%'
)

# Repeated-call collapse (v1.1.2).  An agent loop repeats the *same* subtree once
# per round, so a literal one-node-per-span graph is mostly N copies of a 4-node
# pattern -- 28 x RunnableSequence(prompt, llm, 2 internal steps).  Mermaid puts
# those 28 siblings side by side, which is why a 195-span run came out as a
# 211-node, ~14000px-wide diagram that could not be read as a whole.  Folding
# each group of structurally identical siblings into ONE node labelled "xN"
# -- and carrying N down the subtree -- keeps every span accounted for while
# shrinking that same run to ~19 nodes.  _AGG_STYLE marks such a node as a
# group rather than a single activity (dashed border).
_AGG_STYLE = 'stroke-dasharray:4 3'

# Two guards keep the folding from eating structure the reader still wants:
#
# * only a *parallel* fan-out is folded.  Sequential siblings are already drawn
#   as a single vertical chain, so they never make the graph wide -- folding a
#   chain would hide the order it exists to show.
# * a group needs at least this many members.  Folding 2 nodes into 1 saves one
#   node and costs the branch split; folding 28 is the difference between an
#   unreadable row and one node.
_AGG_MIN_GROUP = 3

# kind -> (fill, text colour, stroke), mirrored from the flowchart classDefs so
# the two views stay visually consistent.
_KIND_STYLE = {
    'llm':       ('#1d4ed8', '#ffffff', '#1e3a8a'),
    'chain':     ('#065f46', '#ffffff', '#064e3b'),
    'tool':      ('#b45309', '#ffffff', '#7c2d12'),
    'agent':     ('#a16207', '#ffffff', '#713f12'),
    'retriever': ('#7e22ce', '#ffffff', '#581c87'),
    'embedding': ('#0e7490', '#ffffff', '#164e63'),
    'reranker':  ('#6d28d9', '#ffffff', '#4c1d95'),
    'prompt':    ('#3f6212', '#ffffff', '#365314'),
    'parser':    ('#4b5563', '#ffffff', '#1f2937'),
    'evaluator': ('#a8a29e', '#1c1917', '#78716c'),
    'guardrail': ('#b91c1c', '#ffffff', '#7f1d1d'),
    'unknown':   ('#6b7280', '#ffffff', '#374151'),
}


def _ns(value) -> int:
    """Tolerant nanosecond accessor (records may carry null / strings)."""
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _start_key(span: dict) -> int:
    return _ns(span.get('start_time'))


def _end_key(span: dict) -> int:
    return _ns(span.get('end_time'))


def sanitize_label(text) -> str:
    """Make an arbitrary span name safe inside a double-quoted mermaid label.

    Quoting (``n_x("...")``) is what keeps ``#``, ``;`` and ``|`` harmless, so
    only the two characters that could terminate or escape the quoted string are
    removed; every other control character is folded into a space.  HTML
    significant characters are escaped *before* the caller wraps the text in its
    own markup.
    """
    s = '' if text is None else str(text)
    s = s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    s = re.sub(r'["\\]', ' ', s)
    s = ''.join((' ' if ch < ' ' else ch) for ch in s)
    return re.sub(r'\s+', ' ', s).strip()


def _kind_class(span: dict) -> str:
    kind = span_kind(span.get('attributes') or {})
    key = (kind or 'UNKNOWN').lower()
    return key if key in _KIND_STYLE else 'unknown'


def _activity_label(span: dict, mult: int = 1) -> str:
    """``<icon> <name><br/><small>KIND [· xN] · duration</small>``."""
    attrs = span.get('attributes') or {}
    kind = span_kind(attrs)
    icon = (SPAN_KINDS.get(kind) or SPAN_KINDS['UNKNOWN'])[0]
    raw = _span_display_name(span) or span.get('name') or '(unnamed)'
    name = sanitize_label(raw) or '(unnamed)'
    dur = _format_duration_ms((_end_key(span) - _start_key(span)) / 1_000_000)
    if mult > 1:
        meta = f'{kind} \u00b7 \u00d7{mult} 并发 \u00b7 {dur}'
    else:
        meta = f'{kind} \u00b7 {dur}'
    title = name.replace("'", '&#39;')
    return (
        f"<span class=activity-name title='{title}'>{icon} {name}</span><br/>"
        f'<small class=activity-meta>{meta}</small>'
    )


def _time_phases(items: list, *, start_fn=_start_key, end_fn=_end_key) -> list:
    """Partition time-sorted items into maximal overlap phases.

    A new phase starts only once every item in the preceding phase has ended.
    This preserves a truthful top-to-bottom sequence around concurrent work:
    ``step -> fork(overlap...) -> join -> next step``.  Ties are deterministic
    so refreshes cannot shuffle otherwise identical spans.
    """
    def stable_id(item):
        if isinstance(item, dict):
            return str(item.get('span_id', ''))
        if isinstance(item, tuple) and item:
            return str(item[0])
        return str(getattr(item, 'nid', ''))

    ordered = sorted(
        items,
        key=lambda item: (start_fn(item), end_fn(item), stable_id(item)),
    )
    phases: list = []
    current: list = []
    phase_end = 0
    for item in ordered:
        start = start_fn(item)
        end = max(start, end_fn(item))
        if current and start >= phase_end:
            phases.append(current)
            current = []
        if not current:
            phase_end = end
        else:
            phase_end = max(phase_end, end)
        current.append(item)
    if current:
        phases.append(current)
    return phases


def _all_sequential(kids: list) -> bool:
    """True when every chronological phase contains exactly one sibling."""
    return all(len(phase) == 1 for phase in _time_phases(kids))


def _build_forest(spans: list):
    """Return ``(tree_children, roots)`` - a spanning forest over ``spans``.

    Walks the real ``parent_span_id`` links and, crucially, *claims* every span
    exactly once: a malformed file with a parent cycle (a -> b -> a) or with a
    dangling parent can then neither hide a span nor produce a cyclic Mermaid
    edge.  Whatever is left unreachable is promoted to a root, so the diagram
    always contains all spans.
    """
    by_id = {s['span_id']: s for s in spans}
    raw_children: dict = defaultdict(list)
    roots: list = []
    for s in spans:
        pid = s.get('parent_span_id')
        if pid and pid != s['span_id'] and pid in by_id:
            raw_children[pid].append(s)
        else:
            roots.append(s)
    for kids in raw_children.values():
        kids.sort(key=lambda s: (_start_key(s), _end_key(s), s['span_id']))
    roots.sort(key=lambda s: (_start_key(s), _end_key(s), s['span_id']))

    tree_children: dict = defaultdict(list)
    # ``processed`` = popped and expanded; ``attached`` = already has a place in
    # the tree.  They must be tracked separately: marking a node in ``processed``
    # at *enqueue* time made the pop-time guard skip it again, so the walk only
    # ever went two levels deep and every grandchild was mis-reported as a root.
    processed: set = set()
    attached: set = {s['span_id'] for s in roots}
    queue = list(roots)
    while True:
        while queue:
            s = queue.pop(0)
            sid = s['span_id']
            if sid in processed:
                continue
            processed.add(sid)
            for kid in raw_children.get(sid, ()):
                ksid = kid['span_id']
                if ksid in processed or ksid in attached:
                    continue
                attached.add(ksid)
                tree_children[sid].append(kid)
                queue.append(kid)
        if len(processed) >= len(spans):
            break
        nxt = next((s for s in spans if s['span_id'] not in processed), None)
        if nxt is None:
            break
        attached.add(nxt['span_id'])
        roots.append(nxt)
        queue.append(nxt)
    roots.sort(key=lambda s: (_start_key(s), _end_key(s), s['span_id']))
    return tree_children, roots


_RNode = namedtuple('_RNode', 'span mult nid start end')
_RPlan = namedtuple('_RPlan', 'nodes edges kids aggregated')
_Flow = namedtuple('_Flow', 'entry exits')


def _sequential_nodes(nodes: list) -> bool:
    """``_all_sequential`` for rendered nodes, which carry their own time range.

    An aggregated node's range covers its whole group, so two groups that each
    stand for "N calls spread across the run" overlap in time and are drawn as
    parallel branches rather than as a false sequence.
    """
    return all(len(phase) == 1 for phase in _rendered_phases(nodes))


def _rendered_phases(nodes: list) -> list:
    """``_time_phases`` for ``(nid, _RNode)`` child entries."""
    return _time_phases(
        nodes,
        start_fn=lambda item: item[1].start,
        end_fn=lambda item: item[1].end,
    )


def _shape_signatures(roots, children) -> dict:
    """``span_id -> shape`` of that span's entire subtree.

    Two siblings get the same shape exactly when their subtrees agree in name,
    kind and recursion -- which is precisely the case for the iterations of an
    agent loop, and precisely what makes folding them safe.  Computed with an
    explicit stack rather than recursion so a deeply nested trace cannot blow
    the interpreter's recursion limit.
    """
    sig: dict = {}
    stack = [(r, False) for r in reversed(list(roots))]
    while stack:
        node, expanded = stack.pop()
        sid = node['span_id']
        if sid in sig:
            continue
        kids = children.get(sid, ())
        if expanded or not kids:
            sig[sid] = (
                str(_span_display_name(node) or node.get('name') or ''),
                str(span_kind(node.get('attributes') or {})),
                tuple(sorted(sig[k['span_id']] for k in kids)),
            )
            continue
        stack.append((node, True))
        for kid in reversed(list(kids)):
            if kid['span_id'] not in sig:
                stack.append((kid, False))
    return sig


def _plan_layout(roots, children, sig, *, collapse=True, expand=()) -> _RPlan:
    """Decide which nodes get drawn, and as what, before touching mermaid.

    Siblings are grouped by subtree shape.  A group of ``_AGG_MIN_GROUP`` or
    more is drawn as a single node -- but only under the two guards above, so a
    sequential chain and a two-way split keep their structure.  ``mult`` is
    multiplied into the group's representative and then *carried down* its
    subtree, so every span the group stands for is still represented in the
    diagram, just not drawn N times.  ``expand`` lists the representatives the
    user asked to see unfolded.

    The representative is always ``group[0]``, and children are pre-sorted by
    start time in ``_build_forest``, so the choice is stable across reruns.
    """
    expand = set(expand or ())
    nodes: list = []
    edges: list = []
    aggregated: set = set()
    pending: list = [(r, 1, None, None, None) for r in roots]
    i = 0
    while i < len(pending):
        span, mult, parent_nid, lo, hi = pending[i]
        i += 1
        nid = _mermaid_safe_id(span['span_id'])
        nodes.append(_RNode(
            span, mult, nid,
            lo if lo is not None else _start_key(span),
            hi if hi is not None else _end_key(span),
        ))
        if parent_nid is not None:
            edges.append((parent_nid, nid))
        kids = list(children.get(span['span_id'], ()))
        if not kids:
            continue
        # First preserve chronological stages, then fold within a stage.  The
        # old order did this globally and merged early, middle and final calls
        # into one long aggregate whose time range made every root child look
        # parallel (including the final persist step).
        for phase in _time_phases(kids):
            groups: dict = OrderedDict()
            for kid in phase:
                groups.setdefault(sig[kid['span_id']], []).append(kid)
            fan_out = len(phase) > 1
            for group in groups.values():
                if (collapse and fan_out and len(group) >= _AGG_MIN_GROUP
                        and group[0]['span_id'] not in expand):
                    rep = group[0]
                    aggregated.add(rep['span_id'])
                    pending.append((
                        rep, mult * len(group), nid,
                        min(_start_key(g) for g in group),
                        max(_end_key(g) for g in group),
                    ))
                else:
                    for kid in group:
                        pending.append((kid, mult, nid, None, None))

    by_nid = {node.nid: node for node in nodes}
    kids_map: dict = defaultdict(list)
    for parent_nid, child_nid in edges:
        kids_map[parent_nid].append((child_nid, by_nid[child_nid]))
    for group in kids_map.values():
        group.sort(key=lambda item: (item[1].start, item[1].end, item[0]))
    return _RPlan(nodes, edges, kids_map, aggregated)


def _activity_plan(spans, *, collapse=True, expand=()):
    """``(plan, roots)`` for ``spans`` under the given folding settings."""
    children, roots = _build_forest(spans)
    sig = _shape_signatures(roots, children)
    return _plan_layout(roots, children, sig,
                        collapse=collapse, expand=expand), roots


def _collapsed_groups(spans, *, expand=()) -> set:
    """Span ids that are drawn as a collapsed ``xN`` group node.

    The component needs this to tell "the user clicked a single activity" from
    "the user clicked a xN group", which is the difference between selecting a
    span and unfolding a group.
    """
    if not spans:
        return set()
    return _activity_plan(spans, collapse=True, expand=expand)[0].aggregated


def _flow_layout(plan: _RPlan):
    """Return subtree entry/exits plus stable per-phase fork/join ids.

    A rendered activity node is the entry of its subtree.  Its exit is the
    final chronological phase's real exit. Each parent can contain several
    ordered phases and therefore several independent fork/join pairs.
    """
    parallel: dict[tuple[str, int], tuple[str, str]] = {}
    fork_no = 0
    for node in plan.nodes:
        kids = plan.kids.get(node.nid) or []
        for phase_no, phase in enumerate(_rendered_phases(kids)):
            if len(phase) > 1:
                fork_no += 1
                parallel[(node.nid, phase_no)] = (
                    _FORK_FMT.format(fork_no),
                    _JOIN_FMT.format(fork_no),
                )

    flows: dict[str, _Flow] = {}
    # _plan_layout always appends a child after its parent, so reverse order is
    # a post-order traversal even though the forward list is breadth-first.
    for node in reversed(plan.nodes):
        kids = plan.kids.get(node.nid) or []
        phases = _rendered_phases(kids)
        if not phases:
            exits = (node.nid,)
        else:
            last_no = len(phases) - 1
            last_phase = phases[last_no]
            if len(last_phase) > 1:
                exits = (parallel[(node.nid, last_no)][1],)
            else:
                exits = flows[last_phase[0][0]].exits
        flows[node.nid] = _Flow(node.nid, exits)
    return flows, parallel


def _build_activity_diagram(spans, *, focus=None, collapse=True, expand=None) -> str:
    """Render ``spans`` as one mermaid activity-diagram tree.

    ``focus`` only adds a highlight ``style``; it never changes the topology, so
    clicking a node does not re-shape the diagram under the cursor.  ``collapse``
    folds structurally identical sibling subtrees into one ``xN`` node (see
    ``_plan_layout``) -- pass ``False`` for the literal one-node-per-span graph,
    and ``expand`` to unfold individual groups.
    """
    # one classDef per span kind + the three notation-only classes
    head = [_INIT, 'flowchart TD']
    for name, (fill, color, stroke) in _KIND_STYLE.items():
        head.append(f'    classDef {name} fill:{fill},color:{color},stroke:{stroke};')
    head.append('    classDef term fill:#334155,color:#f8fafc,stroke:#94a3b8;')
    head.append('    classDef bar fill:#475569,color:#f1f5f9,stroke:#cbd5e1;')
    head.append('    classDef vroot fill:#111827,color:#f8fafc,stroke:#fbbf24;')
    head.append('    linkStyle default stroke:#64748b,stroke-width:1px;')

    spans = [s for s in (spans or []) if isinstance(s, dict) and s.get('span_id')]

    if not spans:
        return '\n'.join(head + [
            f'    {_START_ID}(["\u25b6 开始"])',
            f'    {_END_ID}(["\u25a0 结束"])',
            f'    {_START_ID} --> {_END_ID}',
            f'    class {_START_ID} term;',
            f'    class {_END_ID} term;',
        ])

    if len(spans) > _ACTIVITY_MAX_NODES:
        return '\n'.join(head + [
            f'    {_START_ID}(["\u25b6 开始"])',
            f'    {_END_ID}(["\u25a0 结束"])',
            f'    {_INFO_ID}["\u5171 {len(spans)} \u4e2a span<br/>'
            f'<small>\u8d85\u8fc7 {_ACTIVITY_MAX_NODES} \u7684\u6e32\u67d3\u4e0a\u9650'
            f'\uff0c\u672a\u7ed8\u5236</small>"]',
            f'    {_START_ID} --> {_INFO_ID} --> {_END_ID}',
            f'    class {_START_ID} term;',
            f'    class {_END_ID} term;',
            f'    class {_INFO_ID} vroot;',
        ])

    plan, roots = _activity_plan(spans, collapse=collapse, expand=expand)
    root_ids = {s['span_id'] for s in roots}
    multi_root = len(roots) > 1

    body: list = [
        f'    {_START_ID}(["\u25b6 开始"])',
        f'    {_END_ID}(["\u25a0 结束"])',
        f'    class {_START_ID} term;',
        f'    class {_END_ID} term;',
    ]
    if multi_root:
        body.append(
            f'    {_VROOT_ID}{{"\u25c6 全部 traces \u00b7 {len(roots)}"}}'
        )
        body.append(f'    class {_VROOT_ID} vroot;')

    # ---- activity nodes: one per span, or one per repeated-subtree group ----
    for node in plan.nodes:
        span = node.span
        sid = span['span_id']
        label = _activity_label(span, node.mult)
        if sid in root_ids:
            body.append(f'    {node.nid}(["{label}"])')
        elif node.mult > 1:
            # UML "predefined process": N identical activities, drawn once.
            body.append(f'    {node.nid}[["{label}"]]')
        else:
            body.append(f'    {node.nid}("{label}")')
        body.append(f'    class {node.nid} {_kind_class(span)};')

        style_bits: list = []
        if sid == focus:
            # focus wins over the error stroke: the user just clicked this node.
            style_bits = ['stroke:#facc15', 'stroke-width:3px']
        else:
            if str(span.get('status', '')).upper() == 'ERROR':
                style_bits += ['stroke:#ef4444', 'stroke-width:2px']
            if sid in root_ids:
                style_bits += ['stroke-width:3px']
        if node.mult > 1:
            style_bits.append(_AGG_STYLE)
        if style_bits:
            body.append(f'    style {node.nid} {",".join(style_bits)}')

    flows, parallel = _flow_layout(plan)

    # ---- initial node -> root(s) ------------------------------------------
    if multi_root:
        body.append(f'    {_START_ID} --> {_VROOT_ID}')
        for r in roots:
            body.append(f'    {_VROOT_ID} --> {_mermaid_safe_id(r["span_id"])}')
    else:
        body.append(f'    {_START_ID} --> {_mermaid_safe_id(roots[0]["span_id"])}')

    # ---- subtree-aware, chronological control flow ------------------------
    for node in plan.nodes:
        kids = plan.kids.get(node.nid) or []
        if not kids:
            continue
        frontier = (node.nid,)
        for phase_no, phase in enumerate(_rendered_phases(kids)):
            if len(phase) == 1:
                child_nid = phase[0][0]
                for exit_id in frontier:
                    body.append(f'    {exit_id} --> {flows[child_nid].entry}')
                frontier = flows[child_nid].exits
                continue

            fid, jid = parallel[(node.nid, phase_no)]
            body.append(f'    {fid}{{"并行 \u00b7 {len(phase)}"}}')
            body.append(f'    class {fid} bar;')
            body.append(f'    {jid}{{"汇聚"}}')
            body.append(f'    class {jid} bar;')
            for exit_id in frontier:
                body.append(f'    {exit_id} --> {fid}')
            for nid, _node in phase:
                body.append(f'    {fid} --> {flows[nid].entry}')
            for nid, _node in phase:
                for exit_id in flows[nid].exits:
                    body.append(f'    {exit_id} --> {jid}')
            frontier = (jid,)

    # ---- complete every root subtree before the final node ----------------
    root_nids = [_mermaid_safe_id(r['span_id']) for r in roots]
    if multi_root:
        body.append(f'    {_ROOT_JOIN_ID}{{"全部完成"}}')
        body.append(f'    class {_ROOT_JOIN_ID} bar;')
        for nid in root_nids:
            for exit_id in flows[nid].exits:
                body.append(f'    {exit_id} --> {_ROOT_JOIN_ID}')
        body.append(f'    {_ROOT_JOIN_ID} --> {_END_ID}')
    else:
        for exit_id in flows[root_nids[0]].exits:
            body.append(f'    {exit_id} --> {_END_ID}')

    return '\n'.join(head + body)


def _render_activity_component(all_spans, *, focus=None, collapse=True,
                               expand=None) -> None:
    """Render the activity diagram in the click-back component.

    Same protocol as the flowchart: a node click posts ``{span_id, ts}`` back,
    which updates ``st.session_state.selected_span`` and therefore the
    right-hand detail column, without navigating the page.

    Clicking a ``xN`` group node does double duty: it selects the group's
    representative span AND unfolds that group, because "let me look at this
    one" is the only sensible reading of a click on a node standing for 28
    identical subtrees.  The per-click timestamp is what keeps a stale component
    value from re-triggering the unfold on every later rerun.
    """
    if _flowchart_component is None:
        st.warning('未找到 flowchart_component/，无法渲染活动图。')
        return

    sel_ids = {s['span_id'] for s in all_spans}
    mermaid_src = _build_activity_diagram(
        all_spans, focus=None, collapse=collapse, expand=expand
    )

    clicked = _flowchart_component(
        mermaid_src=mermaid_src,
        focus=focus or '',
        trace_id='',
        default=None,
        key='activity_all',
    )

    if not (isinstance(clicked, dict) and clicked.get('span_id')):
        return
    ts = clicked.get('ts')
    if ts is None or ts == st.session_state.get('_last_activity_click_ts'):
        return
    st.session_state._last_activity_click_ts = ts
    sid = str(clicked['span_id'])
    if sid not in sel_ids:
        return
    st.session_state.selected_span = sid
    if st.query_params.get('focus') != sid:
        st.query_params['focus'] = sid
    if collapse and sid in _collapsed_groups(all_spans, expand=expand):
        st.session_state.activity_expand = set(
            st.session_state.get('activity_expand') or ()
        ) | {sid}
    # Restart from the top so both the component focus argument and the detail
    # column read the same selected span. The timestamp guard above makes the
    # component's retained v1 value harmless on the following run.
    st.rerun()


def _render_activity_center(all_spans, *, focus=None, n_traces=1) -> None:
    """The merged left+centre column: the whole run as one activity diagram."""
    st.markdown('#### \U0001f9ed Activity diagram')
    st.session_state.setdefault('activity_expand', set())

    too_many = len(all_spans) > _ACTIVITY_MAX_NODES
    collapse = not bool(st.session_state.get('activity_expand_all', False))
    expand = set(st.session_state.activity_expand) if collapse else set()

    n_nodes = len(all_spans)
    n_groups = 0
    if all_spans and not too_many:
        plan, _roots = _activity_plan(all_spans, collapse=collapse, expand=expand)
        n_nodes = len(plan.nodes)
        n_groups = len(plan.aggregated)

    if too_many:
        st.caption(
            f'共 {len(all_spans)} 个 span，超过 {_ACTIVITY_MAX_NODES} 的渲染上限'
            '（避免浏览器卡死），无法绘制。'
        )
    else:
        fold_stat = f' · **{n_groups}** 组已折叠' if n_groups else ''
        st.caption(
            f'**{len(all_spans)}** spans · **{n_traces}** traces · '
            f'**{n_nodes}** 个可视节点{fold_stat}'
        )

    col_a, col_b = st.columns([3, 2], gap='small')
    with col_a:
        st.toggle('展开全部 span', key='activity_expand_all')
    with col_b:
        if st.session_state.activity_expand:
            n_open = len(st.session_state.activity_expand)
            if st.button(f'收起 {n_open} 个展开组'):
                st.session_state.activity_expand = set()
                st.rerun()

    _render_activity_component(all_spans, focus=focus, collapse=collapse,
                              expand=expand)


__all__ = [
    '_build_activity_diagram', '_activity_label', '_kind_class',
    '_render_activity_component', '_render_activity_center',
    '_all_sequential', 'sanitize_label', '_SYNTHETIC_ID_PREFIXES',
    '_ACTIVITY_MAX_NODES', '_START_ID', '_END_ID',
    '_VROOT_ID', '_ROOT_JOIN_ID', '_INFO_ID',
    '_activity_plan', '_plan_layout', '_shape_signatures', '_sequential_nodes',
    '_collapsed_groups', '_flow_layout', '_time_phases', '_rendered_phases',
    '_AGG_STYLE', '_AGG_MIN_GROUP',
]
