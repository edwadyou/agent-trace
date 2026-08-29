import sys
sys.stdout.reconfigure(encoding="utf-8")
p = r"D:\my-projects\agent-monitor\viewer.py"
with open(p, encoding="utf-8") as f:
    lines = f.read().splitlines(keepends=False)

# Find col_tree line
col_tree_line = None
for i, l in enumerate(lines):
    if l.startswith("col_tree, col_detail, col_meta = st.columns"):
        col_tree_line = i + 1
        break
print(f"col_tree at L{col_tree_line}")

# The body extends from col_tree_line to end of file. Find the actual body end
# by walking forward looking for "_render_metadata_panel(...)" which is the last call.
end_body = col_tree_line - 1
last_metadata_line = None
for i in range(col_tree_line - 1, len(lines)):
    if "_render_metadata_panel(" in lines[i]:
        last_metadata_line = i
if last_metadata_line is None:
    print("ERROR: _render_metadata_panel not found")
    sys.exit(1)
# The body extends from col_tree to that line inclusive + its closing )
# Actually find the matching closing ")" at column 0
end_excl = last_metadata_line
while end_excl < len(lines) and lines[end_excl].strip() != ")":
    end_excl += 1
if end_excl >= len(lines):
    print("ERROR: could not find closing )")
    sys.exit(1)
end_excl += 1  # past ")"
print(f"Body from L{col_tree_line} to L{end_excl}")

# Get the lines
body_lines = lines[col_tree_line - 1:end_excl]
print(f"Body has {len(body_lines)} lines")

# Indent each by 4 spaces
indented = [("    " + l) if l.strip() else l for l in body_lines]

# Construct the new block
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

# Replace
lines[col_tree_line - 1:end_excl] = new_block
print(f"Replaced with {len(new_block)} lines")

with open(p, "w", encoding="utf-8", newline="\n") as f:
    f.write("\n".join(lines) + "\n")
print(f"Final: {len(lines)} lines")