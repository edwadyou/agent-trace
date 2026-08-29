import sys
sys.stdout.reconfigure(encoding="utf-8")
HEAD = open(r"D:\my-projects\agent-monitor\.workbuddy\viewer_HEAD.py", encoding="utf-8").read()
head_lines = HEAD.splitlines()
# Extract _render_tree block (lines 1030-1468 in HEAD = indices 1029-1467)
# _render_tree starts at index 1029
# _render_metadata_panel starts at index 1467 (where we stop)
extracted = head_lines[1029:1467]
print("Lines extracted:", len(extracted))
# Now find the insertion point in current file: right before Flowchart mode helpers
content = open(r"D:\my-projects\agent-monitor\viewer.py", encoding="utf-8").read()
# Find marker
marker = "# ---------------------------------------------------------------------------\n# Flowchart mode (Mermaid) + click-to-zoom"
idx = content.find(marker)
print("Flowchart marker at:", idx)
# Insert before
insertion = chr(10).join(extracted) + chr(10) + chr(10)
content = content[:idx] + insertion + content[idx:]
open(r"D:\my-projects\agent-monitor\viewer.py", "w", encoding="utf-8").write(content)
print("Bytes:", len(content.encode("utf-8")))