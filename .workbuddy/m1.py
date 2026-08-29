# -*- coding: utf-8 -*-
"""Phase 1+2+3 combined: translations + flowchart helpers insertion."""
import sys
sys.stdout.reconfigure(encoding="utf-8")

p = r"D:\my-projects\agent-monitor\viewer.py"
content = open(p, encoding="utf-8").read()

def replace_once(text, old, new, label):
    if old in text:
        text = text.replace(old, new, 1)
        print(f"  [OK] {label}")
    else:
        print(f"  [SKIP] {label}")
    return text


# ===== Phase 1+2: translations =====
T1_RULES = [
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
]
for old, new in T1_RULES:
    content = replace_once(content, old, new, f"T1: {old[:25]}")

T2_RULES = [
    ("## \U0001F50E Agent Trace Monitor  `v3-3col`", "## \U0001F50E Agent \u94fe\u8def\u76d1\u63a7  `v3-3col`"),
    ('st.tabs(["Run", "Feedback", "Metadata"])', 'st.tabs(["\u8fd0\u884c", "\u53cd\u9988", "\u5143\u6570\u636e"])'),
    ("#### \u26a0 Error", "#### \u26a0 \u9519\u8bef"),
    ("**Stack trace:**", "**\u5806\u6808\u4fe1\u606f\uff1a**"),
    ('"Trace source"', '"\u6570\u636e\u6e90"'),
    ("\u2b07  Input", "\u2b07  \u8f93\u5165"),
    ("\u2b06  Output", "\u2b06  \u8f93\u51fa"),
    ("**Tool arguments:**", "**\u5de5\u5177\u53c2\u6570\uff1a**"),
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
]
for old, new in T2_RULES:
    content = replace_once(content, old, new, f"T2: {old[:30]}")

# Save now
open(p, "w", encoding="utf-8", newline="\n").write(content)
print(f"\nAfter Phase 1+2: {len(content.encode('utf-8'))} bytes")