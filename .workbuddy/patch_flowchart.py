# -*- coding: utf-8 -*-
"""Add flowchart mode (Mermaid) + view-mode switcher to viewer.py.

Three insertions:
  A) Helper functions (_build_mermaid, _render_flowchart_mode, _render_mermaid_html)
     inserted right BEFORE the "# LEFT tree renderer" header (line ~1028).
  B) View-mode radio inserted right AFTER the hdr_r block (around line 798-800).
  C) Wrap the 3-column body in `if view_mode == "列表"` and add `else` branch.
"""
import sys
sys.stdout.reconfigure(encoding="utf-8")

p = r"D:\my-projects\agent-monitor\viewer.py"
src = open(p, encoding="utf-8").read()

# ============================================================
# INSERTION A: helper functions before "# LEFT tree renderer"
# ============================================================
insert_A_marker = '# LEFT tree renderer'
assert insert_A_marker in src, "marker A not found"

helpers = r'''# ---------------------------------------------------------------------------
# Flowchart mode (Mermaid) + click-to-zoom
# ---------------------------------------------------------------------------
_MERMAID_MAX_NODES = 80  # 当节点数超过此值时折叠为聚合节点
_NODE_LABEL_MAX_CHARS = 60


def _mermaid_safe_id(sid: str) -> str:
    """Mermaid node IDs can't contain hyphens; normalize."""
    return "n_" + sid.replace("-", "_")


def _mermaid_label(span: dict) -> str:
    """Build a 2-line Mermaid label: <icon> <name> on top, kind + duration below."""
    attrs = span.get("attributes") or {}
    kind = span_kind(attrs)
    info = SPAN_KINDS.get(kind, SPAN_KINDS["UNKNOWN"])
    icon = info[0]
    name = _span_display_name(span)
    # Sanitize: strip Mermaid-meaningful punctuation, replace with spaces
    name = re.sub(r'[\[\](){}<>|`]', " ", name).strip()
    if len(name) > _NODE_LABEL_MAX_CHARS:
        name = name[:_NODE_LABEL_MAX_CHARS - 1] + "..."
    start_ns = int(span.get("start_time", 0))
    end_ns = int(span.get("end_time", 0))
    dur_ms = (end_ns - start_ns) / 1_000_000
    dur = _format_duration_ms(dur_ms)
    # <br/> works inside double-quoted Mermaid labels
    return f"<b>{icon} {name}</b><br/><small>{kind} &middot; {dur}</small>"


def _build_mermaid(spans: list, *, focus: str | None = None, hops: int = 2) -> str:
    """Build a Mermaid `flowchart TB` source for the given spans.

    When `focus` is set, only render the focus node plus its ancestors and
    descendants within `hops` edges; everything else is hidden.  This produces
    the "zoom-in" subgraph shown on the left side of the focused view.
    """
    if not spans:
        return "flowchart TB\n    empty[\u00a0\uff08\u65e0 span\uff09\u00a0]"

    spans_by_id = {s["span_id"]: s for s in spans}

    # Compute the visible set (focus mode: 2-hop neighborhood)
    if focus and focus in spans_by_id:
        visible: set[str] = {focus}
        up, down = {focus}, {focus}
        for _ in range(hops):
            new_up: set[str] = set()
            for sid in up:
                pid = spans_by_id.get(sid, {}).get("parent_span_id")
                if pid and pid in spans_by_id and pid not in visible:
                    new_up.add(pid)
            visible |= new_up
            up = new_up
            new_down: set[str] = set()
            for sid in down:
                for s in spans:
                    if s.get("parent_span_id") == sid and s["span_id"] not in visible:
                        new_down.add(s["span_id"])
            visible |= new_down
            down = new_down
    else:
        visible = {s["span_id"] for s in spans}

    visible_spans = [s for s in spans if s["span_id"] in visible]

    # Fold to a single placeholder when there are too many nodes (only without focus)
    if len(visible_spans) > _MERMAID_MAX_NODES and not focus:
        return (
            "flowchart TB\n"
            "    root[<\u00a0\u5171 " + str(len(spans)) + " \u4e2a span\u00a0<br/>"
            "<small>\u8282\u70b9\u6570\u8fc7\u591a\uff0c\u8bf7\u5207\u56de \u5217\u8868 \u6a21\u5f0f\u67e5\u770b</small>]\n"
            "    classDef root fill:#4b5563,color:#fff,stroke:#1f2937;\n"
            "    class root root;"
        )

    # ---- Mermaid source ---------------------------------------------------
    out: list[str] = ["flowchart TB"]
    # Class definitions for 11 kinds + error / focus overlays
    out.append("    classDef llm       fill:#1d4ed8,color:#fff,stroke:#1e3a8a,stroke-width:1px;")
    out.append("    classDef chain     fill:#065f46,color:#fff,stroke:#064e3b,stroke-width:1px;")
    out.append("    classDef tool      fill:#b45309,color:#fff,stroke:#7c2d12,stroke-width:1px;")
    out.append("    classDef agent     fill:#a16207,color:#fff,stroke:#713f12,stroke-width:1px;")
    out.append("    classDef retriever fill:#7e22ce,color:#fff,stroke:#581c87,stroke-width:1px;")
    out.append("    classDef embedding fill:#0e7490,color:#fff,stroke:#164e63,stroke-width:1px;")
    out.append("    classDef reranker  fill:#6d28d9,color:#fff,stroke:#4c1d95,stroke-width:1px;")
    out.append("    classDef prompt    fill:#3f6212,color:#fff,stroke:#365314,stroke-width:1px;")
    out.append("    classDef parser    fill:#4b5563,color:#fff,stroke:#1f2937,stroke-width:1px;")
    out.append("    classDef evaluator fill:#a8a29e,color:#1c1917,stroke:#78716c,stroke-width:1px;")
    out.append("    classDef guardrail fill:#b91c1c,color:#fff,stroke:#7f1d1d,stroke-width:1px;")
    out.append("    classDef unknown   fill:#6b7280,color:#fff,stroke:#374151,stroke-width:1px;")
    out.append("    classDef error     stroke:#ef4444,stroke-width:2px,color:#fff;")
    out.append("    classDef focus     stroke:#facc15,stroke-width:3px;")
    out.append("    linkStyle default stroke:#64748b,stroke-width:1px;")

    # Nodes
    for span in visible_spans:
        sid = span["span_id"]
        nid = _mermaid_safe_id(sid)
        kind = span_kind(span.get("attributes") or {})
        kind_class = kind.lower() if kind in SPAN_KINDS else "unknown"
        cls = [kind_class]
        if str(span.get("status", "")).upper() == "ERROR":
            cls.append("error")
        if sid == focus:
            cls.append("focus")
        out.append(f'    {nid}["{_mermaid_label(span)}"]')
        out.append(f"    class {nid} {','.join(cls)};")

    # Edges
    for span in visible_spans:
        pid = span.get("parent_span_id")
        if pid and pid in visible:
            out.append(f"    {_mermaid_safe_id(pid)} --> {_mermaid_safe_id(span['span_id'])}")

    return "\n".join(out)


def _render_mermaid_html(src: str, *, height: int = 620, key_prefix: str = "m") -> None:
    """Render Mermaid inside an iframe; clicking a node updates ?focus=<span_id>.

    We escape the Mermaid source so backticks / dollar-signs inside label
    content don't break the surrounding JS template literal.
    """
    # Escape for inclusion inside a JS template literal ``...``
    js_src = (
        src.replace("\\", "\\\\")
           .replace("`", "\\`")
           .replace("${", "\\${")
    )
    html_doc = (
        '<!DOCTYPE html>\n'
        '<html><head><meta charset="utf-8">\n'
        '<style>\n'
        '  body { margin: 0; padding: 8px; background: transparent;\n'
        '         color: #e5e7eb; font-family: ui-system, system-ui, sans-serif; }\n'
        '  .mermaid { background: rgba(255,255,255,0.02); border-radius: 8px; padding: 8px; }\n'
        '  .node { cursor: pointer; }\n'
        '  .node:hover rect, .node:hover polygon { filter: brightness(1.25); }\n'
        '</style>\n'
        '<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>\n'
        '</head><body>\n'
        '<div class="mermaid" id="m_' + key_prefix + '">\n'
        + js_src + "\n"
        '</div>\n'
        '<script>\n'
        '  mermaid.initialize({\n'
        '    startOnLoad: true,\n'
        '    theme: "dark",\n'
        '    themeVariables: {\n'
        '      background: "#0f172a",\n'
        '      primaryColor: "#1e293b",\n'
        '      primaryTextColor: "#e5e7eb",\n'
        '      primaryBorderColor: "#334155",\n'
        '      lineColor: "#64748b",\n'
        '      fontFamily: "ui-system, system-ui, sans-serif",\n'
        '    },\n'
        '    flowchart: { curve: "basis", htmlLabels: true, useMaxWidth: true },\n'
        '    securityLevel: "loose",\n'
        '  }).then(() => {\n'
        '    document.querySelectorAll(".mermaid .node").forEach(node => {\n'
        '      node.addEventListener("click", () => {\n'
        '        const id = node.id || (node.querySelector("[id]") ? node.querySelector("[id]").id : "");\n'
        '        const m = id.match(/n_[A-Za-z0-9_]+/);\n'
        '        if (!m) return;\n'
        '        const spanId = m[0].substring(2).replace(/_/g, "-");\n'
        '        const url = new URL(window.parent.location.href);\n'
        '        url.searchParams.set("focus", spanId);\n'
        '        window.parent.location.href = url.toString();\n'
        '      });\n'
        '    });\n'
        '  });\n'
        '</script>\n'
        '</body></html>'
    )
    st.components.v1.html(html_doc, height=height, scrolling=True)


def _render_flowchart_mode(sel_spans: list, kpi, all_by_id: dict) -> None:
    """流程图模式: 全貌 + 点击节点放大聚焦(左:子图 / 右:详情)。"""
    focus = st.query_params.get("focus")
    if focus and focus in all_by_id:
        focused_span = all_by_id[focus]
        st.markdown(
            f"#### \U0001F50D \u805a\u7126\u00a0\u00b7\u00a0{_span_display_name(focused_span)}"
        )
        if st.button("\u2190 \u8fd4\u56de\u5168\u8c8c", key="back_to_overview"):
            if "focus" in st.query_params:
                del st.query_params["focus"]
            st.rerun()
        st.caption(
            f"\u663e\u793a\u9009\u4e2d\u8282\u70b9\u53ca\u5176 2 \u8df3\u90bb\u57df\u3002"
            f"\u70b9\u51fb\u300c\u8fd4\u56de\u5168\u8c8c\u300d\u6216\u6e05\u9664 URL \u4e2d\u7684 focus \u53c2\u6570\u53ef\u9000\u51fa\u3002"
        )
        fcol_l, fcol_r = st.columns([1.3, 1])
        with fcol_l:
            st.markdown("##### \u8fd1\u90e8\u5b50\u56fe")
            _render_mermaid_html(
                _build_mermaid(sel_spans, focus=focus, hops=2),
                height=620, key_prefix="focus",
            )
        with fcol_r:
            st.markdown("##### \u8be6\u60c5\u9762\u677f")
            st.session_state.selected_span = focus
            _render_detail_panel(sel_spans, by_id_all=all_by_id)
    else:
        st.markdown("#### \U0001F500 Agent \u6d41\u7a0b\u56fe")
        st.caption(
            f"\u5171 {len(sel_spans)} \u4e2a span\u3002"
            f"\u70b9\u51fb\u8282\u70b9\u53ef\u653e\u5927\u67e5\u770b\u8be6\u60c5\uff1b"
            f"\u5207\u56de\u300c\u5217\u8868\u300d\u6a21\u5f0f\u67e5\u770b\u5b8c\u6574\u6811\u3002"
        )
        _render_mermaid_html(
            _build_mermaid(sel_spans, focus=None),
            height=720, key_prefix="full",
        )
        if focus and focus not in all_by_id:
            # Stale focus param (span was filtered out): clear it.
            if "focus" in st.query_params:
                del st.query_params["focus"]
            st.rerun()


'''

