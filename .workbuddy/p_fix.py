# -*- coding: utf-8 -*-
"""Fix the broken line with literal newline."""
import sys
sys.stdout.reconfigure(encoding="utf-8")
p = r"D:\my-projects\agent-monitor\viewer.py"
with open(p, encoding="utf-8", newline="\n") as f:
    content = f.read()
# Look for the broken pattern
import re
m = re.search(r"st\.code\(tout\[:6000\] \+ \"\n[^\n]*\(truncated\)\"\)", content)
if m:
    print("Found broken:", repr(m.group()))
    # Replace with proper single-line version
    fixed = m.group().replace("\n", "...").replace("...(truncated)", "...truncated")
    # Actually: should be `st.code(tout[:6000] + "...truncated")` on one line
    fixed = 'st.code(tout[:6000] + "...truncated")'
    content = content[:m.start()] + content[m.start():m.end()].replace(m.group(), fixed) + content[m.end():]
    # Simpler: do the replace
    content = re.sub(
        r"st\.code\(tout\[:6000\] \+ \"[^\"]*\(truncated\)\"\)",
        'st.code(tout[:6000] + "...truncated")',
        content
    )
with open(p, "w", encoding="utf-8", newline="\n") as f:
    f.write(content)
print("Done")
