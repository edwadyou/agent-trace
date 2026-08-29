# -*- coding: utf-8 -*-
"""Apply all 5 phases + run tab refactor in one pass, with proper escaping."""
import sys
sys.stdout.reconfigure(encoding="utf-8")

p = r"D:\my-projects\agent-monitor\viewer.py"
src = open(p, encoding="utf-8").read()

# IMPORTANT: write Python source code with escaped backslashes ("\\n" not "\n")
# so the file ends up with literal "\n" in the source, which Python then
# parses as a newline character at runtime.


def sub(rules, label):
    n = 0
    miss = []
    for old, new in rules:
        c = src.count(old)
        if c:
            src = src.replace(old, new)
            n += c
        else:
            miss.append(old[:60])
    print(f"{label}: {n} subs, {len(miss)} miss")
    for m in miss[:5]:
        print(f"  miss: {m!r}")
    return n


# ===========================================================
# Phase 1: _trace_label + _fmt_trace_option
# ===========================================================
sub([
    ("Tool Agent", "\u5de5\u5177\u578b\u667a\u80fd\u4f53"),
    ("Retrieval Chain", "\u68c0\u7d22\u94fe"),
    ("LLM Chain", "LLM \u8c03\u7528\u94fe"),
    ("LLM Call (templated)", "\u5927\u6a21\u578b\u8c03\u7528\uff08\u5e26\u6a21\u677f\uff09"),
    ("Parallel Search ({n})", "\u591a\u4efb\u52a1\u5e76\u884c\uff08{n}\uff09"),
    ("Parallel: {_short_purpose(tools[0]) or tools[0]}", "\u591a\u4efb\u52a1\u5e76\u884c\uff1a{_short_purpose(tools[0]) or tools[0]}"),
    ("Parallel: {a} + {b}", "\u591a\u4efb\u52a1\u5e76\u884c\uff1a{a} + {b}"),
    ("Parallel Search (", "\u591a\u4efb\u52a1\u5e76\u884c\uff08"),
    ("Parallel: ", "\u591a\u4efb\u52a1\u5e76\u884c\uff1a"),
    ("Parallel Branches", "\u591a\u4efb\u52a1\u5e76\u884c"),
    ("Chain Step", "\u94fe\u8def\u6b65\u9aa4"),
    ("LLM Call", "\u5927\u6a21\u578b\u8c03\u7528"),
    ("(unnamed)", "\uff08\u672a\u547d\u540d\uff09"),
    ("(empty trace)", "\uff08\u7a7a trace\uff09"),
    ("  # red cross", "  # \u7ea2\u8272\u53c9\uff08\u9519\u8bef\uff09"),
    ("  # green tick", "  # \u7eff\u8272\u52fe\uff08\u6210\u529f\uff09"),
    ("  # hourglass (UNSET / in-progress)", "  # \u6c99\u6f0f\uff08\u672a\u5b8c\u6210\uff09"),
], "Phase 1")


