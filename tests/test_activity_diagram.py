# -*- coding: utf-8 -*-
"""Tests for the layout-"B" activity diagram (``viewer_app/render_activity.py``).

The Streamlit page cannot be driven head-less here, so these tests pin the
*generated Mermaid source*, which is where every real contract lives:

* the node-id protocol with ``flowchart_component/index.html`` (a click must
  round-trip to a real span id, and no synthetic node may look like a span);
* the removal of the old 80-node cap (``render_flowchart._MERMAID_MAX_NODES``);
* the tree topology: the root span is the top of the tree, chronological
  phases are chained, and only overlapping siblings get fork/join bars;
* the error/focus emphasis is emitted as ``style`` and never re-shapes the
  diagram.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from viewer_app import render_activity as ra

TID = "t" * 32


def _span(sid, *, parent=None, name="step", kind="CHAIN",
          start=0, end=1_000_000, status="OK", model=None, trace=TID):
    attrs = {"openinference.span.kind": kind}
    if model:
        attrs["llm.model_name"] = model
    return {
        "trace_id": trace,
        "span_id": sid,
        "parent_span_id": parent,
        "name": name,
        "start_time": start,
        "end_time": end,
        "status": status,
        "kind": kind,
        "attributes": attrs,
    }


def _node_ids(src: str) -> set:
    """Every id that is *defined* as a node (``id(shape...)``)."""
    return set(re.findall(r"^\s{4}([A-Za-z_][A-Za-z0-9_]*)\s*[\(\[\{]", src, re.M))


def _edges(src: str) -> set:
    out = set()
    for line in src.splitlines():
        line = line.strip()
        if "-->" in line and not line.startswith("linkStyle"):
            parts = [p.strip() for p in line.split("-->")]
            for a, b in zip(parts, parts[1:]):
                out.add((a, b))
    return out


# ---------------------------------------------------------------------------
# capsule contract: __all__ / module shape
# ---------------------------------------------------------------------------

def test_all_is_strings():
    assert ra.__all__
    for entry in ra.__all__:
        assert isinstance(entry, str), f"{entry!r} is not a str"


def test_init_module_uses_the_activity_view_not_the_old_three_column_body():
    """Layout "B" regression: the merged activity diagram must own the body."""
    from pathlib import Path

    src = (Path(ra.__file__).resolve().parent / "__init__.py").read_text(encoding="utf-8")
    assert "_render_activity_center" in src
    assert "_render_activity_mode" in src
    assert "_render_flowchart_mode" not in src
    assert "_render_trace_cards_list" not in src
    assert "_MERMAID_MAX_NODES" not in src


# ---------------------------------------------------------------------------
# node ids: the click-back protocol
# ---------------------------------------------------------------------------

def test_span_node_id_round_trips_through_the_frontend_regex():
    """index.html recovers the span id with /(n_[A-Za-z0-9_]+)/ + '_'->'-'."""
    sid = "0a1b2c3d-4e5f-6789-abcd-ef0123456789"
    src = ra._build_activity_diagram([_span(sid)])
    assert f"n_0a1b2c3d_4e5f_6789_abcd_ef0123456789" in src

    frontend = re.search(r"n_[A-Za-z0-9_]+", src).group(0)
    assert frontend.replace("n_", "").replace("_", "-") == sid


def test_synthetic_node_ids_can_never_be_clicked_as_a_span():
    """A synthetic id containing 'n_' would post a bogus span_id on click."""
    for prefix in ra._SYNTHETIC_ID_PREFIXES:
        assert "n_" not in prefix, f"synthetic id {prefix!r} matches /n_[A-Za-z0-9_]+/"

    # ...and the invariant holds for every id the builder actually emits.
    spans = [_span("a" * 16)] + [
        _span(f"b{i:015d}", parent="a" * 16, start=i * 2, end=i * 2 + 3)
        for i in range(4)
    ]
    src = ra._build_activity_diagram(spans)
    for nid in _node_ids(src):
        if not nid.startswith("n_"):
            assert "n_" not in nid, f"{nid!r} would be mistaken for a span node"


# ---------------------------------------------------------------------------
# topology
# ---------------------------------------------------------------------------

def test_root_span_is_the_top_of_the_tree():
    spans = [
        _span("root" + "0" * 12, name="claim_verification", kind="AGENT"),
        _span("child" + "0" * 11, parent="root" + "0" * 12),
    ]
    src = ra._build_activity_diagram(spans)
    assert f'{ra._START_ID} --> n_root{"0" * 12}' in src
    # single root -> no artificial root node on top of it
    assert ra._VROOT_ID not in _node_ids(src)
    # the root activity is drawn as a stadium (container), children as activities
    assert re.search(r'n_root0{12}\(\["', src)


def test_multiple_roots_get_one_virtual_root():
    spans = [
        _span("a" * 16, name="run-a"),
        _span("b" * 16, name="run-b"),
    ]
    src = ra._build_activity_diagram(spans)
    assert ra._VROOT_ID in _node_ids(src)
    assert f"{ra._START_ID} --> {ra._VROOT_ID}" in src
    assert f"{ra._VROOT_ID} --> n_{'a' * 16}" in src
    assert f"{ra._VROOT_ID} --> n_{'b' * 16}" in src
    assert f"n_{'a' * 16} --> {ra._ROOT_JOIN_ID}" in src
    assert f"n_{'b' * 16} --> {ra._ROOT_JOIN_ID}" in src
    assert f"{ra._ROOT_JOIN_ID} --> {ra._END_ID}" in src


def test_every_span_appears_and_the_80_node_cap_is_gone():
    """render_flowchart refuses to draw >80 nodes; this view must not."""
    root = "r" * 16
    spans = [_span(root, kind="AGENT", end=10_000_000)]
    for i in range(140):
        spans.append(_span(f"s{i:015d}", parent=root, start=i * 1000, end=i * 1000 + 500))

    src = ra._build_activity_diagram(spans)
    assert len(spans) > 80
    for s in spans:
        assert f"n_{s['span_id'].replace('-', '_')}" in src
    assert "节点数过多" not in src
    assert "请切回 列表 模式查看" not in src


def test_sequential_siblings_form_a_sequence_chain():
    root = "r" * 16
    a, b, c = "a" * 16, "b" * 16, "c" * 16
    spans = [
        _span(root, kind="AGENT", start=0, end=30),
        _span(a, parent=root, start=0, end=10),
        _span(b, parent=root, start=10, end=20),
        _span(c, parent=root, start=20, end=30),
    ]
    edges = _edges(ra._build_activity_diagram(spans))
    assert (f"n_{root}", f"n_{a}") in edges
    assert (f"n_{a}", f"n_{b}") in edges
    assert (f"n_{b}", f"n_{c}") in edges
    assert "adfork1" not in {n for e in edges for n in e}


def test_overlapping_siblings_get_fork_and_join_bars():
    root = "r" * 16
    a, b = "a" * 16, "b" * 16
    spans = [
        _span(root, kind="AGENT", start=0, end=100),
        _span(a, parent=root, start=10, end=90),   # overlaps b -> parallel fan-out
        _span(b, parent=root, start=20, end=80),
    ]
    src = ra._build_activity_diagram(spans)
    edges = _edges(src)
    assert (f"n_{root}", "adfork1") in edges
    assert ("adfork1", f"n_{a}") in edges
    assert ("adfork1", f"n_{b}") in edges
    assert (f"n_{a}", "adjoin1") in edges
    assert (f"n_{b}", "adjoin1") in edges
    assert "adjoin1" in _node_ids(src)


def test_sequential_parallel_sequential_phases_form_a_vertical_chain():
    root, before, left, right, after = (ch * 16 for ch in "rablc")
    spans = [
        _span(root, kind="AGENT", start=0, end=100),
        _span(before, parent=root, name="before", start=0, end=10),
        _span(left, parent=root, name="left", start=10, end=30),
        _span(right, parent=root, name="right", start=15, end=25),
        _span(after, parent=root, name="after", start=30, end=40),
    ]
    edges = _edges(ra._build_activity_diagram(spans))
    assert (f"n_{root}", f"n_{before}") in edges
    assert (f"n_{before}", "adfork1") in edges
    assert ("adfork1", f"n_{left}") in edges
    assert ("adfork1", f"n_{right}") in edges
    assert (f"n_{left}", "adjoin1") in edges
    assert (f"n_{right}", "adjoin1") in edges
    assert ("adjoin1", f"n_{after}") in edges


def test_chain_overlap_stays_in_one_maximal_phase():
    """A overlaps B and B overlaps C, so no false serial boundary is added."""
    root, a, b, c = (ch * 16 for ch in "rabc")
    spans = [
        _span(root, kind="AGENT", start=0, end=100),
        _span(a, parent=root, name="a", start=0, end=10),
        _span(b, parent=root, name="b", start=5, end=15),
        _span(c, parent=root, name="c", start=14, end=20),
    ]
    edges = _edges(ra._build_activity_diagram(spans))
    for sid in (a, b, c):
        assert ("adfork1", f"n_{sid}") in edges
        assert (f"n_{sid}", "adjoin1") in edges


def test_touching_intervals_are_sequential_not_parallel():
    root, a, b = (ch * 16 for ch in "rab")
    phases = ra._time_phases([
        _span(a, parent=root, start=0, end=10),
        _span(b, parent=root, start=10, end=20),
    ])
    assert [[s["span_id"] for s in phase] for phase in phases] == [[a], [b]]


def test_sequential_siblings_connect_subtree_exit_to_next_entry():
    """A nested branch must finish before the next sibling starts."""
    root, a, a_leaf, b = (ch * 16 for ch in "ralb")
    spans = [
        _span(root, kind="AGENT", start=0, end=100),
        _span(a, parent=root, name="first", start=0, end=40),
        _span(a_leaf, parent=a, name="first-leaf", start=10, end=30),
        _span(b, parent=root, name="second", start=50, end=90),
    ]
    edges = _edges(ra._build_activity_diagram(spans))
    assert (f"n_{root}", f"n_{a}") in edges
    assert (f"n_{a}", f"n_{a_leaf}") in edges
    assert (f"n_{a_leaf}", f"n_{b}") in edges
    assert (f"n_{a}", f"n_{b}") not in edges


def test_parallel_siblings_join_from_each_subtree_exit():
    root, a, a_leaf, b, b_leaf = (ch * 16 for ch in "ralbc")
    spans = [
        _span(root, kind="AGENT", start=0, end=100),
        _span(a, parent=root, name="left", start=0, end=80),
        _span(a_leaf, parent=a, name="left-leaf", start=10, end=70),
        _span(b, parent=root, name="right", start=20, end=90),
        _span(b_leaf, parent=b, name="right-leaf", start=30, end=85),
    ]
    edges = _edges(ra._build_activity_diagram(spans))
    assert (f"n_{a_leaf}", "adjoin1") in edges
    assert (f"n_{b_leaf}", "adjoin1") in edges
    assert (f"n_{a}", "adjoin1") not in edges
    assert (f"n_{b}", "adjoin1") not in edges
    assert ("adjoin1", ra._END_ID) in edges


def test_nested_parallel_join_becomes_outer_branch_exit():
    root, a, b, c, d = (ch * 16 for ch in "rabcd")
    spans = [
        _span(root, kind="AGENT", start=0, end=200),
        _span(a, parent=root, name="outer-left", start=0, end=160),
        _span(b, parent=root, name="outer-right", start=20, end=180),
        _span(c, parent=a, name="inner-one", start=30, end=120),
        _span(d, parent=a, name="inner-two", start=40, end=130),
    ]
    edges = _edges(ra._build_activity_diagram(spans))
    # Fork numbering follows rendered-node order: root is outer fork 1 and a
    # owns inner fork 2. The inner join is therefore the exit of branch a.
    assert ("adjoin2", "adjoin1") in edges
    assert (f"n_{a}", "adjoin1") not in edges


def test_last_activity_flows_into_the_final_node():
    spans = [
        _span("r" * 16, kind="AGENT", start=0, end=30),
        _span("l" * 16, parent="r" * 16, start=20, end=30),
    ]
    src = ra._build_activity_diagram(spans)
    assert f'n_{"l" * 16} --> {ra._END_ID}' in src


def test_cyclic_parent_links_still_render_every_span():
    """A malformed file can contain a parent cycle no root reaches."""
    a, b = "a" * 16, "b" * 16
    spans = [
        _span(a, parent=b),
        _span(b, parent=a),
    ]
    src = ra._build_activity_diagram(spans)
    ids = _node_ids(src)
    assert f"n_{a}" in ids and f"n_{b}" in ids


def test_deep_chain_has_exactly_one_root_and_no_virtual_root():
    """Regression: the tree walk must expand grandchildren.

    An earlier version marked a child as visited when it was *enqueued*, so the
    dequeue guard skipped it and the walk never went past depth two - every
    grandchild was mis-reported as a root and the diagram sprouted a spurious
    "◆ 全部 traces · n" node (131 of them on the real trace).
    """
    ids = ["r" * 16, "a" * 16, "b" * 16, "c" * 16, "d" * 16]
    spans = [_span(ids[0], kind="AGENT", start=0, end=100)]
    for i, (sid, parent) in enumerate(zip(ids[1:], ids), start=1):
        spans.append(_span(sid, parent=parent, start=i, end=i + 1))

    children, roots = ra._build_forest(spans)
    assert [r["span_id"] for r in roots] == [ids[0]]

    src = ra._build_activity_diagram(spans)
    assert ra._VROOT_ID not in _node_ids(src)
    edges = _edges(src)
    for parent, child in zip(ids, ids[1:]):
        assert (f"n_{parent}", f"n_{child}") in edges


def test_wide_and_deep_tree_keeps_one_root():
    """A realistic orchestrator shape: one root, fan-out, and nested children."""
    root = "r" * 16
    spans = [_span(root, kind="AGENT", start=0, end=10_000)]
    step = 0
    for branch in range(6):                      # sequential branches
        bid = f"b{branch:015d}"
        spans.append(_span(bid, parent=root, start=step, end=step + 100))
        for leaf in range(4):                    # overlapping leaves -> fork/join
            # Distinct names on purpose: four *identical* parallel leaves are
            # folded into one "x4" node by the collapse pass (see the folding
            # tests below), which would leave no fork/join to assert here.
            spans.append(_span(f"l{branch:07d}{leaf:08d}", parent=bid,
                               name=f"leaf-{leaf}",
                               start=step + leaf, end=step + leaf + 50))
        step += 100

    children, roots = ra._build_forest(spans)
    assert len(roots) == 1, [r["name"] for r in roots]
    assert len(children) == 7                    # root + 6 branches
    assert sum(len(v) for v in children.values()) == len(spans) - 1

    src = ra._build_activity_diagram(spans)
    assert ra._VROOT_ID not in _node_ids(src)
    assert "adfork1" in _node_ids(src)
    assert f"{ra._START_ID} --> n_{root}" in src


def test_every_edge_endpoint_is_a_defined_node():
    root = "r" * 16
    spans = [_span(root, kind="AGENT", start=0, end=100)]
    spans += [_span(f"c{i:015d}", parent=root, start=i, end=i + 1) for i in range(5)]
    spans += [_span(f"d{i:015d}", parent=f"c{i:015d}", start=i, end=i + 1) for i in range(5)]
    src = ra._build_activity_diagram(spans)
    ids = _node_ids(src)
    for a, b in _edges(src):
        assert a in ids, f"edge source {a} is not defined"
        assert b in ids, f"edge target {b} is not defined"


def test_generated_control_flow_is_acyclic():
    root = "r" * 16
    spans = [_span(root, kind="AGENT", start=0, end=1_000)]
    for i in range(4):
        branch = f"b{i:015d}"
        spans.append(_span(branch, parent=root, name=f"branch-{i}",
                           start=i * 10, end=700 + i * 10))
        for j in range(2):
            spans.append(_span(f"l{i:07d}{j:08d}", parent=branch,
                               name=f"leaf-{i}-{j}", start=100 + j,
                               end=300 + j))
    src = ra._build_activity_diagram(spans)
    graph = {}
    for start, end in _edges(src):
        graph.setdefault(start, []).append(end)

    visiting, visited = set(), set()

    def visit(node):
        assert node not in visiting, f"cycle reaches {node}"
        if node in visited:
            return
        visiting.add(node)
        for child in graph.get(node, ()):
            visit(child)
        visiting.remove(node)
        visited.add(node)

    visit(ra._START_ID)


# ---------------------------------------------------------------------------
# labels / emphasis
# ---------------------------------------------------------------------------

def test_sanitizer_keeps_the_label_inside_its_quotes():
    assert '"' not in ra.sanitize_label('a"b')
    assert "\\" not in ra.sanitize_label("a\\b")
    assert ra.sanitize_label("a\nb") == "a b"
    # html-significant characters are escaped, not dropped
    assert ra.sanitize_label("a & b <c>") == "a &amp; b &lt;c&gt;"


def test_label_carries_icon_name_kind_and_duration():
    span = _span("a" * 16, name="verify_claim", kind="TOOL",
                 start=0, end=1_500_000_000)
    label = ra._activity_label(span)
    assert "verify_claim" in label
    assert "TOOL" in label
    assert "1.50s" in label
    assert "<br/>" in label
    assert "class=activity-name" in label
    assert "class=activity-meta" in label


def test_activity_label_keeps_the_complete_name_and_tooltip():
    name = "long activity name " * 12
    label = ra._activity_label(_span("a" * 16, name=name))
    assert name.strip() in label
    assert "…" not in label
    assert "title='" in label


def test_activity_label_escapes_apostrophes_in_its_tooltip():
    label = ra._activity_label(_span("a" * 16, name="agent's complete step"))
    assert "title='agent&#39;s complete step'" in label


def test_kind_class_falls_back_to_unknown():
    assert ra._kind_class(_span("a" * 16, kind="LLM")) == "llm"
    assert ra._kind_class(_span("a" * 16, kind="RETRIEVER")) == "retriever"
    assert ra._kind_class(_span("a" * 16, kind="NOT_A_KIND")) == "unknown"
    assert ra._kind_class({"span_id": "x", "attributes": {}}) == "unknown"


def test_error_and_focus_are_styles_not_topology_changes():
    root = "r" * 16
    spans = [
        _span(root, kind="AGENT", start=0, end=100),
        _span("e" * 16, parent=root, start=10, end=20, status="ERROR"),
    ]
    plain = ra._build_activity_diagram(spans)
    focused = ra._build_activity_diagram(spans, focus="e" * 16)

    assert _edges(plain) == _edges(focused), "focus must not re-shape the diagram"
    assert f"style n_{'e' * 16} stroke:#ef4444,stroke-width:2px" in plain
    assert f"style n_{'e' * 16} stroke:#facc15,stroke-width:3px" in focused
    # focus wins over the error stroke (the user just clicked the node)
    assert "stroke:#ef4444" not in focused


# ---------------------------------------------------------------------------
# degenerate inputs
# ---------------------------------------------------------------------------

def test_empty_input_is_still_valid_mermaid():
    for spans in ([], None):
        src = ra._build_activity_diagram(spans)
        assert src.splitlines()[1] == "flowchart TD"
        assert f"{ra._START_ID} --> {ra._END_ID}" in src


def test_over_limit_shows_a_notice_instead_of_hanging_the_browser():
    spans = [_span(f"s{i:015d}") for i in range(ra._ACTIVITY_MAX_NODES + 1)]
    src = ra._build_activity_diagram(spans)
    assert ra._INFO_ID in _node_ids(src)
    assert f"n_{spans[0]['span_id']}" not in src
    assert f"{ra._START_ID} --> {ra._INFO_ID} --> {ra._END_ID}" in src


def test_diagram_starts_with_the_init_directive_then_the_graph_type():
    src = ra._build_activity_diagram([_span("a" * 16)])
    lines = src.splitlines()
    assert lines[0].startswith("%%{init:")
    assert '"useMaxWidth": false' in lines[0]
    assert lines[1] == "flowchart TD"


@pytest.mark.parametrize("n,expected", [(0, False), (1, False), (2, True), (5, True)])
def test_virtual_root_appears_only_for_several_roots(n, expected):
    spans = [_span(f"{i:016d}", name=f"run-{i}") for i in range(n)]
    src = ra._build_activity_diagram(spans)
    assert (ra._VROOT_ID in _node_ids(src)) is expected


# ---------------------------------------------------------------------------
# repeated-subtree folding (v1.1.2)
#
# An agent loop repeats the same subtree once per round, so the literal
# one-node-per-span graph is mostly N copies of a 4-node pattern laid out side by
# side.  These tests pin the invariant that makes folding safe -- the sum of the
# drawn multiplicities still equals the number of spans -- and the two guards
# that keep it from eating structure the reader wants.
# ---------------------------------------------------------------------------

def _fan_children(root, n, *, name="step", dur=50, gap=1):
    """``n`` *identical* overlapping children of ``root``: a parallel fan-out."""
    return [
        _span(f"{i:016d}", parent=root, name=name, start=i * gap, end=i * gap + dur)
        for i in range(n)
    ]


def test_folding_helpers_are_exported():
    for name in ("_activity_plan", "_plan_layout", "_shape_signatures",
                 "_sequential_nodes", "_time_phases", "_rendered_phases",
                 "_collapsed_groups", "_AGG_STYLE", "_AGG_MIN_GROUP"):
        assert name in ra.__all__, name


def test_identical_parallel_siblings_fold_into_one_xN_node():
    root = "r" * 16
    spans = [_span(root, kind="AGENT", end=10_000)] + _fan_children(root, 6)
    src = ra._build_activity_diagram(spans)
    plan, _roots = ra._activity_plan(spans)

    assert sum(node.mult for node in plan.nodes) == len(spans)
    assert len(plan.aggregated) == 1
    assert "\u00d76" in src, "the multiplicity must be in the label"
    assert "\u00d76 并发" in src
    # drawn as a UML "predefined process" (double border) rather than a plain
    # activity: the node stands for six activities, not one
    assert re.search(r"^    n_[A-Za-z0-9_]+\[\[", src, re.M)
    assert len([n for n in _node_ids(src) if n.startswith("n_")]) == 2  # root + group


def test_folding_accounts_for_every_span_exactly_once():
    """The invariant that makes folding safe: multiplicities sum to span count."""
    root = "r" * 16
    spans = [_span(root, kind="AGENT", end=100_000)]
    for i in range(12):                        # 12 identical parallel branches
        bid = f"b{i:015d}"
        spans.append(_span(bid, parent=root, name="branch", start=i, end=i + 500))
        for j in range(3):                     # each with 3 identical children
            spans.append(_span(f"l{i:07d}{j:08d}", parent=bid, name="leaf",
                               start=i + j, end=i + j + 100))
    plan, _roots = ra._activity_plan(spans)

    assert len(spans) == 1 + 12 + 36
    assert sum(node.mult for node in plan.nodes) == len(spans)


def test_multiplicity_is_carried_down_the_folded_subtree():
    root = "r" * 16
    spans = [_span(root, kind="AGENT", end=10_000)]
    for i in range(5):
        spans.append(_span(f"{i:016d}", parent=root, name="round",
                           start=i, end=i + 100))
        spans.append(_span(f"{i + 100:016d}", parent=f"{i:016d}", name="llm",
                           kind="LLM", start=i, end=i + 50))

    src = ra._build_activity_diagram(spans)
    # both the folded group AND its single child represent five spans each
    assert src.count("\u00d75") >= 2


def test_identical_sequential_siblings_keep_their_chain():
    """A loop of identical steps is already one column; folding it would hide order."""
    root = "r" * 16
    spans = [_span(root, kind="AGENT", start=0, end=30)]
    for i in range(4):
        spans.append(_span(f"{i:016d}", parent=root, name="round",
                           start=i * 10, end=i * 10 + 5))

    src = ra._build_activity_diagram(spans)
    edges = _edges(src)
    ids = [f"n_{i:016d}" for i in range(4)]
    assert "\u00d7" not in src
    for a, b in zip([f"n_{root}"] + ids, ids):
        assert (a, b) in edges


def test_identical_parallel_spans_never_fold_across_time_phases():
    root = "r" * 16
    spans = [_span(root, kind="AGENT", start=0, end=100)]
    for offset in (0, 20):
        for i in range(3):
            sid = f"{offset + i:016d}"
            spans.append(_span(sid, parent=root, name="same-shape",
                               start=offset + i, end=offset + 10))

    plan, _roots = ra._activity_plan(spans)
    root_nid = f"n_{root}"
    phases = ra._rendered_phases(plan.kids[root_nid])
    assert len(plan.aggregated) == 2
    assert len(phases) == 2
    assert [[node.mult for _nid, node in phase] for phase in phases] == [[3], [3]]
    assert sum(node.mult for node in plan.nodes) == len(spans)

    edges = _edges(ra._build_activity_diagram(spans))
    first, second = (phase[0][0] for phase in phases)
    assert (root_nid, first) in edges
    assert (first, second) in edges


def test_two_identical_siblings_stay_split():
    """Below _AGG_MIN_GROUP the two branches stay visible."""
    root = "r" * 16
    spans = [
        _span(root, kind="AGENT", start=0, end=100),
        _span("a" * 16, parent=root, start=10, end=90),
        _span("b" * 16, parent=root, start=20, end=80),
    ]
    src = ra._build_activity_diagram(spans)
    assert f"n_{'a' * 16}" in _node_ids(src)
    assert f"n_{'b' * 16}" in _node_ids(src)
    assert "\u00d7" not in src
    assert ra._AGG_MIN_GROUP == 3


def test_expand_unfolds_only_the_named_group():
    root = "r" * 16
    spans = [_span(root, kind="AGENT", end=10_000)] + _fan_children(root, 6)
    plan, _roots = ra._activity_plan(spans)
    rep = next(iter(plan.aggregated))

    src = ra._build_activity_diagram(spans, collapse=True, expand={rep})
    ids = {n for n in _node_ids(src) if n.startswith("n_")}
    assert len(ids) == 1 + 6, "the unfolded group must draw all six children"
    assert "\u00d7" not in src


def test_collapse_false_draws_one_node_per_span():
    root = "r" * 16
    spans = [_span(root, kind="AGENT", end=10_000)] + _fan_children(root, 6)
    src = ra._build_activity_diagram(spans, collapse=False)
    for s in spans:
        assert f"n_{s['span_id'].replace('-', '_')}" in src
    assert "\u00d7" not in src


def test_collapsed_groups_are_real_span_ids_the_frontend_can_post_back():
    """Clicking a xN node posts a span id, so it has to BE one."""
    root = "r" * 16
    spans = [_span(root, kind="AGENT", end=10_000)] + _fan_children(root, 6)
    aggs = ra._collapsed_groups(spans)
    assert aggs
    known = {s["span_id"] for s in spans}
    for sid in aggs:
        assert sid in known
        assert f"n_{sid.replace('-', '_')}" in _node_ids(
            ra._build_activity_diagram(spans))


def test_final_node_follows_the_last_leaf_not_the_root():
    """The root's end_time covers the whole run, so it must not own 结束."""
    root = "r" * 16
    spans = [
        _span(root, kind="AGENT", start=0, end=100),
        _span("a" * 16, parent=root, start=10, end=20),
        _span("b" * 16, parent=root, start=30, end=95),
    ]
    src = ra._build_activity_diagram(spans)
    assert f'n_{"b" * 16} --> {ra._END_ID}' in src
    assert f"n_{root} --> {ra._END_ID}" not in src


