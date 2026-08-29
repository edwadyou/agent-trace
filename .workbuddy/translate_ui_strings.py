"""Translate UI strings in viewer.py to Simplified Chinese.

Reads viewer.py, applies an ordered list of literal substring
substitutions, reports HIT/miss/skip per rule, writes the file back
as UTF-8 (no BOM), then py_compile-checks the result.
"""
from pathlib import Path
import py_compile

SRC = Path(r"D:\my-projects\agent-monitor\viewer.py")


RULES = [
    # Header title (line 755)
    ("## \U0001F50E Agent Trace Monitor  `v3-3col`",
     "## \U0001F50E Agent \u8fd0\u884c\u76d1\u63a7  `v3-3col`"),

    # Tabs (line 1147)
    ('st.tabs(["Run", "Feedback", "Metadata"])',
     'st.tabs(["\u8fd0\u884c", "\u53cd\u9988", "\u5143\u6570\u636e"])'),

    # Error block heading (line 1316)
    ("#### \u26a0 Error",
     "#### \u26a0 \u9519\u8bef"),

    # Stack trace label (line 1328)
    ("**Stack trace:**",
     "**\u5806\u6808\u4fe1\u606f\uff1a**"),

    # Span Detail header (line 1669)
    ("#### \U0001F50D Span Detail",
     "#### \U0001F50D Span \u8be6\u60c5"),

    # Metadata right panel header (line 1677)
    ("#### \U0001F4CA Metadata",
     "#### \U0001F4CA \u5143\u6570\u636e\u9762\u677f"),

    # Navigation Tree header (line 1647)
    ("#### \U0001F5BB Navigation Tree ",
     "#### \U0001F5BB \u5bfc\u822a\u6811 "),

    # Trace source selectbox label (line 766)
    ('"Trace source"',
     '"\u6570\u636e\u6e90"'),

    # Run tab expander labels
    ('\u2b07  Input',
     '\u2b07  \u8f93\u5165'),
    ('\u2b06  Output',
     '\u2b06  \u8f93\u51fa'),
    ('**Tool arguments:**',
     '**\u5de5\u5177\u53c2\u6570\uff1a**'),
    ("(no parameters captured)",
     "\uff08\u672a\u6355\u83b7\u53c2\u6570\uff09"),
    ("(no result captured)",
     "\uff08\u672a\u6355\u83b7\u8fd4\u56de\u7ed3\u679c\uff09"),
    ("(no span events recorded)",
     "\uff08\u672a\u8bb0\u5f55 span \u4e8b\u4ef6\uff09"),

    # Flow state expander label template
    ('f"\U0001F514? Flow state ({len(events)} event(s))"',
     'f"\U0001F514 \u6d41\u7a0b\u4e8b\u4ef6\uff08{len(events)} \u6761\uff09"'),

    # Identity / Timing / Attributes / Span events detail-card heads (HTML)
    ('<div class="detail-head">Identity</div>',
     '<div class="detail-head">\u57fa\u672c\u4fe1\u606f</div>'),
    ('<div class="detail-head">Timing</div>',
     '<div class="detail-head">\u65f6\u95f4\u4fe1\u606f</div>'),
    ('<div class="detail-head">All attributes (filtered)</div>',
     '<div class="detail-head">\u5168\u90e8\u5c5e\u6027\uff08\u8fc7\u6ee4\u540e\uff09</div>'),
    ('<div class="detail-head">Span events</div>',
     '<div class="detail-head">Span \u4e8b\u4ef6</div>'),

    # Right-panel meta-section headers
    ('<div class="meta-section"><h5>Tokens</h5>',
     '<div class="meta-section"><h5>Token</h5>'),
    ('<div class="meta-section"><h5>Cost (est.)</h5>',
     '<div class="meta-section"><h5>\u6210\u672c\uff08\u4f30\u8ba1\uff09</h5>'),
    ('<div class="meta-section"><h5>Selected span</h5>',
     '<div class="meta-section"><h5>\u9009\u4e2d\u7684 Span</h5>'),

    # Metadata panel empty state messages
    ('<div style="color:#6b7280;font-size:11.5px">no token data captured</div>',
     '<div style="color:#6b7280;font-size:11.5px">\u672a\u6355\u83b7 token \u6570\u636e</div>'),
    ('<div style="color:#6b7280;font-size:11.5px">click a tree node</div>',
     '<div style="color:#6b7280;font-size:11.5px">\u8bf7\u5728\u5de6\u4fa7\u6811\u4e2d\u9009\u62e9\u4e00\u4e2a span</div>'),

    # Metadata right panel KV row labels (line ~1477-1483)
    ('("Service", trace_kpi.service_name or "-")',
     '("\u670d\u52a1", trace_kpi.service_name or "-")'),
    ('("Span count", str(trace_kpi.n_spans))',
     '("Span \u6570\u91cf", str(trace_kpi.n_spans))'),
    ('("LLM / Tool", f"{trace_kpi.n_llm} / {trace_kpi.n_tool}")',
     '("\u5927\u6a21\u578b\u8c03\u7528 / \u5de5\u5177", f"{trace_kpi.n_llm} / {trace_kpi.n_tool}")'),
    ('("Chain / Agent / Prompt",\n                       f"{trace_kpi.n_chain} / {trace_kpi.n_agent} / {trace_kpi.n_prompt}")',
     '("\u94fe\u8def / \u667a\u80fd\u4f53 / \u63d0\u793a\u8bcd",\n                       f"{trace_kpi.n_chain} / {trace_kpi.n_agent} / {trace_kpi.n_prompt}")'),

    # Empty state messages
    ('No spans in the current trace. Run your agent and refresh.',
     '\u5f53\u524d trace \u4e2d\u6ca1\u6709 span\uff0c\u8bf7\u8fd0\u884c\u4f60\u7684 agent \u540e\u5237\u65b0\u3002'),

    # Detail-card "Click a node" empty state (line 1108 - HTML)
    ('<div class="detail-card" style="text-align:center;color:#9ca3af;\'\n            \'padding:36px 16px;">\'\n            \'<div style="font-size:34px;">\U0001F61F</div>\'\n            \'<div style="margin-top:6px;">Click a node in the tree to inspect it.</div>',
     '<div class="detail-card" style="text-align:center;color:#9ca3af;\'\n            \'padding:36px 16px;">\'\n            \'<div style="font-size:34px;">\U0001F61F</div>\'\n            \'<div style="margin-top:6px;">\u8bf7\u5728\u5de6\u4fa7\u6811\u4e2d\u9009\u4e2d\u4e00\u4e2a\u8282\u70b9\u67e5\u770b\u8be6\u60c5\u3002</div>'),

    # Feedback tab empty state (line 1349)
    ('<div style="margin-top:6px;">No feedback recorded yet.</div>',
     '<div style="margin-top:6px;">\u5c1a\u672a\u8bb0\u5f55\u53cd\u9988\u5206\u6570\u3002</div>'),
    ('Once you score this run, scores will appear here automatically.',
     '\u4e00\u65e6\u5bf9\u8be5\u8fd0\u884c\u8bc4\u5206\uff0c\u5206\u6570\u4f1a\u81ea\u52a8\u51fa\u73b0\u5728\u8fd9\u91cc\u3002'),

    # Metadata Identity KV labels (rows list, lines ~1407-1429)
    ('("Trace ID", span.get("trace_id", ""))',
     '("Trace ID", span.get("trace_id", ""))'),
    ('("Span ID", span.get("span_id", ""))',
     '("Span ID", span.get("span_id", ""))'),
    ('("Parent Span ID", span.get("parent_span_id") or "(root)")',
     '("\u7236 Span ID", span.get("parent_span_id") or "(\u6839 span)")'),
    ('("Service", span.get("service_name") or "-")',
     '("\u670d\u52a1", span.get("service_name") or "-")'),
    ('("Schema ver", str(span.get("schema_version", "-")))',
     '("\u6cd5\u6848\u7248\u672c", str(span.get("schema_version", "-")))'),
    ('("Session / Thread", sid)',
     '("\u4f1a\u8bdd / \u4e3b\u9898", sid)'),
    ('("User", uid)',
     '("\u7528\u6237", uid)'),
    ('("Tags", ", ".join(t))',
     '("\u6807\u7b7e", ", ".join(t))'),
    ('("Tags", str(tags))',
     '("\u6807\u7b7e", str(tags))'),

    # Metadata Timing KV labels
    ('("Duration", _format_duration_ms(dur_ms))',
     '("\u603b\u65f6\u957f", _format_duration_ms(dur_ms))'),

    # Right panel metadata "Start/End/Duration/Latency" etc.
    ('("Name", name)',
     '("\u540d\u79f0", name)'),
    ('("Kind", kind)',
     '("\u7c7b\u578b", kind)'),
    ('("Latency", _format_duration_ms(dur_ms))',
     '("\u8017\u65f6", _format_duration_ms(dur_ms))'),
    ('("In / Out",\n                f"{_esc(_format_tokens(tin))} / {_esc(_format_tokens(tout))}")',
     '("\u8f93\u5165 / \u8f93\u51fa",\n                f"{_esc(_format_tokens(tin))} / {_esc(_format_tokens(tout))}")'),

    # Token cost labels in Run tab (line ~1277-1281)
    ('("Input tokens",      canon(attrs, "tokens.input"))',
     '("\u8f93\u5165 token",      canon(attrs, "tokens.input"))'),
    ('("Output tokens",     canon(attrs, "tokens.output"))',
     '("\u8f93\u51fa token",     canon(attrs, "tokens.output"))'),
    ('("Total tokens",      canon(attrs, "tokens.total"))',
     '("\u603b\u8ba1 token",      canon(attrs, "tokens.total"))'),
    ('("Cache read tokens", canon(attrs, "tokens.cache_read"))',
     '("\u7f13\u5b58\u8bfb\u53d6 token", canon(attrs, "tokens.cache_read"))'),
    ('("Reasoning tokens",  canon(attrs, "tokens.reasoning"))',
     '("\u601d\u8003 token",  canon(attrs, "tokens.reasoning"))'),

    # Cost estimation caption (line ~1285 area)
    ('f"\U0001F4B5 estimated cost (this span): **${cost:.4f}**"',
     'f"\U0001F4B5 \u672c span \u4f30\u8ba1\u6210\u672c\uff1a**${cost:.4f}**"'),
]


