import sys
sys.stdout.reconfigure(encoding="utf-8")
content = open(r"D:\my-projects\agent-monitor\viewer.py", encoding="utf-8").read()

old_edge = (
    "    # Render edges (parent->child)\n"
    "    for span in visible_spans:\n"
    "        pid = span.get(\"parent_span_id\")\n"
    "        if pid and pid in visible:\n"
    "            out.append(f\"    {_mermaid_safe_id(pid)} --> {_mermaid_safe_id(span['span_id'])}\")\n"
    "\n"
    "    # Mermaid native click"
)
new_edge = (
    "    # Render edges (parent->child) for parents not yet handled by chain/parallel block\n"
    "    for span in visible_spans:\n"
    "        pid = span.get(\"parent_span_id\")\n"
    "        if pid and pid in visible and pid not in _handled_parents:\n"
    "            out.append(f\"    {_mermaid_safe_id(pid)} --> {_mermaid_safe_id(span['span_id'])}\")\n"
    "\n"
    "    # Mermaid native click"
)
if old_edge in content:
    content = content.replace(old_edge, new_edge, 1)
    print("Edge loop updated to skip handled parents")
else:
    print("Edge loop pattern not found")
open(r"D:\my-projects\agent-monitor\viewer.py", "w", encoding="utf-8").write(content)