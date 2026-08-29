import sys
sys.stdout.reconfigure(encoding="utf-8")
content = open(r"D:\my-projects\agent-monitor\viewer.py", encoding="utf-8").read()

# Source literal:        "  mermaid.initialize({\\n"
# Python interprets this as a string containing "  mermaid.initialize({\\n" (with backslash-n literal)
# We want to insert before this line

# Build the literal source text we want to insert
old_literal = '        "  mermaid.initialize({\\n"'
new_literal = (
    '        "  window.focusSpan = function(nodeId) {\\n"\n'
    '        "    var spanId = (nodeId || \\"\\").replace(/^n_/, \\"\\").replace(/_/g, \\"-\\");\\n"\n'
    '        "    if (!spanId) return;\\n"\n'
    '        "    var url = new URL(window.parent.location.href);\\n"\n'
    '        "    url.searchParams.set(\\"focus\\", spanId);\\n"\n'
    '        "    window.parent.location.href = url.toString();\\n"\n'
    '        "  };\\n"\n'
    '        "  mermaid.initialize({\\n"\n'
)

print("Old literal:", repr(old_literal))
print()
print("In content?", old_literal in content)
if old_literal in content:
    content = content.replace(old_literal, new_literal, 1)
    print("focusSpan injected")
open(r"D:\my-projects\agent-monitor\viewer.py", "w", encoding="utf-8").write(content)