def _short(s, n=80):
    """Return a one-line, length-bounded preview of the snippet."""
    flat = s.replace("\n", "\\n")
    return flat if len(flat) <= n else flat[: n - 1] + "\u2026"


def main():
    text = SRC.read_text(encoding="utf-8")
    hits = 0
    misses = 0
    skips = 0
    rows = []
    for idx, (old, new) in enumerate(RULES, start=1):
        count = text.count(old)
        if count == 0:
            rows.append((idx, "miss", 0, _short(old)))
            misses += 1
            continue
        text = text.replace(old, new)
        if old == new:
            rows.append((idx, "SKIP", count, _short(old)))
            skips += 1
        else:
            rows.append((idx, "HIT", count, _short(old)))
            hits += 1

    print(f"{'#':>3} {'result':<6} {'n':>3}  snippet")
    print("-" * 80)
    for idx, status, count, snippet in rows:
        print(f"{idx:>3} {status:<6} {count:>3}  {snippet}")
    print("-" * 80)
    print(f"Total: hit={hits} miss={misses} skip={skips}; substitutions={hits}")

    SRC.write_text(text, encoding="utf-8")
    print(f"Wrote {SRC} ({len(text)} chars, UTF-8, no BOM)")

    py_compile.compile(str(SRC), doraise=True)
    print("py_compile: OK")


if __name__ == "__main__":
    main()