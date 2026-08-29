# -*- coding: utf-8 -*-
"""Apply ALL viewer.py changes via line-based surgery."""
import sys
sys.stdout.reconfigure(encoding="utf-8")

p = r"D:\my-projects\agent-monitor\viewer.py"
with open(p, encoding="utf-8") as f:
    lines = f.read().splitlines(keepends=False)
print("Total lines:", len(lines))

# Helper: replace lines [start, end] (1-indexed inclusive) with new_lines (list of strings without \n)
def repl(start, end, new_lines, label):
    s = start - 1
    e = end  # exclusive
    old_count = e - s
    new_count = len(new_lines)
    print(f"  L{start}-L{end} ({old_count} lines) -> {new_count} lines: {label}")
    lines[s:e] = new_lines

# === Step 1: CSS additions ===
# 1a) Before "/* ----- right metadata panel ----- */" at L178, insert trace-card CSS
trace_card_css = [
    "/* ----- trace card list (flowchart explorer left column) ----- */",
    ".trace-card {",
    "    background: rgba(255,255,255,0.03);",
    "    border: 1px solid rgba(255,255,255,0.08);",
    "    border-radius: 8px;",
    "    padding: 6px 8px;",
    "    margin-bottom: 6px;",
    "}",
    ".trace-card-active {",
    "    border-color: rgba(59,130,246,0.55);",
    "    background: rgba(59,130,246,0.10);",
    "}",
    "",
]
# Find the actual line
for i, l in enumerate(lines):
    if "/* ----- right metadata panel -----" in l:
        target = i + 1  # 1-indexed
        break
# Insert before this line by appending the CSS block to lines[target-1]
# Actually easier: split the line and re-insert
old_line = lines[target - 1]
new_lines = trace_card_css + [old_line]
repl(target, target, new_lines, "trace-card CSS inserted before right meta panel CSS")

# 1b) L311: change max-height: 6em to 18em + add msg-meta + msg-part-block + cursor:pointer
# Find it
for i, l in enumerate(lines):
    if "max-height: 6em" in l:
        target = i + 1
        break
old_msg_body = lines[target - 1]
# Replace with new content
repl(target, target, [
    "    max-height: 18em;",
    "    overflow-y: auto;",
    "    overflow-wrap: anywhere;",
    "    word-break: break-word;",
    "    padding: 6px 10px 8px 10px;",
    "    margin: 0;",
    "    font-size: 12.5px;",
    "    line-height: 1.45;",
    "    color: #d1d5db;",
    "}",
    ".msg-card .msg-meta {",
    "    padding: 3px 10px;",
    "    font-size: 10.5px;",
    "    color: #9ca3af;",
    "    background: rgba(255,255,255,0.02);",
    "    border-bottom: 1px solid rgba(255,255,255,0.05);",
    "}",
    ".msg-card .msg-part-block {",
    "    margin: 6px 0;",
    "    padding: 6px 8px;",
    "    border-left: 2px solid rgba(59,130,246,0.5);",
    "    background: rgba(59,130,246,0.06);",
    "    border-radius: 0 4px 4px 0;",
    "    font-size: 11.5px;",
    "}",
    ".mermaid .nodeLabel, .mermaid .node rect, .mermaid .node polygon {",
    "    cursor: pointer;",
    "}",
], "msg-body CSS expanded + meta + part-block + cursor")


# === Step 2: Delete expanded_spans init (L680) ===
# Find "st.session_state.setdefault(\"expanded_spans\""
for i, l in enumerate(lines):
    if 'st.session_state.setdefault("expanded_spans"' in l:
        target = i + 1
        break
repl(target, target, [], "expanded_spans init deleted")


