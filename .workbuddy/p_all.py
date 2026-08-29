# -*- coding: utf-8 -*-
"""Reapply Mermaid-related patches: LR->TD, safe regex, chain/parallel, focusSpan."""
import sys, re
sys.stdout.reconfigure(encoding="utf-8")
p = r"D:\my-projects\agent-monitor\viewer.py"
content = open(p, encoding="utf-8").read()

# === 1. _mermaid_label: fix safe regex ===
old_label = chr(32) * 4 + "name = re.sub(r'[\\[\\](){}<>|`]', ' ', name).strip()"
new_label = chr(32) * 4 + "name = re.sub(r'[\\\"\\\\#;|]', ' ', name).strip()"
count_label = content.count(old_label)
if count_label:
    content = content.replace(old_label, new_label, 1)
    print(f"1: _mermaid_label safe regex fixed ({count_label})")
else:
    print("1: _mermaid_label safe regex pattern not found")

# === 2. _build_mermaid: replace whole function ===
m_build = re.search(
    r"def _build_mermaid\(spans, \*, focus=None, hops=2\):.*?(?=\n\n\ndef )",
    content, re.DOTALL,
)
if m_build:
    NEW_BUILD = '''def _build_mermaid(spans, *, focus=None, hops=2):
    """Build a Mermaid `flowchart TD` source. With focus, render a 2-hop subgraph.

    Nodes are emitted in start_time order so Mermaid's TD layout flows
    top-down in time. Each node label carries a t+<ms> relative timestamp.
    Sequential siblings are chained; concurrent siblings wrapped in subgraph.
    """
    if not spans:
        return "flowchart TD\\n    empty[\\u3000\\uff08\\u65e0 span\\uff09\\u3000]"
    spans_by_id = {s["span_id"]: s for s in spans}

    if focus and focus in spans_by_id:
        visible = {focus}
        up, down = {focus}, {focus}
        for _ in range(hops):
            new_up = set()
            for sid in up:
                pid = spans_by_id.get(sid, {}).get("parent_span_id")
                if pid and pid in spans_by_id and pid not in visible:
                    new_up.add(pid)
            visible |= new_up
            up = new_up
            new_down = set()
            for sid in down:
                for s in spans:
                    if s.get("parent_span_id") == sid and s["span_id"] not in visible:
                        new_down.add(s["span_id"])
            visible |= new_down
            down = new_down
    else:
        visible = {s["span_id"] for s in spans}
    visible_spans = [s for s in spans if s["span_id"] in visible]

    if len(visible_spans) > _MERMAID_MAX_NODES and not focus:
        return (
            "flowchart TD\\n"
            "    root[<\\u3000\\u5171 " + str(len(spans)) + " \\u4e2a span\\u3000<br/>"
            "<small>\\u8282\\u70b9\\u6570\\u8fc7\\u591a\\uff0c\\u8bf7\\u5207\\u56de \\u5217\\u8868 \\u6a21\\u5f0f\\u67e5\\u770b</small>]\\n"
            "    classDef root fill:#4b5563,color:#fff,stroke:#1f2937;\\n"
            "    class root root;"
        )

    visible_spans.sort(key=lambda s: int(s.get("start_time", 0)))
    starts = [int(s.get("start_time", 0)) for s in visible_spans]
    min_start = min(starts) if starts else 0

    out = ["flowchart TD"]
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

    children_by_parent = {}
    for s in visible_spans:
        pid = s.get("parent_span_id")
        if pid and pid in visible:
            children_by_parent.setdefault(pid, []).append(s)

    _handled_parents = set()

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
        start_ns = int(span.get("start_time", 0))
        offset_ms = int((start_ns - min_start) / 1_000_000)
        label = _mermaid_label(span)
        full_label = f"{label}<br/><small>t+{offset_ms}ms</small>"
        safe = re.sub(r"[\\"\\\\#;|]", " ", full_label).strip()
        out.append(f'    {nid}["{safe}"]')
        out.append(f"    class {nid} {",".join(cls)};")

    # Infer chain vs parallel from time-overlap
    for parent_id, kids in children_by_parent.items():
        if len(kids) < 2:
            continue
        sorted_kids = sorted(kids, key=lambda s: int(s.get("start_time", 0)))
        n_kids = len(sorted_kids)
        all_sequential = True
        for i in range(n_kids - 1):
            prev_end = int(sorted_kids[i].get("end_time", 0))
            next_start = int(sorted_kids[i + 1].get("start_time", 0))
            if next_start < prev_end:
                all_sequential = False
                break
        pnid = _mermaid_safe_id(parent_id)
        if all_sequential:
            # Chain: parent connects to first child only; siblings chain in time
            _handled_parents.add(parent_id)
            first_id = _mermaid_safe_id(sorted_kids[0]["span_id"])
            out.append(f"    {pnid} --> {first_id}")
            for i in range(n_kids - 1):
                a = _mermaid_safe_id(sorted_kids[i]["span_id"])
                b = _mermaid_safe_id(sorted_kids[i + 1]["span_id"])
                out.append(f"    {a} --> {b}")
        else:
            # Parallel: wrap in subgraph; all children fan out from parent
            _handled_parents.add(parent_id)
            out.append('    subgraph SG_' + pnid + '["\\u5e76\\u884c\\u5206\\u652f"]')
            out.append("    direction LR")
            for k in sorted_kids:
                out.append(f"        {_mermaid_safe_id(k['span_id'])}")
            out.append("    end")
            for k in sorted_kids:
                out.append(f"    {pnid} --> {_mermaid_safe_id(k['span_id'])}")

    # Render edges for parents not handled by chain/parallel block
    for span in visible_spans:
        pid = span.get("parent_span_id")
        if pid and pid in visible and pid not in _handled_parents:
            out.append(f"    {_mermaid_safe_id(pid)} --> {_mermaid_safe_id(span['span_id'])}")

    # Mermaid native click directives
    for span in visible_spans:
        nid = _mermaid_safe_id(span["span_id"])
        out.append(f"    click {nid} focusSpan")

    return "\\n".join(out)


'''
    content = content[:m_build.start()] + NEW_BUILD + content[m_build.end():]
    print("2: _build_mermaid replaced")
