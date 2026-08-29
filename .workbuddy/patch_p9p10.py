# -*- coding: utf-8 -*-
"""Phase 9+10: rewrite _build_mermaid and _render_mermaid_html."""
import sys
sys.stdout.reconfigure(encoding="utf-8")

p = r"D:\my-projects\agent-monitor\viewer.py"
content = open(p, encoding="utf-8").read()


# ============================================================
# Replace _build_mermaid
# ============================================================
NEW_BUILD = '''def _build_mermaid(spans, *, focus=None, hops=2):
    """Build a Mermaid `flowchart LR` source. With focus, render a 2-hop subgraph.

    Nodes are emitted in start_time order so Mermaid's LR layout flows
    left-to-right in time.  Each node label carries a t+<ms> relative
    timestamp.  Parallel branches (>=2 children starting within 5ms of
    each other) are wrapped in subgraph groups.
    """
    if not spans:
        return "flowchart LR\\n    empty[\\u3000\\uff08\\u65e0 span\\uff09\\u3000]"
    spans_by_id = {s["span_id"]: s for s in spans}

    # Determine visible set (focus mode: 2-hop neighborhood)
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

    # Too many nodes: fold
    if len(visible_spans) > _MERMAID_MAX_NODES and not focus:
        return (
            "flowchart LR\\n"
            "    root[<\\u3000\\u5171 " + str(len(spans)) + " \\u4e2a span\\u3000<br/>"
            "<small>\\u8282\\u70b9\\u6570\\u8fc7\\u591a\\uff0c\\u8bf7\\u5207\\u56de \\u5217\\u8868 \\u6a21\\u5f0f\\u67e5\\u770b</small>]\\n"
            "    classDef root fill:#4b5563,color:#fff,stroke:#1f2937;\\n"
            "    class root root;"
        )

    # Sort by start_time so Mermaid LR flows in time order
    visible_spans.sort(key=lambda s: int(s.get("start_time", 0)))

    # Compute trace-start for relative timestamps
    starts = [int(s.get("start_time", 0)) for s in visible_spans]
    min_start = min(starts) if starts else 0

    out = ["flowchart LR"]
    # Class definitions
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

    # Group children by parent for parallel-branch detection
    children_by_parent = {}
    for s in visible_spans:
        pid = s.get("parent_span_id")
        if pid and pid in visible:
            children_by_parent.setdefault(pid, []).append(s)

    # Render nodes (with t+<ms> annotation)
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
        # Build label with time annotation
        start_ns = int(span.get("start_time", 0))
        offset_ms = int((start_ns - min_start) / 1_000_000)
        label = _mermaid_label(span)
        # Append t+<ms>
        full_label = f"{label}<br/><small>t+{offset_ms}ms</small>"
        # Escape for mermaid syntax: strip brackets/parens/backticks/pipes
        safe = re.sub(r"[\\[\\](){}<>|`]", " ", full_label).strip()
        out.append(f'    {nid}["{safe}"]')
        out.append(f"    class {nid} {','.join(cls)};")

    # Group parallel children in subgraphs
    for parent_id, kids in children_by_parent.items():
        if len(kids) < 2:
            continue
        # Sort by start time
        kids.sort(key=lambda s: int(s.get("start_time", 0)))
        # Check if any pair starts within 5ms
        starts_k = [int(k.get("start_time", 0)) / 1_000_000 for k in kids]
        is_parallel = False
        for i in range(len(starts_k) - 1):
            if abs(starts_k[i + 1] - starts_k[i]) <= 5:
                is_parallel = True
                break
        if is_parallel:
            pnid = _mermaid_safe_id(parent_id)
            out.append(f"    subgraph SG_{pnid}[\\""])
            sub.append("    direction LR")
            for k in kids:
                out.append(f"        {_mermaid_safe_id(k['span_id'])}")
            out.append("    end")

    # Render edges (parent->child)
    for span in visible_spans:
        pid = span.get("parent_span_id")
        if pid and pid in visible:
            out.append(f"    {_mermaid_safe_id(pid)} --> {_mermaid_safe_id(span['span_id'])}")

    # Mermaid native click directives (most reliable click handling)
    for span in visible_spans:
        nid = _mermaid_safe_id(span["span_id"])
        out.append(f"    click {nid} focusSpan")

    return "\\n".join(out)


'''

# Find and replace
import re
m = re.search(
    r'def _build_mermaid\(spans, \*, focus=None, hops=2\):.*?(?=\n\n\ndef )',
    content,
    re.DOTALL,
)
if m:
    old = m.group(0)
    content = content.replace(old, NEW_BUILD, 1)
    print("Phase 9a: _build_mermaid replaced; old len:", len(old), "new len:", len(NEW_BUILD))
else:
    print("Phase 9a: _build_mermaid pattern not found")


# ============================================================
# Replace _render_mermaid_html (add window.focusSpan + selectbox fallback later)
# ============================================================
NEW_RENDER = '''def _render_mermaid_html(src, *, height=620, key_prefix="m"):
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
        "    // nodeId looks like n_<span_id_with_underscores>\\n"
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
        "    // Backup DOM event delegation (Mermaid native click is primary)\\n"
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

m = re.search(
    r'def _render_mermaid_html\(src, \*, height=620, key_prefix="m"\):.*?(?=\n\n\ndef )',
    content,
    re.DOTALL,
)
if m:
    old = m.group(0)
    content = content.replace(old, NEW_RENDER, 1)
    print("Phase 9b: _render_mermaid_html replaced")
else:
    print("Phase 9b: _render_mermaid_html pattern not found")


open(p, "w", encoding="utf-8", newline="\n").write(content)
print("Bytes:", len(content.encode("utf-8")))