def test_folded_subtree_finishes_at_its_rendered_leaf():
    root = "r" * 16
    spans = [_span(root, kind="AGENT", start=0, end=1_000)]
    for i in range(3):
        branch = f"b{i:015d}"
        spans.append(_span(branch, parent=root, name="round",
                           start=i, end=900 + i))
        spans.append(_span(f"l{i:015d}", parent=branch, name="result",
                           start=100 + i, end=800 + i))
    plan, _roots = ra._activity_plan(spans)
    representative = next(iter(plan.aggregated))
    rendered_leaf = next(
        node.nid for node in plan.nodes
        if node.span.get("parent_span_id") == representative
    )
    edges = _edges(ra._build_activity_diagram(spans))
    assert (rendered_leaf, ra._END_ID) in edges
    assert (f"n_{representative}", ra._END_ID) not in edges


def test_real_157_span_trace_keeps_its_five_time_phases():
    trace_path = Path("D:/agent/complex-agent-langchain/latest_traces.jsonl")
    if not trace_path.is_file():
        pytest.skip("local 157-span validation trace is unavailable")

    from viewer_app.data import load_traces

    traces, dropped = load_traces(str(trace_path))
    spans = [span for trace in traces.values() for span in trace]
    if len(spans) != 157:
        pytest.skip("local trace has been replaced since this regression was captured")

    plan, roots = ra._activity_plan(spans)
    root_nid = f"n_{roots[0]['span_id'].replace('-', '_')}"
    phases = ra._rendered_phases(plan.kids[root_nid])

    assert dropped == 0
    assert len(plan.nodes) == 25
    assert len(plan.aggregated) == 2
    assert sum(node.mult for node in plan.nodes) == 157
    assert [[node.mult for _nid, node in phase] for phase in phases] == [
        [1], [4], [25, 1], [1], [1],
    ]
    assert phases[-1][0][1].span["name"] == "persist_report"

    edges = _edges(ra._build_activity_diagram(spans))
    flows, _parallel = ra._flow_layout(plan)
    before_persist = phases[-2][0][0]
    persist = phases[-1][0][0]
    assert (flows[before_persist].exits[0], persist) in edges
    assert (persist, ra._END_ID) in edges