src = src.replace(insert_A_marker, helpers + insert_A_marker, 1)


# ============================================================
# INSERTION B: view-mode radio after hdr_r block
# We look for the close of `with hdr_r:` block by finding the next line
# beginning with "if trace_ids:" (start of trace dropdown).
# ============================================================
insert_B_marker = '        try:\n            idx = trace_ids.index(st.session_state.selected_trace)\n        except ValueError:\n            idx = 0'
assert insert_B_marker in src, "marker B not found"

radio_block = (
    '\n# ---------------------------------------------------------------------------\n'
    '# View-mode switcher: \u5217\u8868 / \u6d41\u7a0b\u56fe\n'
    '# ---------------------------------------------------------------------------\n'
    'st.session_state.setdefault("view_mode", "\u5217\u8868")\n'
    '_view_opts = ["\u5217\u8868", "\u6d41\u7a0b\u56fe"]\n'
    '_view_idx = _view_opts.index(st.session_state.view_mode) if st.session_state.view_mode in _view_opts else 0\n'
    'st.radio(\n'
    '    "\u89c6\u56fe\u6a21\u5f0f",\n'
    '    options=_view_opts,\n'
    '    index=_view_idx,\n'
    '    horizontal=True,\n'
    '    key="view_mode",\n'
    '    label_visibility="collapsed",\n'
    ')\n'
)

