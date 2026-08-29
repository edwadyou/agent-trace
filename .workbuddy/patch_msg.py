# -*- coding: utf-8 -*-
import sys, re
sys.stdout.reconfigure(encoding="utf-8")
p = r"D:\my-projects\agent-monitor\viewer.py"
content = open(p, encoding="utf-8").read()

# Step 1: Replace _render_msg function body
idx = content.find("def _render_msg(")
end_idx = content.find("def _render_run_tab", idx)

# Anchor for the function start to end (excluding trailing blank lines)
start_anchor = "def _render_msg(role: str, content: object) -> None:"
end_anchor = '    st.markdown("</div></div>", unsafe_allow_html=True)'

start_pos = content.find(start_anchor, idx)
end_pos = content.find(end_anchor, start_pos) + len(end_anchor)
assert start_pos > 0 and end_pos > start_pos

new_msg_func = (
    'def _render_msg(msg):\n'
    '    """Render a single LLM message as a structured card.\n'
    '    msg is the full normalized message dict. Renders role chip + meta + body\n'
    '    content (str or Anthropic-style parts list) + raw-JSON expander.\n'
    '    """\n'
    '    if isinstance(msg, dict) and isinstance(msg.get("message"), dict):\n'
    '        inner = msg["message"]\n'
    '        tool_calls = msg.get("tool_calls") or []\n'
    '    else:\n'
    '        inner = msg if isinstance(msg, dict) else {"content": msg}\n'
    '        tool_calls = []\n'
    '    role = (inner.get("role") or "user").lower()\n'
    '    content = inner.get("content") or ""\n'
    '    palette = {\n'
    '        "user":      ("\U0001F464", "#10b981", "\u7528\u6237"),\n'
    '        "human":     ("\U0001F464", "#10b981", "\u7528\u6237"),\n'
    '        "assistant": ("\U0001F916", "#3b82f6", "\u52a9\u624b"),\n'
    '        "ai":        ("\U0001F916", "#3b82f6", "\u52a9\u624b"),\n'
    '        "system":    ("\u2699\ufe0f", "#9ca3af", "\u7cfb\u7edf"),\n'
    '        "tool":      ("\U0001F527", "#f59e0b", "\u5de5\u5177"),\n'
    '        "function":  ("\U0001F527", "#f59e0b", "\u5de5\u5177"),\n'
    '    }\n'
    '    key = role or "user"\n'
    '    icon, color, label = palette.get(key, ("\U0001F4AC", "#6b7280", key.title() if key else "\u6d88\u606f"))\n'
    '    st.markdown(\n'
    '        f"<div class=\"msg-card\" style=\"border-left:3px solid {color};\">"\n'
    '        f"<div class=\"msg-head\">"\n'
    '        f"<span>{icon}</span>"\n'
    '        f"<span class=\"msg-role-label\" style=\"color:{color}">{_esc(label)}</span>"\n'
    '        f"</div>",\n'
    '        unsafe_allow_html=True,\n'
    '    )\n'
    '    meta_bits = []\n'
    '    if tool_calls:\n'
    '        meta_bits.append(f"\U0001F527 {len(tool_calls)} \u4e2a\u5de5\u5177\u8c03\u7528")\n'
    '    if isinstance(content, list):\n'
    '        meta_bits.append(f"\U0001F4DC {len(content)} \u4e2a\u5185\u5bb9\u5757")\n'
    '    if meta_bits:\n'
    '        st.markdown(\n'
    '            f"<div class=\"msg-meta\">{" &nbsp;\u00b7&nbsp; ".join(meta_bits)}</div>",\n'
    '            unsafe_allow_html=True,\n'
    '        )\n'
    '    st.markdown("<div class=\"msg-body\">", unsafe_allow_html=True)\n'
    '    if not content:\n'
    '        st.markdown("<em style=\'color:#6b7280\'>\uff08\u7a7a\uff09</em>", unsafe_allow_html=True)\n'
    '    elif isinstance(content, str):\n'
    '        st.markdown(content)\n'
    '    elif isinstance(content, list):\n'
    '        for part in content:\n'
    '            if not isinstance(part, dict):\n'
    '                st.markdown(_esc(str(part)))\n'
    '                continue\n'
    '            ptype = part.get("type")\n'
    '            if ptype == "text":\n'
    '                st.markdown(part.get("text", ""))\n'
    '            elif ptype == "tool_use":\n'
    '                inp = part.get("input", {})\n'
    '                if not isinstance(inp, dict):\n'
    '                    inp = {"value": inp}\n'
    '                st.markdown(\n'
    '                    f"<div class=\"msg-part-block\">"\n'
    '                    f"<b>\U0001F527 \u5de5\u5177\u8c03\u7528</b>: "\n'
    '                    f"<code>{_esc(part.get(\"name\", \"?\"))}</code><br/>"\n'
    '                    f"<pre style=\"margin:4px 0;padding:6px 8px;background:rgba(0,0,0,0.25);\"\n'
    '                    f"border-radius:4px;font-size:11.5px;white-space:pre-wrap;\"\n'
    '                    f"word-break:break-all">"\n'
    '                    f"{_esc(json.dumps(inp, ensure_ascii=False, indent=2)[:600])}</pre></div>",\n'
    '                    unsafe_allow_html=True,\n'
    '                )\n'
    '            elif ptype == "tool_result":\n'
    '                res = part.get("content", "")\n'
    '                st.markdown(\n'
    '                    f"<div class=\"msg-part-block\">"\n'
    '                    f"<b>\U0001F4E5 \u5de5\u5177\u7ed3\u679c</b>:"\n'
    '                    f"<pre style=\"margin:4px 0;padding:6px 8px;background:rgba(0,0,0,0.25);"\n'
    '                    f"border-radius:4px;font-size:11.5px;white-space:pre-wrap;\"\n'
    '                    f"word-break:break-all">"\n'
    '                    f"{_esc(str(res)[:600])}</pre></div>",\n'
    '                    unsafe_allow_html=True,\n'
    '                )\n'
    '            else:\n'
    '                st.markdown(_esc(json.dumps(part, ensure_ascii=False)[:600]))\n'
    '    else:\n'
    '        st.markdown(_esc(str(content)))\n'
    '    if tool_calls and isinstance(tool_calls, list):\n'
    '        for tc in tool_calls:\n'
    '            if not isinstance(tc, dict):\n'
    '                continue\n'
    '            name = tc.get("name", "tool")\n'
    '            args = tc.get("arguments", "")\n'
    '            if isinstance(args, str):\n'
    '                try:\n'
    '                    args = json.loads(args)\n'
    '                except (json.JSONDecodeError, TypeError):\n'
    '                    pass\n'
    '            with st.expander(f"\U0001F527 \u8c03\u7528 {name}"):\n'
    '                st.json(args)\n'
    '    st.markdown("</div>", unsafe_allow_html=True)\n'
    '    with st.expander("\U0001F4CB \u539f\u59cb JSON" if False else "\U0001F4CB \u539f\u59cb JSON"):\n'
    '        st.json(msg)\n'
    '    st.markdown("</div>", unsafe_allow_html=True)\n'
    '\n'
    '\n'
)