# ===========================================================
# Phase 2: UI strings (still pre-translation)
# ===========================================================
sub([
    ("## \U0001F50E Agent Trace Monitor  `v3-3col`", "## \U0001F50E Agent \u94fe\u8def\u76d1\u63a7  `v3-3col`"),
    ('st.tabs(["Run", "Feedback", "Metadata"])', 'st.tabs(["\u8fd0\u884c", "\u53cd\u9988", "\u5143\u6570\u636e"])'),
    ("#### \u26a0 Error", "#### \u26a0 \u9519\u8bef"),
    ("**Stack trace:**", "**\u5806\u6808\u4fe1\u606f\uff1a**"),
    ('"Trace source"', '"\u6570\u636e\u6e90"'),
    ("\u2b07  Input", "\u2b07  \u8f93\u5165"),
    ("\u2b06  Output", "\u2b06  \u8f93\u51fa"),
    ("**Tool arguments:**", "**\u5de5\u5177\u53c2\u6570\uff1a**"),
    ("(no parameters captured)", "\uff08\u672a\u6355\u83b7\u53c2\u6570\uff09"),
    ("(no result captured)", "\uff08\u672a\u6355\u83b7\u8fd4\u56de\u7ed3\u679c\uff09"),
    ("(no span events recorded)", "\uff08\u672a\u8bb0\u5f55 span \u4e8b\u4ef6\uff09"),
    ('<div class="detail-head">Identity</div>', '<div class="detail-head">\u57fa\u672c\u4fe1\u606f</div>'),
    ('<div class="detail-head">Timing</div>', '<div class="detail-head">\u65f6\u95f4\u4fe1\u606f</div>'),
    ('<div class="detail-head">All attributes (filtered)</div>', '<div class="detail-head">\u5168\u90e8\u5c5e\u6027\uff08\u8fc7\u6ee4\u540e\uff09</div>'),
    ('<div class="detail-head">Span events</div>', '<div class="detail-head">Span \u4e8b\u4ef6</div>'),
    ('<div class="meta-section"><h5>Tokens</h5>', '<div class="meta-section"><h5>Token</h5>'),
    ('<div class="meta-section"><h5>Cost (est.)</h5>', '<div class="meta-section"><h5>\u6210\u672c\uff08\u4f30\u8ba1\uff09</h5>'),
    ('<div class="meta-section"><h5>Selected span</h5>', '<div class="meta-section"><h5>\u9009\u4e2d\u7684 Span</h5>'),
    ('<div style="color:#6b7280;font-size:11.5px">no token data captured</div>', '<div style="color:#6b7280;font-size:11.5px">\u672a\u6355\u83b7 token \u6570\u636e</div>'),
    ('<div style="color:#6b7280;font-size:11.5px">click a tree node</div>', '<div style="color:#6b7280;font-size:11.5px">\u8bf7\u5728\u5de6\u4fa7\u6811\u4e2d\u9009\u62e9\u4e00\u4e2a span</div>'),
    ('("Service", trace_kpi.service_name or "-")', '("\u670d\u52a1", trace_kpi.service_name or "-")'),
    ('("Span count", str(trace_kpi.n_spans))', '("Span \u6570\u91cf", str(trace_kpi.n_spans))'),
    ('("LLM / Tool", f"{trace_kpi.n_llm} / {trace_kpi.n_tool}")', '("\u5927\u6a21\u578b\u8c03\u7528 / \u5de5\u5177", f"{trace_kpi.n_llm} / {trace_kpi.n_tool}")'),
    ('("Chain / Agent / Prompt",\n                       f"{trace_kpi.n_chain} / {trace_kpi.n_agent} / {trace_kpi.n_prompt}")',
     '("\u94fe\u8def / \u667a\u80fd\u4f53 / \u63d0\u793a\u8bcd",\n                       f"{trace_kpi.n_chain} / {trace_kpi.n_agent} / {trace_kpi.n_prompt}")'),
    ('No spans in the current trace. Run your agent and refresh.', '\u5f53\u524d trace \u4e2d\u6ca1\u6709 span\uff0c\u8bf7\u8fd0\u884c\u4f60\u7684 agent \u540e\u5237\u65b0\u3002'),
    ('<div style="margin-top:6px;">No feedback recorded yet.</div>', '<div style="margin-top:6px;">\u5c1a\u672a\u8bb0\u5f55\u53cd\u9988\u5206\u6570\u3002</div>'),
    ('Once you score this run, scores will appear here automatically.', '\u4e00\u65e6\u5bf9\u8be5\u8fd0\u884c\u8bc4\u5206\uff0c\u5206\u6570\u4f1a\u81ea\u52a8\u51fa\u73b0\u5728\u8fd9\u91cc\u3002'),
    ('("Parent Span ID", span.get("parent_span_id") or "(root)")', '("\u7236 Span ID", span.get("parent_span_id") or "(\u6839 span)")'),
    ('("Service", span.get("service_name") or "-")', '("\u670d\u52a1", span.get("service_name") or "-")'),
    ('("Schema ver", str(span.get("schema_version", "-")))', '("\u6cd5\u6848\u7248\u672c", str(span.get("schema_version", "-")))'),
    ('("Session / Thread", sid)', '("\u4f1a\u8bdd / \u4e3b\u9898", sid)'),
    ('("User", uid)', '("\u7528\u6237", uid)'),
    ('("Tags", str(tags))', '("\u6807\u7b7e", str(tags))'),
    ('("Duration", _format_duration_ms(dur_ms))', '("\u603b\u65f6\u957f", _format_duration_ms(dur_ms))'),
    ('("Name", name)', '("\u540d\u79f0", name)'),
    ('("Kind", kind)', '("\u7c7b\u578b", kind)'),
    ('("Latency", _format_duration_ms(dur_ms))', '("\u8017\u65f6", _format_duration_ms(dur_ms))'),
    ('("Input tokens",      canon(attrs, "tokens.input"))', '("\u8f93\u5165 token",      canon(attrs, "tokens.input"))'),
    ('("Output tokens",     canon(attrs, "tokens.output"))', '("\u8f93\u51fa token",     canon(attrs, "tokens.output"))'),
    ('("Total tokens",      canon(attrs, "tokens.total"))', '("\u603b\u8ba1 token",      canon(attrs, "tokens.total"))'),
    ('("Cache read tokens", canon(attrs, "tokens.cache_read"))', '("\u7f13\u5b58\u8bfb\u53d6 token", canon(attrs, "tokens.cache_read"))'),
    ('("Reasoning tokens",  canon(attrs, "tokens.reasoning"))', '("\u601d\u8003 token",  canon(attrs, "tokens.reasoning"))'),
    ("#### \U0001F5C2 Navigation Tree ", "#### \U0001F5C2 \u5bfc\u822a\u6811 "),
    ("\u23f1  Flow state ({len(events)} event(s))", "\u23f1  \u6d41\u7a0b\u4e8b\u4ef6\uff08{len(events)} \u6761\uff09"),
    ("Click a node in the tree to inspect it.", "\u8bf7\u5728\u5de6\u4fa7\u6811\u4e2d\u9009\u4e2d\u4e00\u4e2a\u8282\u70b9\u67e5\u770b\u8be6\u60c5\u3002"),
    ('rows.append(("Tags", ", ".join(str(t) for t in tags)))', 'rows.append(("\u6807\u7b7e", ", ".join(str(t) for t in tags)))'),
    ('<div class="k">In / Out</div>', '<div class="k">\u8f93\u5165 / \u8f93\u51fa</div>'),
    ("\U0001F4B0 estimated cost (this span): **${cost:.4f}**", "\U0001F4B0 \u672c span \u4f30\u8ba1\u6210\u672c\uff1a**${cost:.4f}**"),
], "Phase 2")


