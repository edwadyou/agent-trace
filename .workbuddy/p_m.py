# -*- coding: utf-8 -*-
"""Replace IO blocks, _render_msg, _render_input_fallback. Wrap body. Delete list mode functions."""
import sys
sys.stdout.reconfigure(encoding="utf-8")
p = r"D:\my-projects\agent-monitor\viewer.py"
with open(p, encoding="utf-8") as f:
    lines = f.read().splitlines(keepends=False)

def find_first(needle):
    for i, l in enumerate(lines):
        if needle in l:
            return i + 1
    return None

# === 1. Replace IO blocks (input_block + output_block) with side-by-side ===
NEW_IO = """    # --- Input / Output side-by-side (headers aligned; each side scrolls independently) --
    c_in, c_out = st.columns(2, gap="medium")

    with c_in:
        st.markdown('<div class="io-col-head in-head">\u2b07  \u8f93\u5165</div>', unsafe_allow_html=True)
        if kind == "LLM":
            msgs = to_messages(canon(attrs, "messages.input"))
            if msgs:
                for m in msgs:
                    role = (m.get("role") or "user").lower()
                    content_val = m.get("content") or ""
                    _render_msg(m)
                    for tc in m.get("tool_calls") or []:
                        nm = tc.get("name") or "tool"
                        with st.expander(f"\U0001F527 {nm}"):
                            st.json(tc.get("arguments"))
            else:
                _render_input_fallback(attrs, "input.value")
        elif kind == "TOOL":
            tp = canon(attrs, "tool.parameters")
            st.markdown("**\u5de5\u5177\u53c2\u6570\uff1a**")
            if tp is None:
                st.caption("\uff08\u672a\u6355\u83b7\u53c2\u6570\uff09")
            elif isinstance(tp, str):
                try:
                    st.json(json.loads(tp))
                except (json.JSONDecodeError, TypeError):
                    st.code(tp)
            else:
                st.json(tp)
        else:
            _render_input_fallback(attrs, "input.value")

    with c_out:
        st.markdown('<div class="io-col-head out-head">\u2b06  \u8f93\u51fa</div>', unsafe_allow_html=True)
        if kind == "LLM":
            msgs = to_messages(canon(attrs, "messages.output"))
            if msgs:
                for m in msgs:
                    role = (m.get("role") or "assistant").lower()
                    content_val = m.get("content") or ""
                    _render_msg(m)
            else:
                _render_input_fallback(attrs, "output.value")
        elif kind == "TOOL":
            tout = canon(attrs, "tool.output")
            if tout is None:
                st.caption("\uff08\u672a\u6355\u83b7\u8fd4\u56de\u7ed3\u679c\uff09")
            elif isinstance(tout, (dict, list)):
                st.json(tout)
            elif isinstance(tout, str):
                try:
                    parsed = json.loads(tout)
                    if isinstance(parsed, (dict, list)):
                        st.json(parsed)
                    else:
                        st.code(str(parsed))
                except (json.JSONDecodeError, TypeError):
                    if len(tout) > 6000:
                        st.code(tout[:6000] + "\n\u2026(truncated)")
                    else:
                        st.code(tout)
            else:
                st.code(str(tout))
        else:
            _render_input_fallback(attrs, "output.value")

""".splitlines()

input_block = find_first("Input block (collapsible)")
token_breakdown = find_first("Token breakdown (LLM)")
print(f"Replacing IO block: L{input_block} to L{token_breakdown-1}")
lines[input_block - 1:token_breakdown - 1] = NEW_IO


# === 2. Replace _render_input_fallback ===
NEW_FB = """def _render_input_fallback(attrs, key):
    \"\"\"Smart fallback for input/output values.\"\"\"
    val = attrs.get(key)
    if val is None:
        st.caption(f"\uff08\u672a\u6355\u83b7 {key.split(chr(46))[0]} \uff09")
        return
    if isinstance(val, str):
        parsed = None
        try:
            cand = json.loads(val)
            if isinstance(cand, (dict, list)):
                parsed = cand
        except (json.JSONDecodeError, TypeError, ValueError):
            parsed = None
        if parsed is not None:
            st.json(parsed)
        elif len(val) > 800:
            st.code(val[:800])
            st.caption("\u2026\uff08\u88ab\u622a\u65ad\uff09")
        else:
            st.code(val)
    else:
        st.json(val)


""".splitlines()