# Insert radio_block just BEFORE the trace dropdown marker
src = src.replace(insert_B_marker, radio_block + insert_B_marker, 1)


# ============================================================
# INSERTION C: wrap 3-column body in if/else
# We replace the existing `col_tree, col_detail, col_meta = st.columns(...)` block
# with a `if view_mode == "列表":` branch + `else:` branch.
# ============================================================
old_body = (
    'col_tree, col_detail, col_meta = st.columns([1.1, 2.6, 1.3])\n'
    '\n'
    '\n'
    '# ===========================================================================\n'
    '# LEFT column - navigation tree\n'
    '# ===========================================================================\n'
    'with col_tree:\n'
    '    st.markdown(\n'
    '        f"#### \U0001F5C2 \u5bfc\u822a\u6811 "\n'
    '        f\'<span style="color:#9ca3af;font-size:11px;font-weight:400">\'\n'
    '        f\'\u00b7 {len(filtered_spans)} spans</span>\',\n'
    '        unsafe_allow_html=True,\n'
    '    )\n'
    '\n'
    '    def _select_only(sid: str) -> None:\n'
    '        st.session_state.selected_span = sid\n'
    '\n'
    '    def _toggle_expand(sid: str) -> None:\n'
    '        if sid in st.session_state.expanded_spans:\n'
    '            st.session_state.expanded_spans.discard(sid)\n'
    '        else:\n'
    '            st.session_state.expanded_spans.add(sid)\n'
    '\n'
    '    _render_tree(roots, children_map, depth=0)\n'
    '\n'
    '\n'
    '# ===========================================================================\n'
    '# CENTER column - detail panel (Run / Feedback / Metadata)\n'
    '# ===========================================================================\n'
    'with col_detail:\n'
    '    st.markdown("#### \U0001F50D Span \u8be6\u60c5")\n'
    '    _render_detail_panel(sel_spans, by_id_all={s["span_id"]: s for s in sel_spans})\n'
    '\n'
    '\n'
    '# ===========================================================================\n'
    '# RIGHT column - metadata indicator panel\n'
    '# ===========================================================================\n'
    'with col_meta:\n'
    '    st.markdown("#### \U0001F4CA \u5143\u6570\u636e\u9762\u677f")\n'
    '    _render_metadata_panel(kpi, sel_spans, by_id_all={s["span_id"]: s for s in sel_spans})\n'
)
assert old_body in src, "marker C not found"