else:
    print("2: _build_mermaid pattern not found")

# === 3. _render_mermaid_html: replace whole function ===
m_html = re.search(
    r"def _render_mermaid_html\(src, \*, height=620, key_prefix='m'\):.*?(?=\n\n\ndef )",
    content, re.DOTALL,
)
if m_html:
    NEW_HTML = '''def _render_mermaid_html(src, *, height=620, key_prefix='m'):
    """Render Mermaid inside an iframe. Mermaid click directive fires
    window.focusSpan(nodeId); DOM delegation is kept as a backup.
    """
    js_src = (
        src.replace("\\\\", "\\\\\\\\")
           .replace("`", "\\\\`")
           .replace("${", "\\\\${")
    )
    html_doc = (
        "<!DOCTYPE html>\\n"
        "<html><head><meta charset=\\"utf-8\\">\\n"
        "<style>\\n"
        "  body { margin: 0; padding: 8px; background: transparent;\\n"
        "         color: #e5e7eb; font-family: ui-system, system-ui, sans-serif; }\\n"
        "  .mermaid { background: rgba(255,255,255,0.02); border-radius: 8px; padding: 8px; overflow-x: auto; }\\n"
        "  .node { cursor: pointer; }\\n"
        "  .node:hover rect, .node:hover polygon { filter: brightness(1.25); }\\n"
        "</style>\\n"
        "<script src=\\"https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js\\"></script>\\n"
        "</head><body>\\n"
        "<div class=\\"mermaid\\" id=\\"m_" + key_prefix + "\\">\\n"
        + js_src + "\\n"
        "</div>\\n"
        "<script>\\n"
        "  window.focusSpan = function(nodeId) {\\n"
        "    var spanId = (nodeId || \\"\\").replace(/^n_/, \\"\\").replace(/_/g, \\"-\\");\\n"
        "    if (!spanId) return;\\n"
        "    var url = new URL(window.parent.location.href);\\n"
        "    url.searchParams.set(\\"focus\\", spanId);\\n"
        "    window.parent.location.href = url.toString();\\n"
        "  };\\n"
        "  mermaid.initialize({\\n"
        "    startOnLoad: true,\\n"
        "    theme: \\"dark\\",\\n"
        "    themeVariables: {\\n"
        "      background: \\"#0f172a\\",\\n"
        "      primaryColor: \\"#1e293b\\",\\n"
        "      primaryTextColor: \\"#e5e7eb\\",\\n"
        "      primaryBorderColor: \\"#334155\\",\\n"
        "      lineColor: \\"#64748b\\",\\n"
        "      fontFamily: \\"ui-system, system-ui, sans-serif\\",\\n"
        "    },\\n"
        "    flowchart: { curve: \\"basis\\", htmlLabels: true, useMaxWidth: true },\\n"
        "    securityLevel: \\"loose\\",\\n"
        "  }).then(function() {\\n"
        "    document.querySelectorAll(\\".mermaid .node\\").forEach(function(node) {\\n"
        "      node.addEventListener(\\"click\\", function() {\\n"
        "        var id = node.id || (node.querySelector(\\"[id]\\") ? node.querySelector(\\"[id]\\").id : \\"\\");\\n"
        "        var m = id.match(/n_[A-Za-z0-9_]+/);\\n"
        "        if (m) window.focusSpan(m[0]);\\n"
        "      });\\n"
        "    });\\n"
        "  });\\n"
        "</script>\\n"
        "</body></html>"
    )
    st.components.v1.html(html_doc, height=height, scrolling=True)


'''
    content = content[:m_html.start()] + NEW_HTML + content[m_html.end():]
    print("3: _render_mermaid_html replaced")