fb = find_first("def _render_input_fallback(")
fb_end = None
for i in range(fb, len(lines)):
    if lines[i].startswith("def ") and not lines[i].startswith("def _render_input_fallback"):
        fb_end = i
        break
    if lines[i].startswith("# ===") and i > fb:
        fb_end = i
        break
print(f"Replacing fallback: L{fb} to L{fb_end}")
lines[fb - 1:fb_end] = NEW_FB


# === 3. Replace _render_msg (preserving _render_run_tab which follows) ===
NEW_MSG = """def _render_msg(msg):
    \"\"\"Render a single LLM message as a structured card.\"\"\"
    if isinstance(msg, dict) and isinstance(msg.get("message"), dict):
        inner = msg["message"]
        tool_calls = msg.get("tool_calls") or []
    else:
        inner = msg if isinstance(msg, dict) else {"content": msg}
        tool_calls = []
    role = (inner.get("role") or "user").lower()
    content_val = inner.get("content") or ""
    palette = {
        "user":      ("\U0001F464", "#10b981", "\u7528\u6237"),
        "human":     ("\U0001F464", "#10b981", "\u7528\u6237"),
        "assistant": ("\U0001F916", "#3b82f6", "\u52a9\u624b"),
        "ai":        ("\U0001F916", "#3b82f6", "\u52a9\u624b"),
        "system":    ("\u2699\ufe0f", "#9ca3af", "\u7cfb\u7edf"),
        "tool":      ("\U0001F527", "#f59e0b", "\u5de5\u5177"),
        "function":  ("\U0001F527", "#f59e0b", "\u5de5\u5177"),
    }
    key = role or "user"
    icon, color, label = palette.get(key, ("\U0001F4AC", "#6b7280", key.title() if key else "\u6d88\u606f"))
    st.markdown(
        f'<div class="msg-card" style="border-left:3px solid {color};">'
        f'<div class="msg-head"><span>{icon}</span>'
        f'<span class="msg-role-label" style="color:{color}">{_esc(label)}</span></div>',
        unsafe_allow_html=True,
    )
    meta_bits = []
    if tool_calls:
        meta_bits.append(f"\U0001F527 {len(tool_calls)} \u4e2a\u5de5\u5177\u8c03\u7528")
    if isinstance(content_val, list):
        meta_bits.append(f"\U0001F4DC {len(content_val)} \u4e2a\u5185\u5bb9\u5757")
    if meta_bits:
        st.markdown('<div class="msg-meta">' + " &nbsp;\u00b7&nbsp; ".join(meta_bits) + '</div>', unsafe_allow_html=True)
    st.markdown('<div class="msg-body">', unsafe_allow_html=True)
    if not content_val:
        st.markdown("<em style='color:#6b7280'>\uff08\u7a7a\uff09</em>", unsafe_allow_html=True)
    elif isinstance(content_val, str):
        st.markdown(content_val)
    elif isinstance(content_val, list):
        for part in content_val:
            if not isinstance(part, dict):
                st.markdown(_esc(str(part)))
                continue
            ptype = part.get("type")
            if ptype == "text":
                st.markdown(part.get("text", ""))
            elif ptype == "tool_use":
                inp = part.get("input", {})
                if not isinstance(inp, dict):
                    inp = {"value": inp}
                st.markdown(
                    f'<div class="msg-part-block"><b>\U0001F527 \u5de5\u5177\u8c03\u7528</b>: '
                    f'<code>{_esc(part.get("name", "?"))}</code><br/>'
                    f'<pre style="margin:4px 0;padding:6px 8px;background:rgba(0,0,0,0.25);'
                    f'border-radius:4px;font-size:11.5px;white-space:pre-wrap;word-break:break-all">'
                    f'{_esc(json.dumps(inp, ensure_ascii=False, indent=2)[:600])}</pre></div>',
                    unsafe_allow_html=True,
                )
            elif ptype == "tool_result":
                res = part.get("content", "")
                st.markdown(
                    f'<div class="msg-part-block"><b>\U0001F4E5 \u5de5\u5177\u7ed3\u679c</b>:'
                    f'<pre style="margin:4px 0;padding:6px 8px;background:rgba(0,0,0,0.25);'
                    f'border-radius:4px;font-size:11.5px;white-space:pre-wrap;word-break:break-all">'
                    f'{_esc(str(res)[:600])}</pre></div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(_esc(json.dumps(part, ensure_ascii=False)[:600]))
    else:
        st.markdown(_esc(str(content_val)))
    if tool_calls and isinstance(tool_calls, list):
        for tc in tool_calls:
            if not isinstance(tc, dict):
                continue
            name = tc.get("name", "tool")
            args = tc.get("arguments", "")
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except (json.JSONDecodeError, TypeError):
                    pass
            with st.expander(f"\U0001F527 \u8c03\u7528 {name}"):
                st.json(args)
    st.markdown("</div>", unsafe_allow_html=True)
    with st.expander("\U0001F4CB \u539f\u59cb JSON"):
        st.json(msg)
    st.markdown("</div>", unsafe_allow_html=True)


""".splitlines()

