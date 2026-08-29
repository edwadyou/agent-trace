import sys, re
sys.stdout.reconfigure(encoding="utf-8")
p = r"D:\my-projects\agent-monitor\viewer.py"
content = open(p, encoding="utf-8").read()

# Remove the 3 lines containing st.session_state.expanded_spans = set()
# They are at L783, L816, L1034. Each is on a standalone line followed by other code.
# We only need to remove the assignment line, not the surrounding context.
# Each line ends with "\n" and is preceded by 4 or 12 spaces of indent.

# Use a regex: remove lines whose stripped form is exactly "st.session_state.expanded_spans = set()"
pattern = re.compile(r"^[ \t]*st\.session_state\.expanded_spans = set\(\)\n", re.MULTILINE)
new_content, n = pattern.subn("", content)
print(f"Removed {n} expanded_spans assignments")
open(p, "w", encoding="utf-8", newline="\n").write(new_content)