import sys
sys.stdout.reconfigure(encoding="utf-8")
p = r"D:\my-projects\agent-monitor\viewer.py"
content = open(p, encoding="utf-8").read()
lines = content.splitlines()

# Remove old _render_msg (1216-1254 1-indexed = 1215-1253 0-indexed) and the blank line at 1215
# Old _render_run_tab (1255-1385 = 1254-1384 0-indexed)
# Plus blank line 1385 (0-indexed 1384)
# So we remove lines 1215-1385 inclusive (1-indexed) = 1214-1384 0-indexed

# Verify boundaries
print("Line 1215 (0-idx 1214):", repr(lines[1214]))
print("Line 1216 (0-idx 1215):", repr(lines[1215]))
print("Line 1385 (0-idx 1384):", repr(lines[1384]))
print("Line 1386 (0-idx 1385):", repr(lines[1385]))

# Remove lines 1215-1385 inclusive (1-indexed) = 0-indexed 1214-1384
new_lines = lines[:1214] + lines[1385:]
print("Removed", len(lines) - len(new_lines), "lines")
print("Before:", len(lines), "After:", len(new_lines))

open(p, "w", encoding="utf-8").write(chr(10).join(new_lines) + chr(10))