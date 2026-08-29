# -*- coding: utf-8 -*-
"""Phase 5: major restructuring: wrap body, replace IO blocks, replace msg + fallback, delete list mode."""
import sys
sys.stdout.reconfigure(encoding="utf-8")
p = r"D:\my-projects\agent-monitor\viewer.py"
with open(p, encoding="utf-8") as f:
    lines = f.read().splitlines(keepends=False)

print("Starting lines:", len(lines))


# Find current line numbers
def find_first(needle, start=0):
    for i in range(start, len(lines)):
        if needle in lines[i]:
            return i + 1
    return None

render_tree_start = find_first("def _render_tree(")
render_tree_end = None
# Find end: next top-level def or # ===
for i in range(render_tree_start, len(lines)):
    if i + 1 < render_tree_start: continue
    if lines[i].startswith("def ") and not lines[i].startswith("def _render_tree"):
        render_tree_end = i  # exclusive (0-indexed)
        break
    if lines[i].startswith("# ===") and i > render_tree_start:
        render_tree_end = i
        break
# Find render_metadata_start
render_metadata_start = find_first("def _render_metadata_panel(")
render_metadata_end = None
for i in range(render_metadata_start, len(lines)):
    if lines[i].startswith("def ") and not lines[i].startswith("def _render_metadata_panel"):
        render_metadata_end = i
        break
    if lines[i].startswith("# ===") and i > render_metadata_start:
        render_metadata_end = i
        break
old_msg_start = find_first("def _render_msg(role: str, content: object)")
run_tab_start = find_first("def _render_run_tab(")
input_block_start = find_first("Input block (collapsible)")
output_block_start = find_first("Output block (collapsible)")
fallback_start = find_first("def _render_input_fallback(")
fallback_end = None
for i in range(fallback_start, len(lines)):
    if lines[i].startswith("def ") and not lines[i].startswith("def _render_input_fallback"):
        fallback_end = i
        break
    if lines[i].startswith("# ===") and i > fallback_start:
        fallback_end = i
        break
col_tree_line = find_first("col_tree, col_detail, col_meta = st.columns")

print(f"render_tree: {render_tree_start}..{render_tree_end}")
print(f"render_metadata: {render_metadata_start}..{render_metadata_end}")
print(f"old_msg: {old_msg_start}")
print(f"run_tab: {run_tab_start}")
print(f"input_block: {input_block_start}")
print(f"output_block: {output_block_start}")
print(f"fallback: {fallback_start}..{fallback_end}")
print(f"col_tree: {col_tree_line}")


# Apply transformations in REVERSE order (highest line first to preserve indices)
# Actually, the cleanest: use 0-indexed ranges and apply from end to start

# === Transform 7: Delete _render_metadata_panel + 1 blank line before ===
new_metadata_block = []
s = render_metadata_start - 2  # 0-idx; include blank line
e = render_metadata_end          # exclusive
print(f"\nDeleting render_metadata: 0-idx {s}-{e-1} ({e-s} lines)")
del lines[s:e]

# Re-find (line numbers shifted)
render_tree_start = find_first("def _render_tree(")
render_tree_end = None
for i in range(render_tree_start, len(lines)):
    if lines[i].startswith("def ") and not lines[i].startswith("def _render_tree"):
        render_tree_end = i
        break
    if lines[i].startswith("# ===") and i > render_tree_start:
        render_tree_end = i
        break
print(f"After meta del: render_tree: {render_tree_start}..{render_tree_end}")

# === Transform 6: Delete _render_tree + comment block + blank line before ===
# Find the "LEFT tree renderer" comment + "====" + _render_tree def
left_tree_idx = None
for i, l in enumerate(lines):
    if "LEFT tree renderer" in l:
        left_tree_idx = i
        break
# The structure is:
#   # === (line N)
#   # LEFT tree renderer (line N+1)
#   # === (line N+2)
#   def _render_tree (line N+3)
#   ... function body ...
#   end at line M
# Delete from # === (line N) to end (line M-1 inclusive)
s = left_tree_idx - 1
e = render_tree_end
print(f"Deleting render_tree block: 0-idx {s}-{e-1} ({e-s} lines)")
del lines[s:e]

