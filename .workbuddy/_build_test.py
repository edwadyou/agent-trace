
import re
SPAN_KINDS = {
    "LLM":       ("\U0001F916", "blue",   "大模型调用"),
    "CHAIN":     ("\U0001F517", "green",  "链路步骤"),
    "TOOL":      ("\U0001F527", "orange", "工具调用"),
    "AGENT":     ("\U0001F9E0", "yellow", "智能体"),
    "RETRIEVER": ("\U0001F4DA", "purple", "检索"),
    "EMBEDDING": ("\U0001F4D0", "cyan",   "向量化"),
    "RERANKER":  ("\U0001F3AF", "violet", "重排序"),
    "PROMPT":    ("\U0001F4DD", "olive",  "填充提示词"),
    "PARSER":    ("\U0001F50D", "gray",   "解析响应"),
    "EVALUATOR": ("\u2696\uFE0F",  "tan",   "评估"),
    "GUARDRAIL": ("\U0001F6E1\uFE0F", "red",    "安全检查"),
    "UNKNOWN":   ("\u2754",   "gray",   "未知"),
}

def span_kind(attrs):
    if not isinstance(attrs, dict): return "UNKNOWN"
    v = attrs.get("openinference.span.kind") or attrs.get("kind")
    if v is None: return "UNKNOWN"
    return str(v).upper()

def canon(attrs, key, default=None):
    return default

def _span_display_name(span):
    return span.get("name", "?")

def _format_duration_ms(ms):
    if ms is None: return "-"
    if ms >= 60000: return f"{ms/60000:.1f}m"
    if ms >= 1000: return f"{ms/1000:.2f}s"
    return f"{ms:.0f}ms"

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


_MERMAID_MAX_NODES = 80
_NODE_LABEL_MAX_CHARS = 60
def _build_mermaid(spans, *, focus=None, hops=2):
    """Build a Mermaid `flowchart TD` source. With focus, render a 2-hop subgraph.

    Nodes are emitted in start_time order so Mermaid's TD layout flows
    top-down in time. Each node label carries a t+<ms> relative timestamp.
    Sequential siblings are chained; concurrent siblings wrapped in subgraph.
    """
    if not spans:
        return "flowchart TD\n    empty[\u3000\uff08\u65e0 span\uff09\u3000]"
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
            "flowchart TD\n"
            "    root[<\u3000\u5171 " + str(len(spans)) + " \u4e2a span\u3000<br/>"
            "<small>\u8282\u70b9\u6570\u8fc7\u591a\uff0c\u8bf7\u5207\u56de \u5217\u8868 \u6a21\u5f0f\u67e5\u770b</small>]\n"
            "    classDef root fill:#4b5563,color:#fff,stroke:#1f2937;\n"
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
        safe = re.sub(r"[\"\\#;|]", " ", full_label).strip()
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
            out.append('    subgraph SG_' + pnid + '["\u5e76\u884c\u5206\u652f"]')
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

    return "\n".join(out)


