import sys
sys.stdout.reconfigure(encoding="utf-8")
content = open(r"D:\my-projects\agent-monitor\viewer.py", encoding="utf-8").read()

old = "/* ----- right metadata panel ----- */"
new = (
    "/* ----- trace card list (flowchart explorer left column) ----- */\n"
    ".trace-card {\n"
    "    background: rgba(255,255,255,0.03);\n"
    "    border: 1px solid rgba(255,255,255,0.08);\n"
    "    border-radius: 8px;\n"
    "    padding: 8px 10px;\n"
    "    margin-bottom: 8px;\n"
    "}\n"
    ".trace-card-active {\n"
    "    border-color: rgba(59,130,246,0.55);\n"
    "    background: rgba(59,130,246,0.10);\n"
    "}\n"
    ".trace-card-children {\n"
    "    margin-top: 4px;\n"
    "    font-size: 10.5px;\n"
    "    color: #9ca3af;\n"
    "    overflow: hidden;\n"
    "    text-overflow: ellipsis;\n"
    "    white-space: nowrap;\n"
    "    padding-left: 4px;\n"
    "}\n"
    "\n"
    "/* ----- right metadata panel ----- */"
)
if old in content:
    content = content.replace(old, new, 1)
    print("CSS for trace-card added")
else:
    print("Pattern not found")
open(r"D:\my-projects\agent-monitor\viewer.py", "w", encoding="utf-8").write(content)