# Re-find
col_tree_line = find_first("col_tree, col_detail, col_meta = st.columns")
output_block_start = find_first("Output block (collapsible)")
input_block_start = find_first("Input block (collapsible)")
run_tab_start = find_first("def _render_run_tab(")
old_msg_start = find_first("def _render_msg(role: str, content: object)")
fallback_start = find_first("def _render_input_fallback(")
fallback_end = None
for i in range(fallback_start, len(lines)):
    if lines[i].startswith("def ") and not lines[i].startswith("def _render_input_fallback"):
        fallback_end = i
        break
    if lines[i].startswith("# ===") and i > fallback_start:
        fallback_end = i
        break
print(f"\nAfter tree del: col_tree {col_tree_line}, run_tab {run_tab_start}, old_msg {old_msg_start}, fallback {fallback_start}..{fallback_end}")


# === Transform 5: Wrap body in if/else ===
# Find the col_tree line and the next blank + body wrap
# We need to find the "if not sel_spans" st.stop() block too
# The body section starts at the col_tree line and goes through the
# _render_metadata_panel(...) call (already removed)
# but actually the only line we need is the col_tree block

# Wrap the col_tree line + everything up to where body ends
# Looking at the structure: after col_tree is the existing body, which is now
# broken because _render_tree and _render_metadata_panel are removed.
# Let me just replace the col_tree line with an if/else block.

# Current col_tree line is a single line. I need to find what comes after
# until the body ends.
# Find the st.stop() right after the if not sel_spans
if_not_sel_spans = find_first("if not sel_spans:")
st_stop_line = None
for i in range(if_not_sel_spans - 1, len(lines)):
    if "st.stop()" in lines[i]:
        st_stop_line = i + 1
        break
print(f"if not sel_spans: L{if_not_sel_spans}, st.stop: L{st_stop_line}")

# Find _render_flowchart_mode call after st.stop
flowchart_call_start = find_first("_render_flowchart_mode(", start=st_stop_line)
# Find end of this call (matching closing paren at indent 0)
flowchart_call_end = None
for i in range(flowchart_call_start - 1, len(lines)):
    if lines[i].strip() == ")":
        flowchart_call_end = i + 1
        break
print(f"flowchart call: L{flowchart_call_start}..L{flowchart_call_end}")

# Now replace from col_tree_line to flowchart_call_end with the if/else wrapper
old_body_lines = lines[col_tree_line - 1:flowchart_call_end]
print(f"Old body has {len(old_body_lines)} lines")

new_body = [
    "if st.session_state.view_mode == '\u5217\u8868':",
    "    col_tree, col_detail, col_meta = st.columns([1.1, 2.6, 1.3])",
    "    with col_tree:",
    "        st.markdown(",
    "            f'#### \U0001F5C2 \u5bfc\u822a\u6811 '",
    "            f'<span style=\"color:#9ca3af;font-size:11px;font-weight:400\">'",
    "            f'\u00b7 {len(filtered_spans)} spans</span>',",
    "            unsafe_allow_html=True,",
    "        )",
    "        def _select_only(sid):",
    "            st.session_state.selected_span = sid",
    "        def _toggle_expand(sid):",
    "            if sid in st.session_state.expanded_spans:",
    "                st.session_state.expanded_spans.discard(sid)",
    "            else:",
    "                st.session_state.expanded_spans.add(sid)",
    "        _render_tree(roots, children_map, depth=0)",
    "    with col_detail:",
    "        st.markdown('#### \U0001F50D Span \u8be6\u60c5')",
    "        _render_detail_panel(sel_spans, by_id_all={s['span_id']: s for s in sel_spans})",
    "    with col_meta:",
    "        st.markdown('#### \U0001F4CA \u5143\u6570\u636e\u9762\u677f')",
    "        _render_metadata_panel(kpi, sel_spans, by_id_all={s['span_id']: s for s in sel_spans})",
    "else:  # \u6d41\u7a0b\u56fe mode",
    "    _render_flowchart_mode(",
    "        sel_spans,",
    "        kpi,",
    "        all_by_id={s['span_id']: s for s in sel_spans},",
    "    )",
]
lines[col_tree_line - 1:flowchart_call_end] = new_body
print(f"Body wrapped: {len(new_body)} lines")


# Re-find line numbers
fallback_start = find_first("def _render_input_fallback(")
fallback_end = None
for i in range(fallback_start, len(lines)):
    if lines[i].startswith("def ") and not lines[i].startswith("def _render_input_fallback"):
        fallback_end = i
        break
    if lines[i].startswith("# ===") and i > fallback_start:
        fallback_end = i
        break
