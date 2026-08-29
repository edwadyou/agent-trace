import sys
sys.stdout.reconfigure(encoding="utf-8")
p = r"D:\my-projects\agent-monitor\viewer.py"
content = open(p, encoding="utf-8").read()
lines = content.splitlines()

# Collect deletions (work in 0-indexed line numbers, applied in reverse order to preserve indices)
deletions = []

# 1) View-mode switcher block (1-indexed L1043-1056, 0-idx 1042-1055)
# Plus the # ----- separator line above (L1041) and blank line below (L1057)
# Actually keep # ----- boundary markers, just remove the inner block.
# Safer: remove L1043-1057 (the # =======... line 1041 is the SECTION header above,
# let me look at context. Lines 1040-1041 are # ====..., 1042 blank, 1043-1057 is the block.
# Actually let me just remove the inner content lines 1042-1056 (0-idx 1041-1055)
# But line 1042 is blank, removing it would join the next section header.
# Easiest: remove L1043-1056 (the comment + 14 lines), keep one blank before next.
deletions.append((1042, 1055))  # 0-idx 1042-1055 inclusive (= 1-idx 1043-1056)
# That's the # ----- comment + body of switcher (14 lines)

# 2) session_state expanded_spans init (L720, 0-idx 719)
# Look at L720-721 (line + comment if any)
# Actually it's a single line. But to be safe, check what's around.
# We'll just delete the line.
# Find: st.session_state.setdefault("expanded_spans", set())
# 1-indexed L720 = 0-idx 719
# But we also want to delete the blank line after it? Let me just delete one line.
deletions.append((719, 719))

# 3) _render_tree function (1-idx L1084-L1153, 0-idx 1083-1152)
# Actually need to also delete the blank line BEFORE it (L1083 blank, 0-idx 1082)
# to avoid double blank lines. So delete L1083-L1153 = 0-idx 1082-1152.
deletions.append((1082, 1152))

# 4) _render_metadata_panel function (1-idx L2115-L2209, 0-idx 2114-2208)
# Delete blank before + function
deletions.append((2113, 2208))

# 5) Body wrap if/else (1-idx L2285-L2329, 0-idx 2284-2328)
# L2284 is blank
# L2285: if view_mode == '列表':
# L2324: else: # 流程图 mode  (need to keep, modify to remove else:)
# L2325-2329: _render_flowchart_mode(...) call
# So delete L2285-L2323 (the if-branch + its trailing comment+blank line)
# But also need to handle the else: line.
# Actually I'll:
#   - Delete L2285-L2323 (entire if block including blank line before else)
#   - Then strip "else:  # 流程图 mode" comment from L2324
# Let me delete 2284-2323 (0-idx) -- includes blank line before else
deletions.append((2284, 2323))

# Apply deletions in REVERSE order
for start, end in sorted(deletions, key=lambda x: -x[0]):
    print(f"Deleting 0-idx {start}-{end} (L{start+1}-L{end+1})")
    del lines[start:end+1]

# Now modify the else line (was at L2324, but indices shifted)
# Find it
for i, l in enumerate(lines):
    if l.startswith("else:") and "流程图" in l.encode("ascii", "replace").decode("ascii"):
        print(f"Found else at 0-idx {i} (L{i+1}): {l!r}")
        # Unindent by 4 spaces
        if lines[i].startswith("    else:"):
            lines[i] = lines[i][4:]
        break

# Now the body wrap should look like:
#   if not sel_spans:
#       ...
#       st.stop()
#
#   _render_flowchart_mode(
#       sel_spans,
#       kpi,
#       all_by_id={...},
#   )

open(p, "w", encoding="utf-8", newline="\n").write(chr(10).join(lines) + chr(10))
print("Bytes:", len(open(p, "rb").read()))