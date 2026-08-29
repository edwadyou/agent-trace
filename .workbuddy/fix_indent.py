import sys
sys.stdout.reconfigure(encoding="utf-8")
content = open(r"D:\my-projects\agent-monitor\viewer.py", encoding="utf-8").read()
old = "            # Parallel: wrap in subgraph; all children fan out from parent\n                        _handled_parents.add(parent_id)\n"
new = "            # Parallel: wrap in subgraph; all children fan out from parent\n            _handled_parents.add(parent_id)\n"
if old in content:
    content = content.replace(old, new, 1)
    print("Indentation fixed")
open(r"D:\my-projects\agent-monitor\viewer.py", "w", encoding="utf-8").write(content)