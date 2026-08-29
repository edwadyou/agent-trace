import sys
sys.stdout.reconfigure(encoding="utf-8")
content = open(r"D:\my-projects\agent-monitor\viewer.py", encoding="utf-8").read()
old = '            out.append(f"    subgraph SG_{pnid}[\\""])\n            sub.append("    direction LR")'
new = '            out.append(f"    subgraph SG_{pnid}[\\"\\u5e76\\u884c\\u5206\\u652f\\"]")\n            out.append("    direction LR")'
if old in content:
    content = content.replace(old, new)
    print("Fixed")
else:
    print("Pattern not found")
open(r"D:\my-projects\agent-monitor\viewer.py", "w", encoding="utf-8").write(content)