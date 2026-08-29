import sys
sys.stdout.reconfigure(encoding="utf-8")
content = open(r"D:\my-projects\agent-monitor\viewer.py", encoding="utf-8").read()
checks_removed = [
    ("view_mode", "view_mode state"),
    ("st.radio(", "streamlit radio widget"),
    ("_render_tree", "tree renderer"),
    ("_render_metadata_panel", "metadata panel fn"),
    ("expanded_spans", "expanded_spans state"),
]
checks_kept = [
    ("_render_flowchart_mode", "flowchart fn"),
    ("_render_detail_panel", "detail panel fn"),
    ("st.query_params", "URL query params"),
    ("st.session_state", "session state (other)"),
    ("flowchart TD", "mermaid TD"),
    ("all_sequential", "chain inference"),
    ("window.focusSpan", "focusSpan JS"),
    ("_render_trace_cards_list", "left col fn"),
    ("_render_flowchart_center", "center col fn"),
    ("_render_detail_column", "right col fn"),
    ("_jump_to_span", "focus setter"),
    ("_clear_focus", "focus clearer"),
    ("st.columns([1.3, 2.2, 1.5])", "3-col layout"),
    ("st.columns([1.1, 2.6, 1.3])", "old 3-col layout"),
]
print("== Should be REMOVED (expect 0) ==")
for k, label in checks_removed:
    n = content.count(k)
    mark = "OK" if n == 0 else "STILL PRESENT"
    print("  " + mark + "  " + label + "  (count: " + str(n) + ")")

print()
print("== Should be KEPT (expect >=1) ==")
for k, label in checks_kept:
    n = content.count(k)
    mark = "OK" if n >= 1 else "MISSING"
    print("  " + mark + "  " + label + "  (count: " + str(n) + ")")

print()
print("Bytes:", len(content.encode("utf-8")))
print("Lines:", content.count(chr(10)) + 1)