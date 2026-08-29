import sys
sys.stdout.reconfigure(encoding="utf-8")
content = open(r"D:\my-projects\agent-monitor\viewer.py", encoding="utf-8").read()
checks = [
  ("flowchart TD", "Mermaid direction"),
  ("all_sequential", "chain inference"),
  ("subgraph SG_", "parallel subgraph"),
  ("click {nid} focusSpan", "mermaid click directive"),
  ("window.focusSpan", "focusSpan JS"),
  ("_render_trace_cards_list", "left column fn"),
  ("_render_flowchart_center", "center column fn"),
  ("_render_detail_column", "right column fn"),
  ("st.columns([1.3, 2.2, 1.5])", "3-col ratio"),
  ("_jump_to_span", "focus setter helper"),
  ("_clear_focus", "focus clearer helper"),
  ("manual_focus_pick", "selectbox fallback"),
  ("trace-card", "CSS class"),
  ("trace-card-active", "active CSS"),
  ("trace-card-children", "children CSS"),
  ('st.query_params.get("trace")', "URL trace sync"),
  ('st.query_params.get("focus")', "URL focus sync"),
  ("msg-card", "msg-card CSS"),
]
for k, label in checks:
    mark = "OK" if k in content else "MISS"
    print(mark + "  " + label)
print()
print("Bytes:", len(content.encode("utf-8")))