# === Step 3: All small string translations (do these BEFORE major restructuring) ===
# These are unique-string-line replacements
single_line_replacements = [
    # L1: title
    ('## \U0001F50E Agent Trace Monitor  `v3-3col`', '## \U0001F50E Agent \u94fe\u8def\u76d1\u63a7  `v3-3col`'),
    # L14/L15 etc
    ('  - RunnableParallel<tools...>  -> "Parallel Search (n)"', '  - RunnableParallel<tools...>  -> "\u591a\u4efb\u52a1\u5e76\u884c\uff08n\uff09"'),
    ('  - RunnableSequence with TOOL child spans -> "Tool Agent"', '  - RunnableSequence with TOOL child spans -> "\u5de5\u5177\u578b\u667a\u80fd\u4f53"'),
    ('  - RunnableSequence with RETRIEVER child spans -> "Retrieval Chain"', '  - RunnableSequence with RETRIEVER child spans -> "\u68c0\u7d22\u94fe"'),
    ('  - RunnableSequence (Prompt -> LLM -> Parser) -> "LLM Chain"', '  - RunnableSequence (Prompt -> LLM -> Parser) -> "LLM \u8c03\u7528\u94fe"'),
    ('  - RunnableSequence (just LLM) -> "LLM Call"', '  - RunnableSequence (just LLM) -> "\u5927\u6a21\u578b\u8c03\u7528"'),
    # L767 Trace source
    ('"Trace source"', '"\u6570\u636e\u6e90"'),
    # L1112 Click a node in the tree
    ('Click a node in the tree to inspect it.', '\u8bf7\u5728\u5de6\u4fa7\u6811\u4e2d\u9009\u4e2d\u4e00\u4e2a\u8282\u70b9\u67e5\u770b\u8be6\u60c5\u3002'),
    # L1147 Tabs
    ('st.tabs(["Run", "Feedback", "Metadata"])', 'st.tabs(["\u8fd0\u884c", "\u53cd\u9988", "\u5143\u6570\u636e"])'),
    # L1209 Input block section (we'll replace with side-by-side anyway)
    # L1211 Input expander
    ('"\u2b07  Input"', '"\u2b07  \u8f93\u5165"'),
    # L1227 Tool arguments
    ('"**Tool arguments:**"', '"**\u5de5\u5177\u53c2\u6570\uff1a**"'),
    # L1229 no parameters
    ('"(no parameters captured)"', '"\uff08\u672a\u6355\u83b7\u53c2\u6570\uff09"'),
    # L1240 Output block (will be replaced)
    # L1242 Output expander
    ('"\u2b06  Output"', '"\u2b06  \u8f93\u51fa"'),
    # L1254 no result
    ('"(no result captured)"', '"\uff08\u672a\u6355\u83b7\u8fd4\u56de\u7ed3\u679c\uff09"'),
    # L1277-1281 token labels
    ('("Input tokens",      canon(attrs, "tokens.input"))', '("\u8f93\u5165 token",      canon(attrs, "tokens.input"))'),
    ('("Output tokens",     canon(attrs, "tokens.output"))', '("\u8f93\u51fa token",     canon(attrs, "tokens.output"))'),
    ('("Total tokens",      canon(attrs, "tokens.total"))', '("\u603b\u8ba1 token",      canon(attrs, "tokens.total"))'),
    ('("Cache read tokens", canon(attrs, "tokens.cache_read"))', '("\u7f13\u5b58\u8bfb\u53d6 token", canon(attrs, "tokens.cache_read"))'),
    ('("Reasoning tokens",  canon(attrs, "tokens.reasoning"))', '("\u601d\u8003 token",  canon(attrs, "tokens.reasoning"))'),
    # L1292 Flow state
    ('"Flow state ({len(events)} event(s))"', '"\u6d41\u7a0b\u4e8b\u4ef6\uff08{len(events)} \u6761\uff09"'),
    # L1296 no events
    ('"(no span events recorded)"', '"\uff08\u672a\u8bb0\u5f55 span \u4e8b\u4ef6\uff09"'),
    # L1316 Error
    ('"#### \u26a0 Error"', '"#### \u26a0 \u9519\u8bef"'),
    # L1328 Stack trace
    ('"**Stack trace:**"', '"**\u5806\u6808\u4fe1\u606f\uff1a**"'),
    # L1374 Feedback no feedback
    ('No feedback recorded yet.', '\u5c1a\u672a\u8bb0\u5f55\u53cd\u9988\u5206\u6570\u3002'),
    # L1376 Once you score
    ('Once you score this run, scores will appear here automatically.', '\u4e00\u65e6\u5bf9\u8be5\u8fd0\u884c\u8bc4\u5206\uff0c\u5206\u6570\u4f1a\u81ea\u52a8\u51fa\u73b0\u5728\u8fd9\u91cc\u3002'),
    # L1403 Identity
    ('"Identity</div>"', '"\u57fa\u672c\u4fe1\u606f</div>"'),
    # L1409 Parent
    ('("Parent Span ID", span.get("parent_span_id") or "(root)")', '("\u7236 Span ID", span.get("parent_span_id") or "(\u6839 span)")'),
    # L1410 Service span
    ('("Service", span.get("service_name") or "-")', '("\u670d\u52a1", span.get("service_name") or "-")'),
    # L1411 Schema
    ('("Schema ver", str(span.get("schema_version", "-")))', '("\u6cd5\u6848\u7248\u672c", str(span.get("schema_version", "-")))'),
    # L1420 Session
    ('("Session / Thread", sid)', '("\u4f1a\u8bdd / \u4e3b\u9898", sid)'),
    # L1422 User
    ('("User", uid)', '("\u7528\u6237", uid)'),
    # L1427 Tags joined
    ('rows.append(("Tags", ", ".join(str(t) for t in tags)))', 'rows.append(("\u6807\u7b7e", ", ".join(str(t) for t in tags)))'),
    # L1429 Tags str
    ('("Tags", str(tags))', '("\u6807\u7b7e", str(tags))'),
    # L1442 Duration
    ('("Duration", _format_duration_ms(dur_ms))', '("\u603b\u65f6\u957f", _format_duration_ms(dur_ms))'),
    # L1449 All attrs
    ('"All attributes (filtered)</div>"', '"\u5168\u90e8\u5c5e\u6027\uff08\u8fc7\u6ee4\u540e\uff09</div>"'),
    # L1459 Span events
    ('"Span events</div>"', '"Span \u4e8b\u4ef6</div>"'),
    # L1477 Service kpi
    ('("Service", trace_kpi.service_name or "-")', '("\u670d\u52a1", trace_kpi.service_name or "-")'),
    # L1478 Span count
    ('("Span count", str(trace_kpi.n_spans))', '("Span \u6570\u91cf", str(trace_kpi.n_spans))'),
    # L1482 LLM/Tool
    ('("LLM / Tool", f"{trace_kpi.n_llm} / {trace_kpi.n_tool}")', '("\u5927\u6a21\u578b\u8c03\u7528 / \u5de5\u5177", f"{trace_kpi.n_llm} / {trace_kpi.n_tool}")'),
    # L1483 Chain/Agent
    ('("Chain / Agent / Prompt",', '("\u94fe\u8def / \u667a\u80fd\u4f53 / \u63d0\u793a\u8bcd",'),
    # L1503 Tokens
    ('<div class="meta-section"><h5>Tokens</h5>', '<div class="meta-section"><h5>Token</h5>'),
    # L1521 no token
    ('<div style="color:#6b7280;font-size:11.5px">no token data captured</div>', '<div style="color:#6b7280;font-size:11.5px">\u672a\u6355\u83b7 token \u6570\u636e</div>'),
    # L1528 Cost
    ('<div class="meta-section"><h5>Cost (est.)</h5>', '<div class="meta-section"><h5>\u6210\u672c\uff08\u4f30\u8ba1\uff09</h5>'),
    # L1549 Selected
    ('<div class="meta-section"><h5>Selected span</h5>', '<div class="meta-section"><h5>\u9009\u4e2d\u7684 Span</h5>'),
    # L1554 click tree
    ('<div style="color:#6b7280;font-size:11.5px">click a tree node</div>', '<div style="color:#6b7280;font-size:11.5px">\u8bf7\u5728\u5de6\u4fa7\u6811\u4e2d\u9009\u62e9\u4e00\u4e2a span</div>'),
    # L1583 Name
    ('("Name", name)', '("\u540d\u79f0", name)'),
    # L1584 Kind
    ('("Kind", kind)', '("\u7c7b\u578b", kind)'),
    # L1589 Latency
    ('("Latency", _format_duration_ms(dur_ms))', '("\u8017\u65f6", _format_duration_ms(dur_ms))'),
    # L1617 In/Out
    ('<div class="k">In / Out</div>', '<div class="k">\u8f93\u5165 / \u8f93\u51fa</div>'),
    # L1636 No spans
    ('"No spans in the current trace. Run your agent and refresh."', '"\u5f53\u524d trace \u4e2d\u6ca1\u6709 span\uff0c\u8bf7\u8fd0\u884c\u4f60\u7684 agent \u540e\u5237\u65b0\u3002"'),
    # L1647 Nav Tree
    ('"#### \U0001F5C2 Navigation Tree "', '"#### \U0001F5C2 \u5bfc\u822a\u6811 "'),
    # L755 drop "Run" tab "Feedback" tab "Metadata" tab  - no just tabs array
    # ico = "red cross" / "green tick" / "hourglass" comments at L738-741
    ('ico = "\u274c"  # red cross', 'ico = "\u274c"  # \u7ea2\u8272\u53c9\uff08\u9519\u8bef\uff09'),
    ('ico = "\u2705"  # green tick', 'ico = "\u2705"  # \u7eff\u8272\u52fe\uff08\u6210\u529f\uff09'),
    ('ico = "\u23f3"  # hourglass (UNSET / in-progress)', 'ico = "\u23f3"  # \u6c99\u6f0f\uff08\u672a\u5b8c\u6210\uff09'),
    # Drop _trace_label comments
    ('  - RunnableParallel<tools...>  -> "Parallel Search (n)"', '  - RunnableParallel<tools...>  -> "\u591a\u4efb\u52a1\u5e76\u884c\uff08n\uff09"'),
]

print("\n=== Step 3: Single-line translations ===")
missed = []
for old, new in single_line_replacements:
    # Find in lines (with or without \r at end since splitlines strips them)
    found = False
    for i, l in enumerate(lines):
        if old in l:
            lines[i] = l.replace(old, new)
            found = True
            break
    if found:
        print(f"  OK  {old[:50]}")
    else:
        missed.append(old[:50])
        print(f"  MISSING  {old[:50]}")

print(f"\nMissed: {len(missed)}")


# Save
with open(p, "w", encoding="utf-8", newline="\n") as f:
    f.write("\n".join(lines) + "\n")
print(f"\nAfter Step 1-3: {sum(len(l) for l in lines)} chars (excl. newlines)")