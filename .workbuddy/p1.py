import sys
sys.stdout.reconfigure(encoding="utf-8")
content = open(r"D:\my-projects\agent-monitor\viewer.py", encoding="utf-8").read()
old = '    out = ["flowchart LR"]'
new = '    out = ["flowchart TD"]'
if old in content:
    content = content.replace(old, new, 1)
    print("Phase 1 done: flowchart LR -> TD")
else:
    print("Pattern not found")
open(r"D:\my-projects\agent-monitor\viewer.py", "w", encoding="utf-8").write(content)