old_msg = find_first("def _render_msg(role: str, content: object)")
run_tab = find_first("def _render_run_tab(")
# Find the </div></div> close inside the msg body, then 2 blank lines
msg_close = None
for i in range(old_msg - 1, run_tab):
    if "</div></div>" in lines[i]:
        msg_close = i
        break
# Advance to past the 2 blank lines
msg_end = msg_close + 3
print(f"msg ends at L{msg_end} (msg_close L{msg_close+1}, run_tab L{run_tab})")
lines[old_msg - 1:msg_end] = NEW_MSG


# === 4. Delete _render_tree and the # LEFT tree renderer comment block ===
# Find "LEFT tree renderer" line
left_tree = find_first("LEFT tree renderer")
render_tree = find_first("def _render_tree(")
# Find end of _render_tree
tree_end = None
for i in range(render_tree, len(lines)):
    if lines[i].startswith("def ") and not lines[i].startswith("def _render_tree"):
        tree_end = i
        break
# Also include the blank line before the # === comment
start_del = left_tree - 2  # the # === line
# Also include blank line before
start_del = start_del - 1
print(f"Deleting tree: 0-idx {start_del} to {tree_end-1}")
lines[start_del:tree_end] = []


# === 5. Delete _render_metadata_panel ===
render_metadata = find_first("def _render_metadata_panel(")
md_end = None
for i in range(render_metadata, len(lines)):
    if lines[i].startswith("def ") and not lines[i].startswith("def _render_metadata_panel"):
        md_end = i
        break
# Also include blank line before
md_start = render_metadata - 2
print(f"Deleting metadata: 0-idx {md_start} to {md_end-1}")
lines[md_start:md_end] = []


# === 6. Delete expanded_spans init line + all assignment lines ===
import re
init_line = find_first('st.session_state.setdefault("expanded_spans"')
if init_line:
    del lines[init_line - 1]
    print("Deleted expanded_spans init")
# Remove assignment lines
new_lines = []
removed = 0
for l in lines:
    if re.match(r"^\s*st\.session_state\.expanded_spans = set\(\)\s*$", l):
        removed += 1
        continue
    new_lines.append(l)
print(f"Removed {removed} expanded_spans assignment lines")
lines = new_lines


# === 7. Wrap body in if/else (replace col_tree line + extend through _render_flowchart_mode call) ===
# Since list mode is removed, the col_tree line is no longer used. Replace
# the entire body (col_tree line + 3-col block) with a direct call to _render_flowchart_mode.

col_tree = find_first("col_tree, col_detail, col_meta = st.columns")
# Find the end of body (next non-empty line AFTER the body's closing ")")
body_end = None
for i in range(col_tree, len(lines)):
    if lines[i].strip() == ")":
        body_end = i + 1
        break
print(f"Body: L{col_tree} to L{body_end}")

# Replace entire body with single call to _render_flowchart_mode
NEW_BODY = [
    "_render_flowchart_mode(",
    "    sel_spans,",
    "    kpi,",
    "    all_by_id={s['span_id']: s for s in sel_spans},",
    ")",
]
lines[col_tree - 1:body_end] = NEW_BODY

with open(p, "w", encoding="utf-8", newline="\n") as f:
    f.write("\n".join(lines) + "\n")
print("\nFinal:", len(lines), "lines")
