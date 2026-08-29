# -*- coding: utf-8 -*-
"""CSS additions."""
import sys
sys.stdout.reconfigure(encoding="utf-8")
p = r"D:\my-projects\agent-monitor\viewer.py"
with open(p, encoding="utf-8") as f:
    lines = f.read().splitlines(keepends=False)

CSS_TRACE = """/* ----- trace card list (flowchart explorer left column) ----- */
.trace-card {
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 8px;
    padding: 6px 8px;
    margin-bottom: 6px;
}
.trace-card-active {
    border-color: rgba(59,130,246,0.55);
    background: rgba(59,130,246,0.10);
}

/* ----- right metadata panel ----- */""".splitlines()

CSS_MSG = """    max-height: 18em;
    overflow-y: auto;
    overflow-wrap: anywhere;
    word-break: break-word;
    padding: 6px 10px 8px 10px;
    margin: 0;
    font-size: 12.5px;
    line-height: 1.45;
    color: #d1d5db;
}
.msg-card .msg-meta {
    padding: 3px 10px;
    font-size: 10.5px;
    color: #9ca3af;
    background: rgba(255,255,255,0.02);
    border-bottom: 1px solid rgba(255,255,255,0.05);
}
.msg-card .msg-part-block {
    margin: 6px 0;
    padding: 6px 8px;
    border-left: 2px solid rgba(59,130,246,0.5);
    background: rgba(59,130,246,0.06);
    border-radius: 0 4px 4px 0;
    font-size: 11.5px;
}
.mermaid .nodeLabel, .mermaid .node rect, .mermaid .node polygon {
    cursor: pointer;
}""".splitlines()

# Insert trace-card CSS before "/* ----- right metadata panel ----- */"
for i, l in enumerate(lines):
    if "right metadata panel" in l:
        lines[i:i] = CSS_TRACE
        print("Inserted trace-card CSS at L", i+1)
        break

# Replace msg-body CSS at "max-height: 6em" line
for i, l in enumerate(lines):
    if "max-height: 6em" in l:
        lines[i:i+1] = CSS_MSG
        print("Replaced msg-body CSS at L", i+1)
        break

with open(p, "w", encoding="utf-8", newline="\n") as f:
    f.write("\n".join(lines) + "\n")
print("CSS done:", len(lines), "lines")
