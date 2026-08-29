import sys
sys.stdout.reconfigure(encoding="utf-8")
content = open(r"D:\my-projects\agent-monitor\viewer.py", encoding="utf-8").read()
checks = [
    ("flowchart LR", "Mermaid LR direction"),
    ("t+{offset_ms}ms", "time annotation"),
    ("click {nid} focusSpan", "mermaid click directive"),
    ("window.focusSpan", "focusSpan JS function"),
    ("subgraph SG_", "parallel branches subgraph"),
    ("manual_focus_pick", "manual focus selector"),
    ("def _render_msg(msg):", "structured _render_msg"),
    ("msg-meta", "msg-meta CSS class"),
    ("msg-part-block", "msg-part-block CSS class"),
    ("json.loads(val)", "fallback JSON parse"),
    ("flowchart TB", "old TB removed (should be MISS)"),
]
for k, label in checks:
    found = k in content
    if label.startswith("old TB removed"):
        mark = "OK (removed)" if not found else "STILL PRESENT"
    else:
        mark = "OK" if found else "MISSING"
    print("  " + mark + "  " + label)
print("Total bytes:", len(content.encode("utf-8")))