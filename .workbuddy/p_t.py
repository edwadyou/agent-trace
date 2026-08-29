# -*- coding: utf-8 -*-
"""Translations."""
import sys
sys.stdout.reconfigure(encoding="utf-8")
p = r"D:\my-projects\agent-monitor\viewer.py"
with open(p, encoding="utf-8") as f:
    lines = f.read().splitlines(keepends=False)

TRANSLATIONS = [
    ("## \U0001F50E Agent Trace Monitor  `v3-3col`", "## \U0001F50E Agent \u94fe\u8def\u76d1\u63a7  `v3-3col`"),
    ("  - RunnableParallel<tools...>  -> \"Parallel Search (n)\"", "  - RunnableParallel<tools...>  -> \"\u591a\u4efb\u52a1\u5e76\u884c\uff08n\uff09\""),
    ("  - RunnableSequence with TOOL child spans -> \"Tool Agent\"", "  - RunnableSequence with TOOL child spans -> \"\u5de5\u5177\u578b\u667a\u80fd\u4f53\""),
    ("  - RunnableSequence with RETRIEVER child spans -> \"Retrieval Chain\"", "  - RunnableSequence with RETRIEVER child spans -> \"\u68c0\u7d22\u94fe\""),
    ("  - RunnableSequence (Prompt -> LLM -> Parser) -> \"LLM Chain\"", "  - RunnableSequence (Prompt -> LLM -> Parser) -> \"LLM \u8c03\u7528\u94fe\""),
    ("  - RunnableSequence (just LLM) -> \"LLM Call\"", "  - RunnableSequence (just LLM) -> \"\u5927\u6a21\u578b\u8c03\u7528\""),
    ("\"Trace source\"", "\"\u6570\u636e\u6e90\""),
    ("Click a node in the tree to inspect it.", "\u8bf7\u5728\u5de6\u4fa7\u6811\u4e2d\u9009\u4e2d\u4e00\u4e2a\u8282\u70b9\u67e5\u770b\u8be6\u60c5\u3002"),
    ("st.tabs([\"Run\", \"Feedback\", \"Metadata\"])", "st.tabs([\"\u8fd0\u884c\", \"\u53cd\u9988\", \"\u5143\u6570\u636e\"])"),
    ("\"\u2b07  Input\"", "\"\u2b07  \u8f93\u5165\""),
    ("\"**Tool arguments:**\"", "\"**\u5de5\u5177\u53c2\u6570\uff1a**\""),
    ("(no parameters captured)", "\uff08\u672a\u6355\u83b7\u53c2\u6570\uff09"),
    ("\"\u2b06  Output\"", "\"\u2b06  \u8f93\u51fa\""),
    ("(no result captured)", "\uff08\u672a\u6355\u83b7\u8fd4\u56de\u7ed3\u679c\uff09"),
    ("(\"Input tokens\",      canon(attrs, \"tokens.input\"))", "(\"\u8f93\u5165 token\",      canon(attrs, \"tokens.input\"))"),
    ("(\"Output tokens\",     canon(attrs, \"tokens.output\"))", "(\"\u8f93\u51fa token\",     canon(attrs, \"tokens.output\"))"),
    ("(\"Total tokens\",      canon(attrs, \"tokens.total\"))", "(\"\u603b\u8ba1 token\",      canon(attrs, \"tokens.total\"))"),
    ("(\"Cache read tokens\", canon(attrs, \"tokens.cache_read\"))", "(\"\u7f13\u5b58\u8bfb\u53d6 token\", canon(attrs, \"tokens.cache_read\"))"),
    ("(\"Reasoning tokens\",  canon(attrs, \"tokens.reasoning\"))", "(\"\u601d\u8003 token\",  canon(attrs, \"tokens.reasoning\"))"),
    ("\"Flow state ({len(events)} event(s))\"", "\"\u6d41\u7a0b\u4e8b\u4ef6\uff08{len(events)} \u6761\uff09\""),
    ("(no span events recorded)", "\uff08\u672a\u8bb0\u5f55 span \u4e8b\u4ef6\uff09"),
    ("#### \u26a0 Error", "#### \u26a0 \u9519\u8bef"),
    ("**Stack trace:**", "**\u5806\u6808\u4fe1\u606f\uff1a**"),
    ("No feedback recorded yet.", "\u5c1a\u672a\u8bb0\u5f55\u53cd\u9988\u5206\u6570\u3002"),
    ("Once you score this run, scores will appear here automatically.", "\u4e00\u65e6\u5bf9\u8be5\u8fd0\u884c\u8bc4\u5206\uff0c\u5206\u6570\u4f1a\u81ea\u52a8\u51fa\u73b0\u5728\u8fd9\u91cc\u3002"),
    ("Identity</div>", "\u57fa\u672c\u4fe1\u606f</div>"),
    ("(\"Parent Span ID\", span.get(\"parent_span_id\") or \"(root)\")", "(\"\u7236 Span ID\", span.get(\"parent_span_id\") or \"(\u6839 span)\")"),
    ("(\"Service\", span.get(\"service_name\") or \"-\")", "(\"\u670d\u52a1\", span.get(\"service_name\") or \"-\")"),
    ("(\"Schema ver\", str(span.get(\"schema_version\", \"-\")))", "(\"\u6cd5\u6848\u7248\u672c\", str(span.get(\"schema_version\", \"-\")))"),
    ("(\"Session / Thread\", sid)", "(\"\u4f1a\u8bdd / \u4e3b\u9898\", sid)"),
    ("(\"User\", uid)", "(\"\u7528\u6237\", uid)"),
    ("rows.append((\"Tags\", \", \".join(str(t) for t in tags)))", "rows.append((\"\u6807\u7b7e\", \", \".join(str(t) for t in tags)))"),
    ("(\"Tags\", str(tags))", "(\"\u6807\u7b7e\", str(tags))"),
    ("(\"Duration\", _format_duration_ms(dur_ms))", "(\"\u603b\u65f6\u957f\", _format_duration_ms(dur_ms))"),
    ("All attributes (filtered)</div>", "\u5168\u90e8\u5c5e\u6027\uff08\u8fc7\u6ee4\u540e\uff09</div>"),
    ("Span events</div>", "Span \u4e8b\u4ef6</div>"),
    ("(\"Service\", trace_kpi.service_name or \"-\")", "(\"\u670d\u52a1\", trace_kpi.service_name or \"-\")"),
    ("(\"Span count\", str(trace_kpi.n_spans))", "(\"Span \u6570\u91cf\", str(trace_kpi.n_spans))"),
    ("(\"LLM / Tool\", f\"{trace_kpi.n_llm} / {trace_kpi.n_tool}\")", "(\"\u5927\u6a21\u578b\u8c03\u7528 / \u5de5\u5177\", f\"{trace_kpi.n_llm} / {trace_kpi.n_tool}\")"),
    ("(\"Chain / Agent / Prompt\",", "(\"\u94fe\u8def / \u667a\u80fd\u4f53 / \u63d0\u793a\u8bcd\","),
    ("<div class=\"meta-section\"><h5>Tokens</h5>", "<div class=\"meta-section\"><h5>Token</h5>"),
    ("<div style=\"color:#6b7280;font-size:11.5px\">no token data captured</div>", "<div style=\"color:#6b7280;font-size:11.5px\">\u672a\u6355\u83b7 token \u6570\u636e</div>"),
    ("<div class=\"meta-section\"><h5>Cost (est.)</h5>", "<div class=\"meta-section\"><h5>\u6210\u672c\uff08\u4f30\u8ba1\uff09</h5>"),
    ("<div class=\"meta-section\"><h5>Selected span</h5>", "<div class=\"meta-section\"><h5>\u9009\u4e2d\u7684 Span</h5>"),
    ("<div style=\"color:#6b7280;font-size:11.5px\">click a tree node</div>", "<div style=\"color:#6b7280;font-size:11.5px\">\u8bf7\u5728\u5de6\u4fa7\u6811\u4e2d\u9009\u62e9\u4e00\u4e2a span</div>"),
    ("(\"Name\", name)", "(\"\u540d\u79f0\", name)"),
    ("(\"Kind\", kind)", "(\"\u7c7b\u578b\", kind)"),
    ("(\"Latency\", _format_duration_ms(dur_ms))", "(\"\u8017\u65f6\", _format_duration_ms(dur_ms))"),
    ("<div class=\"k\">In / Out</div>", "<div class=\"k\">\u8f93\u5165 / \u8f93\u51fa</div>"),
    ("No spans in the current trace. Run your agent and refresh.", "\u5f53\u524d trace \u4e2d\u6ca1\u6709 span\uff0c\u8bf7\u8fd0\u884c\u4f60\u7684 agent \u540e\u5237\u65b0\u3002"),
    ("#### \U0001F5C2 Navigation Tree ", "#### \U0001F5C2 \u5bfc\u822a\u6811 "),
    ("ico = \"\u274c\"  # red cross", "ico = \"\u274c\"  # \u7ea2\u8272\u53c9\uff08\u9519\u8bef\uff09"),
    ("ico = \"\u2705\"  # green tick", "ico = \"\u2705\"  # \u7eff\u8272\u52fe\uff08\u6210\u529f\uff09"),
    ("ico = \"\u23f3\"  # hourglass (UNSET / in-progress)", "ico = \"\u23f3\"  # \u6c99\u6f0f\uff08\u672a\u5b8c\u6210\uff09"),
]

for i, l in enumerate(lines):
    for old, new in TRANSLATIONS:
        if old in l:
            lines[i] = l.replace(old, new)
            break

with open(p, "w", encoding="utf-8", newline="\n") as f:
    f.write("\n".join(lines) + "\n")
print("T1 done:", len(lines), "lines")