# Replace
old_block = content[start_pos:end_pos]
content = content[:start_pos] + new_msg_func + content[end_pos:]
print("Step 1: _render_msg replaced; old len:", len(old_block), "new len:", len(new_msg_func))

# Step 2: Update call site in _render_run_tab (input side)
old_call_in = (
    '                    role = (m.get(\'role\') or \'user\').lower()\n'
    '                    content_val = m.get(\'content\') or \'\'\n'
    '                    _render_msg(role, content_val)'
)
new_call_in = '                    _render_msg(m)'
if old_call_in in content:
    content = content.replace(old_call_in, new_call_in, 1)
    print("Step 2a: input call site updated")
else:
    print("Step 2a FAILED: input call site not found")

# Step 3: Update call site in _render_run_tab (output side)
old_call_out = (
    '                    role = (m.get(\'role\') or \'assistant\').lower()\n'
    '                    content_val = m.get(\'content\') or \'\'\n'
    '                    _render_msg(role, content_val)'
)
new_call_out = '                    _render_msg(m)'
if old_call_out in content:
    content = content.replace(old_call_out, new_call_out, 1)
    print("Step 2b: output call site updated")
else:
    print("Step 2b FAILED: output call site not found")

open(p, "w", encoding="utf-8", newline="\n").write(content)
print("Bytes:", len(content.encode("utf-8")))