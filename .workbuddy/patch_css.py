import sys
sys.stdout.reconfigure(encoding="utf-8")
content = open(r"D:\my-projects\agent-monitor\viewer.py", encoding="utf-8").read()

old = '.msg-card .msg-body {\n    max-height: 6em;\n    overflow-y: auto;\n    overflow-wrap: anywhere;\n    word-break: break-word;\n    padding: 6px 10px 8px 10px;\n    margin: 0;\n    font-size: 12.5px;\n    line-height: 1.45;\n    color: #d1d5db;\n}'
new = (
    '.msg-card .msg-body {\n'
    '    max-height: 18em;\n'
    '    overflow-y: auto;\n'
    '    overflow-wrap: anywhere;\n'
    '    word-break: break-word;\n'
    '    padding: 6px 10px 8px 10px;\n'
    '    margin: 0;\n'
    '    font-size: 12.5px;\n'
    '    line-height: 1.45;\n'
    '    color: #d1d5db;\n'
    '}\n'
    '.msg-card .msg-meta {\n'
    '    padding: 3px 10px;\n'
    '    font-size: 10.5px;\n'
    '    color: #9ca3af;\n'
    '    background: rgba(255,255,255,0.02);\n'
    '    border-bottom: 1px solid rgba(255,255,255,0.05);\n'
    '}\n'
    '.msg-card .msg-part-block {\n'
    '    margin: 6px 0;\n'
    '    padding: 6px 8px;\n'
    '    border-left: 2px solid rgba(59,130,246,0.5);\n'
    '    background: rgba(59,130,246,0.06);\n'
    '    border-radius: 0 4px 4px 0;\n'
    '    font-size: 11.5px;\n'
    '}\n'
    '.mermaid .nodeLabel, .mermaid .node rect, .mermaid .node polygon {\n'
    '    cursor: pointer;\n'
    '}'
)
if old in content:
    content = content.replace(old, new, 1)
    print("CSS updated")
else:
    print("Old CSS pattern not found")
open(r"D:\my-projects\agent-monitor\viewer.py", "w", encoding="utf-8").write(content)