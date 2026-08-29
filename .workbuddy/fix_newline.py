import sys
sys.stdout.reconfigure(encoding="utf-8")
p = r"D:\my-projects\agent-monitor\viewer.py"
content = open(p, encoding="utf-8").read()

old = (
    '        elif len(val) > 800:\n'
    '            st.code(val[:800] + "\n\u2026\uff08\u88ab\u622a\u65ad\uff09")\n'
    '        else:\n'
    '            st.code(val)\n'
    '    else:\n'
    '        st.json(val)\n'
    '\n'
    '\n'
    'def _render_run_tab'
)
new = (
    '        elif len(val) > 800:\n'
    '            st.code(val[:800])\n'
    '            st.caption("\u2026\uff08\u88ab\u622a\u65ad\uff09")\n'
    '        else:\n'
    '            st.code(val)\n'
    '    else:\n'
    '        st.json(val)\n'
    '\n'
    '\n'
    'def _render_run_tab'
)
if old in content:
    content = content.replace(old, new, 1)
    print("Fixed")
else:
    print("Pattern not found")
open(p, "w", encoding="utf-8", newline="\n").write(content)