# ===========================================================
# Phase 3: Flowchart helpers
# ===========================================================
helpers_marker = "# LEFT tree renderer"
assert helpers_marker in src

helpers = (
    "# ---------------------------------------------------------------------------\n"
    "# Flowchart mode (Mermaid) + click-to-zoom\n"
    "# ---------------------------------------------------------------------------\n"
    "_MERMAID_MAX_NODES = 80\n"
    "_NODE_LABEL_MAX_CHARS = 60\n"
    "\n"
    "\n"
    "def _mermaid_safe_id(sid):\n"
    "    return 'n_' + sid.replace('-', '_')\n"
    "\n"
    "\n"
    "def _mermaid_label(span):\n"
    "    attrs = span.get('attributes') or {}\n"
    "    kind = span_kind(attrs)\n"
    "    info = SPAN_KINDS.get(kind, SPAN_KINDS['UNKNOWN'])\n"
    "    icon = info[0]\n"
    "    name = _span_display_name(span)\n"
    "    name = re.sub(r'[\\[\\](){}<>|`]', ' ', name).strip()\n"
    "    if len(name) > _NODE_LABEL_MAX_CHARS:\n"
    "        name = name[:_NODE_LABEL_MAX_CHARS - 1] + '...'\n"
    "    start_ns = int(span.get('start_time', 0))\n"
    "    end_ns = int(span.get('end_time', 0))\n"
    "    dur_ms = (end_ns - start_ns) / 1_000_000\n"
    "    dur = _format_duration_ms(dur_ms)\n"
    "    return f'<b>{icon} {name}</b><br/><small>{kind} &middot; {dur}</small>'\n"
    "\n"
    "\n"
    "def _build_mermaid(spans, *, focus=None, hops=2):\n"
    "    if not spans:\n"
    "        return 'flowchart TB\\n    empty[\\u3000\\uff08\\u65e0 span\\uff09\\u3000]'\n"
    "    spans_by_id = {s['span_id']: s for s in spans}\n"
    "    if focus and focus in spans_by_id:\n"
    "        visible = {focus}\n"
    "        up, down = {focus}, {focus}\n"
    "        for _ in range(hops):\n"
    "            new_up = set()\n"
    "            for sid in up:\n"
    "                pid = spans_by_id.get(sid, {}).get('parent_span_id')\n"
    "                if pid and pid in spans_by_id and pid not in visible:\n"
    "                    new_up.add(pid)\n"
    "            visible |= new_up\n"
    "            up = new_up\n"
    "            new_down = set()\n"
    "            for sid in down:\n"
    "                for s in spans:\n"
    "                    if s.get('parent_span_id') == sid and s['span_id'] not in visible:\n"
    "                        new_down.add(s['span_id'])\n"
    "            visible |= new_down\n"
    "            down = new_down\n"
    "    else:\n"
    "        visible = {s['span_id'] for s in spans}\n"
    "    visible_spans = [s for s in spans if s['span_id'] in visible]\n"
    "    if len(visible_spans) > _MERMAID_MAX_NODES and not focus:\n"
    "        return (\n"
    "            'flowchart TB\\n'\n"
    "            '    root[<\\u3000\\u5171 ' + str(len(spans)) + ' \\u4e2a span\\u3000<br/>'\n"
    "            \"<small>\\u8282\\u70b9\\u6570\\u8fc7\\u591a\\uff0c\\u8bf7\\u5207\\u56de \\u5217\\u8868 \\u6a21\\u5f0f\\u67e5\\u770b</small>]\\n\"\n"
    "            '    classDef root fill:#4b5563,color:#fff,stroke:#1f2937;\\n'\n"
    "            '    class root root;'\n"
    "        )\n"
    "    out = ['flowchart TB']\n"
    "    out.append('    classDef llm       fill:#1d4ed8,color:#fff,stroke:#1e3a8a,stroke-width:1px;')\n"
    "    out.append('    classDef chain     fill:#065f46,color:#fff,stroke:#064e3b,stroke-width:1px;')\n"
    "    out.append('    classDef tool      fill:#b45309,color:#fff,stroke:#7c2d12,stroke-width:1px;')\n"
    "    out.append('    classDef agent     fill:#a16207,color:#fff,stroke:#713f12,stroke-width:1px;')\n"
    "    out.append('    classDef retriever fill:#7e22ce,color:#fff,stroke:#581c87,stroke-width:1px;')\n"
    "    out.append('    classDef embedding fill:#0e7490,color:#fff,stroke:#164e63,stroke-width:1px;')\n"
    "    out.append('    classDef reranker  fill:#6d28d9,color:#fff,stroke:#4c1d95,stroke-width:1px;')\n"
    "    out.append('    classDef prompt    fill:#3f6212,color:#fff,stroke:#365314,stroke-width:1px;')\n"
    "    out.append('    classDef parser    fill:#4b5563,color:#fff,stroke:#1f2937,stroke-width:1px;')\n"
    "    out.append('    classDef evaluator fill:#a8a29e,color:#1c1917,stroke:#78716c,stroke-width:1px;')\n"
    "    out.append('    classDef guardrail fill:#b91c1c,color:#fff,stroke:#7f1d1d,stroke-width:1px;')\n"
    "    out.append('    classDef unknown   fill:#6b7280,color:#fff,stroke:#374151,stroke-width:1px;')\n"
    "    out.append('    classDef error     stroke:#ef4444,stroke-width:2px,color:#fff;')\n"
    "    out.append('    classDef focus     stroke:#facc15,stroke-width:3px;')\n"
    "    out.append('    linkStyle default stroke:#64748b,stroke-width:1px;')\n"
    "    for span in visible_spans:\n"
    "        sid = span['span_id']\n"
    "        nid = _mermaid_safe_id(sid)\n"
    "        kind = span_kind(span.get('attributes') or {})\n"
    "        kind_class = kind.lower() if kind in SPAN_KINDS else 'unknown'\n"
    "        cls = [kind_class]\n"
    "        if str(span.get('status', '')).upper() == 'ERROR':\n"
    "            cls.append('error')\n"
    "        if sid == focus:\n"
    "            cls.append('focus')\n"
    "        out.append(f'    {nid}[\"{_mermaid_label(span)}\"]')\n"
    "        out.append(f'    class {nid} {\",\".join(cls)};')\n"
    "    for span in visible_spans:\n"
    "        pid = span.get('parent_span_id')\n"
    "        if pid and pid in visible:\n"
    "            out.append(f'    {_mermaid_safe_id(pid)} --> {_mermaid_safe_id(span[\"span_id\"])}')\n"
    "    return '\\n'.join(out)\n"
    "\n"
    "\n"
    "def _render_mermaid_html(src, *, height=620, key_prefix='m'):\n"
    "    js_src = (\n"
    "        src.replace('\\\\', '\\\\\\\\')\n"
    "           .replace('`', '\\\\`')\n"
    "           .replace('${', '\\\\${')\n"
    "    )\n"
    "    html_doc = (\n"
    "        '<!DOCTYPE html>\\n'\n"
    "        '<html><head><meta charset=\"utf-8\">\\n'\n"
    "        '<style>\\n'\n"
    "        '  body { margin: 0; padding: 8px; background: transparent;\\n'\n"
    "        \"         color: #e5e7eb; font-family: ui-system, system-ui, sans-serif; }\\n\"\n"
    "        '  .mermaid { background: rgba(255,255,255,0.02); border-radius: 8px; padding: 8px; }\\n'\n"
    "        '  .node { cursor: pointer; }\\n'\n"
    "        '  .node:hover rect, .node:hover polygon { filter: brightness(1.25); }\\n'\n"
    "        '</style>\\n'\n"
    "        '<script src=\"https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js\"></script>\\n'\n"
    "        '</head><body>\\n'\n"
    "        \"<div class='mermaid' id='m_\" + key_prefix + \"'>\\n\"\n"
    "        + js_src + '\\n'\n"
    "        \"</div>\\n\"\n"
    "        \"<script>\\n\"\n"
    "        \"  mermaid.initialize({\\n\"\n"
    "        \"    startOnLoad: true,\\n\"\n"
    "        \"    theme: 'dark',\\n\"\n"
    "        \"    themeVariables: {\\n\"\n"
    "        \"      background: '#0f172a',\\n\"\n"
    "        \"      primaryColor: '#1e293b',\\n\"\n"
    "        \"      primaryTextColor: '#e5e7eb',\\n\"\n"
    "        \"      primaryBorderColor: '#334155',\\n\"\n"
    "        \"      lineColor: '#64748b',\\n\"\n"
    "        \"      fontFamily: 'ui-system, system-ui, sans-serif',\\n\"\n"
    "        \"    },\\n\"\n"
    "        \"    flowchart: { curve: 'basis', htmlLabels: true, useMaxWidth: true },\\n\"\n"
    "        \"    securityLevel: 'loose',\\n\"\n"
    "        \"  }).then(() => {\\n\"\n"
    "        \"    document.querySelectorAll('.mermaid .node').forEach(node => {\\n\"\n"
    "        \"      node.addEventListener('click', () => {\\n\"\n"
    "        \"        const id = node.id || (node.querySelector('[id]') ? node.querySelector('[id]').id : '');\\n\"\n"
    "        \"        const m = id.match(/n_[A-Za-z0-9_]+/);\\n\"\n"
    "        \"        if (!m) return;\\n\"\n"
    "        \"        const spanId = m[0].substring(2).replace(/_/g, '-');\\n\"\n"
    "        \"        const url = new URL(window.parent.location.href);\\n\"\n"
    "        \"        url.searchParams.set('focus', spanId);\\n\"\n"
    "        \"        window.parent.location.href = url.toString();\\n\"\n"
    "        \"      });\\n\"\n"
    "        \"    });\\n\"\n"
    "        \"  });\\n\"\n"
    "        \"</script>\\n\"\n"
    "        \"</body></html>\"\n"
    "    )\n"
    "    st.components.v1.html(html_doc, height=height, scrolling=True)\n"
    "\n"
    "\n"
    "def _render_flowchart_mode(sel_spans, kpi, all_by_id):\n"
    "    focus = st.query_params.get('focus')\n"
    "    if focus and focus in all_by_id:\n"
    "        focused_span = all_by_id[focus]\n"
    "        st.markdown(\n"
    "            f\"#### \\U0001F50D \\u805a\\u7126\\u3000\\u00b7\\u3000{_span_display_name(focused_span)}\"\n"
    "        )\n"
    "        if st.button('\\u2190 \\u8fd4\\u56de\\u5168\\u8c8c', key='back_to_overview'):\n"
    "            if 'focus' in st.query_params:\n"
    "                del st.query_params['focus']\n"
    "            st.rerun()\n"
    "        st.caption(\n"
    "            '\\u663e\\u793a\\u9009\\u4e2d\\u8282\\u70b9\\u53ca\\u5176 2 \\u8df3\\u90bb\\u57df\\u3002'\n"
    "            '\\u70b9\\u51fb\\u300c\\u8fd4\\u56de\\u5168\\u8c8c\\u300d\\u6216\\u6e05\\u9664 URL \\u4e2d\\u7684 focus \\u53c2\\u6570\\u53ef\\u9000\\u51fa\\u3002'\n"
    "        )\n"
    "        fcol_l, fcol_r = st.columns([1.3, 1])\n"
    "        with fcol_l:\n"
    "            st.markdown('##### \\u8fd1\\u90e8\\u5b50\\u56fe')\n"
    "            _render_mermaid_html(\n"
    "                _build_mermaid(sel_spans, focus=focus, hops=2),\n"
    "                height=620, key_prefix='focus',\n"
    "            )\n"
    "        with fcol_r:\n"
    "            st.markdown('##### \\u8be6\\u60c5\\u9762\\u677f')\n"
    "            st.session_state.selected_span = focus\n"
    "            _render_detail_panel(sel_spans, by_id_all=all_by_id)\n"
    "    else:\n"
    "        st.markdown('#### \\U0001F500 Agent \\u6d41\\u7a0b\\u56fe')\n"
    "        st.caption(\n"
    "            f'\\u5171 {len(sel_spans)} \\u4e2a span\\u3002'\n"
    "            '\\u70b9\\u51fb\\u8282\\u70b9\\u53ef\\u653e\\u5927\\u67e5\\u770b\\u8be6\\u60c5\\uff1b'\n"
    "            '\\u5207\\u56de\\u300c\\u5217\\u8868\\u300d\\u6a21\\u5f0f\\u67e5\\u770b\\u5b8c\\u6574\\u6811\\u3002'\n"
    "        )\n"
    "        _render_mermaid_html(\n"
    "            _build_mermaid(sel_spans, focus=None),\n"
    "            height=720, key_prefix='full',\n"
    "        )\n"
    "        if focus and focus not in all_by_id:\n"
    "            if 'focus' in st.query_params:\n"
    "                del st.query_params['focus']\n"
    "            st.rerun()\n"
    "\n"
    "\n"
)
src = src.replace(helpers_marker, helpers + helpers_marker, 1)
print("Phase 3: helpers inserted")


