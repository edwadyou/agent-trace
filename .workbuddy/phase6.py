import sys
sys.stdout.reconfigure(encoding="utf-8")
p = r"D:\my-projects\agent-monitor\viewer.py"
with open(p, encoding="utf-8") as f:
    lines = f.read().splitlines(keepends=False)

# Find the list body
col_tree_line = None
for i, l in enumerate(lines):
    if l.startswith("col_tree, col_detail, col_meta = st.columns"):
        col_tree_line = i + 1
        break
print(f"col_tree at L{col_tree_line}")

# Indent L1956 to L1995 by 4 spaces, and prepend "if st.session_state.view_mode == '列表':\n"
# Then add "else:\n    _render_flowchart_mode(sel_spans, kpi, all_by_id={...})\n" after
# Find the end of the list body - it's the last non-empty line
end_body = col_tree_line - 1
while end_body < len(lines) and lines[end_body].strip() != "":
    end_body += 1
# end_body is now the first empty line after the list body
# Actually we want to include the list body
# Walk back if needed
end_body -= 1
# Find the very last non-blank line of the list body
while end_body >= col_tree_line and lines[end_body].strip() == "":
    end_body -= 1
print(f"List body end at L{end_body + 1}: {lines[end_body][:60]}")

# Get the list body lines (col_tree to last non-blank)
body_lines = lines[col_tree_line - 1:end_body + 1]
print(f"List body: {len(body_lines)} lines")

# Indent each line by 4 spaces
indented = ["    " + l if l.strip() else l for l in body_lines]

# Construct the new wrapper
new_block = [
    "if st.session_state.view_mode == '\u5217\u8868':",
] + indented + [
    "",
    "else:  # \u6d41\u7a0b\u56fe mode",
    "    _render_flowchart_mode(",
    "        sel_spans,",
    "        kpi,",
    "        all_by_id={s['span_id']: s for s in sel_spans},",
    "    )",
]

# Replace the list body with the new wrapper
# First, find the END of the body block (after line 1995 there are blank lines)
# Use the line right after the last non-blank line as the exclusive end
end_exclusive = end_body + 1
# Skip blank lines
while end_exclusive < len(lines) and lines[end_exclusive].strip() == "":
    end_exclusive += 1
# Now lines[end_exclusive] is the first non-blank line AFTER the body, or end of file
# We want to replace from col_tree_line-1 to end_exclusive
print(f"Replacing 0-idx {col_tree_line - 1} to {end_exclusive - 1}")

lines[col_tree_line - 1:end_exclusive] = new_block
print(f"Replaced with {len(new_block)} lines")

# Save
with open(p, "w", encoding="utf-8", newline="\n") as f:
    f.write("\n".join(lines) + "\n")
print(f"Final: {len(lines)} lines")