new_body = (
    'if st.session_state.view_mode == "\u5217\u8868":\n'
    '    col_tree, col_detail, col_meta = st.columns([1.1, 2.6, 1.3])\n'
    '\n'
    '    # =======================================================================\n'
    '    # LEFT column - navigation tree\n'
    '    # =======================================================================\n'
    '    with col_tree:\n'
    '        st.markdown(\n'
    '            f"#### \U0001F5C2 \u5bfc\u822a\u6811 "\n'
    '            f\'<span style="color:#9ca3af;font-size:11px;font-weight:400">\'\n'
    '            f\'\u00b7 {len(filtered_spans)} spans</span>\',\n'
    '            unsafe_allow_html=True,\n'
    '        )\n'
    '\n'
    '        def _select_only(sid: str) -> None:\n'
    '            st.session_state.selected_span = sid\n'
    '\n'
    '        def _toggle_expand(sid: str) -> None:\n'
    '            if sid in st.session_state.expanded_spans:\n'
    '                st.session_state.expanded_spans.discard(sid)\n'
    '            else:\n'
    '                st.session_state.expanded_spans.add(sid)\n'
    '\n'
    '        _render_tree(roots, children_map, depth=0)\n'
    '\n'
    '    # =======================================================================\n'
    '    # CENTER column - detail panel (Run / Feedback / Metadata)\n'
    '    # =======================================================================\n'
    '    with col_detail:\n'
    '        st.markdown("#### \U0001F50D Span \u8be6\u60c5")\n'
    '        _render_detail_panel(sel_spans, by_id_all={s["span_id"]: s for s in sel_spans})\n'
    '\n'
    '    # =======================================================================\n'
    '    # RIGHT column - metadata indicator panel\n'
    '    # =======================================================================\n'
    '    with col_meta:\n'
    '        st.markdown("#### \U0001F4CA \u5143\u6570\u636e\u9762\u677f")\n'
    '        _render_metadata_panel(kpi, sel_spans, by_id_all={s["span_id"]: s for s in sel_spans})\n'
    '\n'
    'else:  # "\u6d41\u7a0b\u56fe" mode\n'
    '    _render_flowchart_mode(\n'
    '        sel_spans,\n'
    '        kpi,\n'
    '        all_by_id={s["span_id"]: s for s in sel_spans},\n'
    '    )\n'
)
src = src.replace(old_body, new_body, 1)

open(p, "w", encoding="utf-8", newline="\n").write(src)
print("Patches applied; bytes:", len(src.encode("utf-8")))