input_block_start = find_first("Input block (collapsible)")
output_block_start = find_first("Output block (collapsible)")
old_msg_start = find_first("def _render_msg(role: str, content: object)")
run_tab_start = find_first("def _render_run_tab(")
print(f"After body wrap: fallback {fallback_start}..{fallback_end}, input_block {input_block_start}, output_block {output_block_start}, old_msg {old_msg_start}, run_tab {run_tab_start}")


# === Transform 4: Replace _render_input_fallback with smart version ===
new_fallback = [
    "def _render_input_fallback(attrs, key):",
    "    \"\"\"Smart fallback for input/output values.\"\"\"",
    "    val = attrs.get(key)",
    "    if val is None:",
    "        st.caption(f\"\uff08\u672a\u6355\u83b7 {key.split(chr(46))[0]} \uff09\")",
    "        return",
    "    if isinstance(val, str):",
    "        parsed = None",
    "        try:",
    "            cand = json.loads(val)",
    "            if isinstance(cand, (dict, list)):",
    "                parsed = cand",
    "        except (json.JSONDecodeError, TypeError, ValueError):",
    "            parsed = None",
    "        if parsed is not None:",
    "            st.json(parsed)",
    "        elif len(val) > 800:",
    "            st.code(val[:800])",
    "            st.caption(\"\u2026\uff08\u88ab\u622a\u65ad\uff09\")",
    "        else:",
    "            st.code(val)",
    "    else:",
    "        st.json(val)",
    "",
    "",
]
s = fallback_start - 1
e = fallback_end
print(f"Replacing fallback: 0-idx {s}-{e-1} -> {len(new_fallback)} lines")
lines[s:e] = new_fallback


# Re-find
output_block_start = find_first("Output block (collapsible)")
input_block_start = find_first("Input block (collapsible)")
old_msg_start = find_first("def _render_msg(role: str, content: object)")
run_tab_start = find_first("def _render_run_tab(")
print(f"After fallback: output_block {output_block_start}, input_block {input_block_start}, old_msg {old_msg_start}, run_tab {run_tab_start}")


# === Transform 3: IO side-by-side: replace from "Input block" to end of "Output block" (the function body of _render_run_tab) ===
# Find the start of "Input block" comment and end of "Output block" close paren
# The IO block is inside _render_run_tab. We need to find what's between the
# "Input block" comment and the end of the closing `        else: st.code(str(tout))` + `)` + the function continues with token breakdown.
# Better approach: find the EXACT start and end of the IO block
# Input block starts at "    # --- Input block (collapsible) ..."
# Output block ends at the line after "        else: st.code(str(tout))" which is ")"
# Actually: look for the line "    # --- Token breakdown (LLM) ---" as the END marker

# Find the Token breakdown line
token_breakdown_start = find_first("Token breakdown (LLM)")
print(f"token breakdown: L{token_breakdown_start}")

io_block_start_0idx = input_block_start - 1  # 0-indexed
io_block_end_0idx = token_breakdown_start - 2  # 0-indexed, the blank line before