# ===========================================================
# Phase 4: View-mode radio
# ===========================================================
anchor = "# Build filtered span list + tree structure"
assert anchor in src

radio = (
    "\n# ---------------------------------------------------------------------------\n"
    "# View-mode switcher\n"
    "# ---------------------------------------------------------------------------\n"
    "st.session_state.setdefault('view_mode', '\u5217\u8868')\n"
    "_view_opts = ['\u5217\u8868', '\u6d41\u7a0b\u56fe']\n"
    "_view_idx = _view_opts.index(st.session_state.view_mode) if st.session_state.view_mode in _view_opts else 0\n"
    "st.radio(\n"
    "    '\u89c6\u56fe\u6a21\u5f0f',\n"
    "    options=_view_opts,\n"
    "    index=_view_idx,\n"
    "    horizontal=True,\n"
    "    key='view_mode',\n"
    "    label_visibility='collapsed',\n"
    ")\n\n"
)
src = src.replace(anchor, radio + anchor, 1)
print("Phase 4: radio inserted")


# ===========================================================
# Phase 5: Wrap body in if/else
# ===========================================================
body_start = src.find("col_tree, col_detail, col_meta = st.columns")
body_end_marker = "_render_metadata_panel(kpi, sel_spans, by_id_all={s[\"span_id\"]: s for s in sel_spans})\n"
end_idx = src.find(body_end_marker, body_start) + len(body_end_marker)
assert body_start > 0 and end_idx > body_start
old_body = src[body_start:end_idx]