else:
    print("3: _render_mermaid_html pattern not found")

# === 4. flowchart mode: replace with 3-column layout ===
m_fm = re.search(
    r"def _render_flowchart_mode\(sel_spans, kpi, all_by_id\):.*?(?=\n\n\ndef )",
    content, re.DOTALL,
)
if m_fm:
    NEW_FM = '''def _render_flowchart_mode(sel_spans, kpi, all_by_id):
    """3-column flowchart explorer: traces | mermaid TD | span detail.

    Layout:
        col_left   = trace cards list (click to switch trace)
        col_center = current trace as Mermaid `flowchart TD`
        col_right  = selected span detail (Run / Feedback / Metadata)

    Click a flowchart node -> URL becomes `?trace=<tid>&focus=<sid>` -> page
    reloads -> right column shows that span.  URL is bookmarkable.
    """
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
        row = _fmt_trace_option(tid)
        is_cur = (tid == cur_tid)
        btn_type = "primary" if is_cur else "secondary"
        active_cls = " trace-card-active" if is_cur else ""
        # Build card HTML with button + children preview inside
        # Using st.markdown once for the wrapper + st.button for click handling
        st.markdown(
            f'<div class="trace-card{active_cls}">',
            unsafe_allow_html=True,
        )
        st.button(
            row,
            key=f"trace_card_{tid}",
            type=btn_type,
            use_container_width=True,
        )
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
                    f'<div class="trace-card-children">\\u21b3 {preview}</div>',
                    unsafe_allow_html=True,
                )
        st.markdown("</div>", unsafe_allow_html=True)


def _render_flowchart_center(sel_spans):
    """Center column: current trace's span flowchart (TD)."""
    st.markdown("#### \\U0001F500 Agent \\u6d41\\u7a0b\\u56fe")
    st.caption(
        f"\\u5171 {len(sel_spans)} \\u4e2a span\\u3002"
        "\\u70b9\\u51fb\\u8282\\u70b9\\u67e5\\u770b\\u8be6\\u60c5\\uff1b"
        "\\u4e0a\\u65b9\\u4e3a\\u8d77\\u59cb\\u65f6\\u95f4\\u6700\\u65e9\\u7684\\u8282\\u70b9\\u3002"
    )
    _render_mermaid_html(
        _build_mermaid(sel_spans, focus=None),
        height=720,
        key_prefix="explorer",
    )
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
    st.markdown("#### \\U0001F50D Span \\u8be6\\u60c5")
    if focus and focus in all_by_id:
        if st.button("\\u2190 \\u8fd4\\u56de\\u5168\\u8c8c", key="back_to_overview"):
            _clear_focus()
        st.session_state.selected_span = focus
    elif st.session_state.selected_span and st.session_state.selected_span in all_by_id:
        pass
    else:
        roots = [s for s in sel_spans if not s.get("parent_span_id")]
        if roots:
            st.session_state.selected_span = roots[0]["span_id"]
    _render_detail_panel(sel_spans, by_id_all=all_by_id)
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
    content = content[:m_fm.start()] + NEW_FM + content[m_fm.end():]
    print("4: _render_flowchart_mode replaced (3-col layout)")
else:
    print("4: _render_flowchart_mode pattern not found")

open(p, "w", encoding="utf-8", newline="\n").write(content)
print("\nBytes:", len(content.encode("utf-8")))