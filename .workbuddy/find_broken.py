import sys
sys.stdout.reconfigure(encoding="utf-8")
content = open(r"D:\my-projects\agent-monitor\viewer.py", encoding="utf-8").read()

# Locate the broken subgraph line
idx = content.find('out.append(f"    subgraph SG_')
print("Broken line index:", idx)
print("Context:", repr(content[idx:idx+200]))