new_body = (
    "if st.session_state.view_mode == '\u5217\u8868':\n"
    "    col_tree, col_detail, col_meta = st.columns([1.1, 2.6, 1.3])\n"
    "\n"
    "    # =======================================================================\n"
    "    # LEFT column - navigation tree\n"
    "    # =======================================================================\n"
    "    with col_tree:\n"
    "        st.markdown(\n"
    "            f'#### \U0001F5C2 \u5bfc\u822a\u6811 '\n"
    "            f'<span style=\"color:#9ca3af;font-size:11px;font-weight:400\">'\n"
    "            f'\u00b7 {len(filtered_spans)} spans</span>',\n"
    "            unsafe_allow_html=True,\n"
    "        )\n"
    "\n"
    "        def _select_only(sid):\n"
    "            st.session_state.selected_span = sid\n"
    "\n"
    "        def _toggle_expand(sid):\n"
    "            if sid in st.session_state.expanded_spans:\n"
    "                st.session_state.expanded_spans.discard(sid)\n"
    "            else:\n"
    "                st.session_state.expanded_spans.add(sid)\n"
    "\n"
    "        _render_tree(roots, children_map, depth=0)\n"
    "\n"
    "    # =======================================================================\n"
    "    # CENTER column - detail panel\n"
    "    # =======================================================================\n"
    "    with col_detail:\n"
    "        st.markdown('#### \U0001F50D Span \u8be6\u60c5')\n"
    "        _render_detail_panel(sel_spans, by_id_all={s['span_id']: s for s in sel_spans})\n"
    "\n"
    "    # =======================================================================\n"
    "    # RIGHT column - metadata indicator panel\n"
    "    # =======================================================================\n"
    "    with col_meta:\n"
    "        st.markdown('#### \U0001F4CA \u5143\u6570\u636e\u9762\u677f')\n"
    "        _render_metadata_panel(kpi, sel_spans, by_id_all={s['span_id']: s for s in sel_spans})\n"
    "\n"
    "else:  # \u6d41\u7a0b\u56fe mode\n"
    "    _render_flowchart_mode(\n"
    "        sel_spans,\n"
    "        kpi,\n"
    "        all_by_id={s['span_id']: s for s in sel_spans},\n"
    "    )\n"
)
src = src[:body_start] + new_body + src[end_idx:]
print("Phase 5: body wrapped")


