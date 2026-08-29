import sys
sys.stdout.reconfigure(encoding="utf-8")
content = open(r"D:\my-projects\agent-monitor\viewer.py", encoding="utf-8").read()

inject_before = '        "  mermaid.initialize({\n"'
inject = (
    '        "  window.focusSpan = function(nodeId) {\n"'
    '        "    var spanId = (nodeId || \\"\\").replace(/^n_/, \\"\\").replace(/_/g, \\"-\\");\n"'
    '        "    if (!spanId) return;\n"'
    '        "    var url = new URL(window.parent.location.href);\n"'
    '        "    url.searchParams.set(\\"focus\\", spanId);\n"'
    '        "    window.parent.location.href = url.toString();\n"'
    '        "  };\n"'
    '        "  mermaid.initialize({\n"'
)
if inject_before in content:
    content = content.replace(inject_before, inject, 1)
    print("focusSpan injected")
else:
    print("Pattern not found")
open(r"D:\my-projects\agent-monitor\viewer.py", "w", encoding="utf-8").write(content)