new_io_block = [
    "    # --- Input / Output side-by-side (headers aligned; each side scrolls independently) --",
    "    c_in, c_out = st.columns(2, gap='medium')",
    "",
    "    with c_in:",
    "        st.markdown('<div class=\"io-col-head in-head\">\u2b07  \u8f93\u5165</div>', unsafe_allow_html=True)",
    "        if kind == 'LLM':",
    "            msgs = to_messages(canon(attrs, 'messages.input'))",
    "            if msgs:",
    "                for m in msgs:",
    "                    role = (m.get('role') or 'user').lower()",
    "                    content_val = m.get('content') or ''",
    "                    _render_msg(m)",
    "                    for tc in m.get('tool_calls') or []:",
    "                        nm = tc.get('name') or 'tool'",
    "                        with st.expander(f'\U0001F527 {nm}'):",
    "                            st.json(tc.get('arguments'))",
    "            else:",
    "                _render_input_fallback(attrs, 'input.value')",
    "        elif kind == 'TOOL':",
    "            tp = canon(attrs, 'tool.parameters')",
    "            st.markdown('**\u5de5\u5177\u53c2\u6570\uff1a**')",
    "            if tp is None:",
    "                st.caption('\uff08\u672a\u6355\u83b7\u53c2\u6570\uff09')",
    "            elif isinstance(tp, str):",
    "                try:",
    "                    st.json(json.loads(tp))",
    "                except (json.JSONDecodeError, TypeError):",
    "                    st.code(tp)",
    "            else:",
    "                st.json(tp)",
    "        else:",
    "            _render_input_fallback(attrs, 'input.value')",
    "",
    "    with c_out:",
    "        st.markdown('<div class=\"io-col-head out-head\">\u2b06  \u8f93\u51fa</div>', unsafe_allow_html=True)",
    "        if kind == 'LLM':",
    "            msgs = to_messages(canon(attrs, 'messages.output'))",
    "            if msgs:",
    "                for m in msgs:",
    "                    role = (m.get('role') or 'assistant').lower()",
    "                    content_val = m.get('content') or ''",
    "                    _render_msg(m)",
    "            else:",
    "                _render_input_fallback(attrs, 'output.value')",
    "        elif kind == 'TOOL':",
    "            tout = canon(attrs, 'tool.output')",
    "            if tout is None:",
    "                st.caption('\uff08\u672a\u6355\u83b7\u8fd4\u56de\u7ed3\u679c\uff09')",
    "            elif isinstance(tout, (dict, list)):",
    "                st.json(tout)",
    "            elif isinstance(tout, str):",
    "                try:",
    "                    parsed = json.loads(tout)",
    "                    if isinstance(parsed, (dict, list)):",
    "                        st.json(parsed)",
    "                    else:",
    "                        st.code(str(parsed))",
    "                except (json.JSONDecodeError, TypeError):",
    "                    if len(tout) > 6000:",
    "                        st.code(tout[:6000] + '\n\u2026(truncated)')",
    "                    else:",
    "                        st.code(tout)",
    "            else:",
    "                st.code(str(tout))",
    "        else:",
    "            _render_input_fallback(attrs, 'output.value')",
    "",
]
# Replace from io_block_start_0idx to io_block_end_0idx (inclusive of blank line before token breakdown)
print(f"Replacing IO block: 0-idx {io_block_start_0idx}-{io_block_end_0idx} -> {len(new_io_block)} lines")
lines[io_block_start_0idx:io_block_end_0idx + 1] = new_io_block


# Re-find
old_msg_start = find_first("def _render_msg(role: str, content: object)")
print(f"After IO: old_msg at L{old_msg_start}")


# === Transform 2: Replace _render_msg (preserving _render_run_tab which is right after) ===
# _render_msg ends at "st.markdown(\"</div></div>\", unsafe_allow_html=True)" + blank lines
# Find the end of _render_msg body
# Walk from old_msg_start until we find 3 blank lines then a def
end_msg = None
i = old_msg_start - 1
blanks = 0
while i < len(lines):
    if lines[i].strip() == "":
        blanks += 1
        if blanks == 2:
            # Check if next line is "def _render_run_tab"
            if i + 1 < len(lines) and lines[i + 1].startswith("def _render_run_tab"):
                end_msg = i + 1  # exclusive (1 past 2nd blank)
                break
    else:
        blanks = 0
    i += 1
if end_msg is None:
    print("Could not find end of _render_msg; using fixed search")
    # Try alternate: walk until "def _render_run_tab"
    for i in range(old_msg_start, len(lines)):
        if lines[i].startswith("def _render_run_tab"):
            end_msg = i
            break
print(f"_render_msg: L{old_msg_start}-L{end_msg}")