# ===========================================================
# Phase 6: Side-by-side Input/Output in _render_run_tab
# ===========================================================
io_start = src.find("# --- Input block (collapsible)")
io_end = src.find("# --- Token breakdown")
assert io_start > 0 and io_end > io_start

new_io = (
    "    # --- Input / Output side-by-side (headers aligned; each side scrolls independently) --\n"
    "    c_in, c_out = st.columns(2, gap='medium')\n"
    "\n"
    "    with c_in:\n"
    "        st.markdown('<div class=\"io-col-head in-head\">\u2b07  \u8f93\u5165</div>', unsafe_allow_html=True)\n"
    "        if kind == 'LLM':\n"
    "            msgs = to_messages(canon(attrs, 'messages.input'))\n"
    "            if msgs:\n"
    "                for m in msgs:\n"
    "                    role = (m.get('role') or 'user').lower()\n"
    "                    content = m.get('content') or ''\n"
    "                    _render_msg(role, content)\n"
    "                    for tc in m.get('tool_calls') or []:\n"
    "                        nm = tc.get('name') or 'tool'\n"
    "                        with st.expander(f'\U0001F527 {nm}'):\n"
    "                            st.json(tc.get('arguments'))\n"
    "            else:\n"
    "                _render_input_fallback(attrs, 'input.value')\n"
    "        elif kind == 'TOOL':\n"
    "            tp = canon(attrs, 'tool.parameters')\n"
    "            st.markdown('**\u5de5\u5177\u53c2\u6570\uff1a**')\n"
    "            if tp is None:\n"
    "                st.caption('\uff08\u672a\u6355\u83b7\u53c2\u6570\uff09')\n"
    "            elif isinstance(tp, str):\n"
    "                try:\n"
    "                    st.json(json.loads(tp))\n"
    "                except (json.JSONDecodeError, TypeError):\n"
    "                    st.code(tp)\n"
    "            else:\n"
    "                st.json(tp)\n"
    "        else:\n"
    "            _render_input_fallback(attrs, 'input.value')\n"
    "\n"
    "    with c_out:\n"
    "        st.markdown('<div class=\"io-col-head out-head\">\u2b06  \u8f93\u51fa</div>', unsafe_allow_html=True)\n"
    "        if kind == 'LLM':\n"
    "            msgs = to_messages(canon(attrs, 'messages.output'))\n"
    "            if msgs:\n"
    "                for m in msgs:\n"
    "                    role = (m.get('role') or 'assistant').lower()\n"
    "                    content = m.get('content') or ''\n"
    "                    _render_msg(role, content)\n"
    "            else:\n"
    "                _render_input_fallback(attrs, 'output.value')\n"
    "        elif kind == 'TOOL':\n"
    "            tout = canon(attrs, 'tool.output')\n"
    "            if tout is None:\n"
    "                st.caption('\uff08\u672a\u6355\u83b7\u8fd4\u56de\u7ed3\u679c\uff09')\n"
    "            elif isinstance(tout, (dict, list)):\n"
    "                st.json(tout)\n"
    "            elif isinstance(tout, str):\n"
    "                try:\n"
    "                    parsed = json.loads(tout)\n"
    "                    if isinstance(parsed, (dict, list)):\n"
    "                        st.json(parsed)\n"
    "                    else:\n"
    "                        st.code(str(parsed))\n"
    "                except (json.JSONDecodeError, TypeError):\n"
    "                    if len(tout) > 6000:\n"
    "                        st.code(tout[:6000] + '\\n\\u2026(truncated)')\n"
    "                    else:\n"
    "                        st.code(tout)\n"
    "            else:\n"
    "                st.code(str(tout))\n"
    "        else:\n"
    "            _render_input_fallback(attrs, 'output.value')\n"
    "\n"
)
src = src[:io_start] + new_io + src[io_end:]
print("Phase 6: IO side-by-side")


open(p, "w", encoding="utf-8", newline="\n").write(src)
print("Bytes written:", len(src.encode("utf-8")))