new_msg = [
    "def _render_msg(msg):",
    "    \"\"\"Render a single LLM message as a structured card.\"\"\"",
    "    if isinstance(msg, dict) and isinstance(msg.get('message'), dict):",
    "        inner = msg['message']",
    "        tool_calls = msg.get('tool_calls') or []",
    "    else:",
    "        inner = msg if isinstance(msg, dict) else {'content': msg}",
    "        tool_calls = []",
    "    role = (inner.get('role') or 'user').lower()",
    "    content_val = inner.get('content') or ''",
    "    palette = {",
    "        'user':      ('\U0001F464', '#10b981', '\u7528\u6237'),",
    "        'human':     ('\U0001F464', '#10b981', '\u7528\u6237'),",
    "        'assistant': ('\U0001F916', '#3b82f6', '\u52a9\u624b'),",
    "        'ai':        ('\U0001F916', '#3b82f6', '\u52a9\u624b'),",
    "        'system':    ('\u2699\ufe0f', '#9ca3af', '\u7cfb\u7edf'),",
    "        'tool':      ('\U0001F527', '#f59e0b', '\u5de5\u5177'),",
    "        'function':  ('\U0001F527', '#f59e0b', '\u5de5\u5177'),",
    "    }",
    "    key = role or 'user'",
    "    icon, color, label = palette.get(key, ('\U0001F4AC', '#6b7280', key.title() if key else '\u6d88\u606f'))",
    "    st.markdown(",
    "        f'<div class=\"msg-card\" style=\"border-left:3px solid {color};\">'",
    "        f'<div class=\"msg-head\"><span>{icon}</span>'",
    "        f'<span class=\"msg-role-label\" style=\"color:{color}\">{_esc(label)}</span></div>',",
    "        unsafe_allow_html=True,",
    "    )",
    "    meta_bits = []",
    "    if tool_calls:",
    "        meta_bits.append(f'\U0001F527 {len(tool_calls)} \u4e2a\u5de5\u5177\u8c03\u7528')",
    "    if isinstance(content_val, list):",
    "        meta_bits.append(f'\U0001F4DC {len(content_val)} \u4e2a\u5185\u5bb9\u5757')",
    "    if meta_bits:",
    "        st.markdown('<div class=\"msg-meta\">' + ' &nbsp;\u00b7&nbsp; '.join(meta_bits) + '</div>', unsafe_allow_html=True)",
    "    st.markdown('<div class=\"msg-body\">', unsafe_allow_html=True)",
    "    if not content_val:",
    "        st.markdown(\"<em style='color:#6b7280'>\uff08\u7a7a\uff09</em>\", unsafe_allow_html=True)",
    "    elif isinstance(content_val, str):",
    "        st.markdown(content_val)",
    "    elif isinstance(content_val, list):",
    "        for part in content_val:",
    "            if not isinstance(part, dict):",
    "                st.markdown(_esc(str(part)))",
    "                continue",
    "            ptype = part.get('type')",
    "            if ptype == 'text':",
    "                st.markdown(part.get('text', ''))",
    "            elif ptype == 'tool_use':",
    "                inp = part.get('input', {})",
    "                if not isinstance(inp, dict):",
    "                    inp = {'value': inp}",
    "                st.markdown(",
    "                    f'<div class=\"msg-part-block\"><b>\U0001F527 \u5de5\u5177\u8c03\u7528</b>: '",
    "                    f'<code>{_esc(part.get(\"name\", \"?\"))}</code><br/>'",
    "                    f'<pre style=\"margin:4px 0;padding:6px 8px;background:rgba(0,0,0,0.25);'",
    "                    f'border-radius:4px;font-size:11.5px;white-space:pre-wrap;word-break:break-all\">'",
    "                    f'{_esc(json.dumps(inp, ensure_ascii=False, indent=2)[:600])}</pre></div>',",
    "                    unsafe_allow_html=True,",
    "                )",
    "            elif ptype == 'tool_result':",
    "                res = part.get('content', '')",
    "                st.markdown(",
    "                    f'<div class=\"msg-part-block\"><b>\U0001F4E5 \u5de5\u5177\u7ed3\u679c</b>:'",
    "                    f'<pre style=\"margin:4px 0;padding:6px 8px;background:rgba(0,0,0,0.25);'",
    "                    f'border-radius:4px;font-size:11.5px;white-space:pre-wrap;word-break:break-all\">'",
    "                    f'{_esc(str(res)[:600])}</pre></div>',",
    "                    unsafe_allow_html=True,",
    "                )",
    "            else:",
    "                st.markdown(_esc(json.dumps(part, ensure_ascii=False)[:600]))",
    "    else:",
    "        st.markdown(_esc(str(content_val)))",
    "    if tool_calls and isinstance(tool_calls, list):",
    "        for tc in tool_calls:",
    "            if not isinstance(tc, dict):",
    "                continue",
    "            name = tc.get('name', 'tool')",
    "            args = tc.get('arguments', '')",
    "            if isinstance(args, str):",
    "                try:",
    "                    args = json.loads(args)",
    "                except (json.JSONDecodeError, TypeError):",
    "                    pass",
    "            with st.expander(f'\U0001F527 \u8c03\u7528 {name}'):",
    "                st.json(args)",
    "    st.markdown('</div>', unsafe_allow_html=True)",
    "    with st.expander('\U0001F4CB \u539f\u59cb JSON'):",
    "        st.json(msg)",
    "    st.markdown('</div>', unsafe_allow_html=True)",
    "",
    "",
]
print(f"Replacing _render_msg: 0-idx {old_msg_start-1}-{end_msg-1} -> {len(new_msg)} lines")
lines[old_msg_start - 1:end_msg] = new_msg


# Save
with open(p, "w", encoding="utf-8", newline="\n") as f:
    f.write("\n".join(lines) + "\n")
print(f"\nFinal: {len(lines)} lines")