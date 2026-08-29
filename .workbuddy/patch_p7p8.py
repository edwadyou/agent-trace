# -*- coding: utf-8 -*-
"""Apply phases 7-10:
   7) Replace _render_msg with structured card version
   8) Update _render_input_fallback to parse JSON strings
   9) Replace _build_mermaid: LR direction, time sort, t+ms annotation, Mermaid click
  10) Update _render_mermaid_html: window.focusSpan + add st.selectbox fallback
"""
import sys
sys.stdout.reconfigure(encoding="utf-8")

p = r"D:\my-projects\agent-monitor\viewer.py"
content = open(p, encoding="utf-8").read()


# ============================================================
# Phase 7: Replace _render_msg
# ============================================================
# Find function bounds
start_anchor = "def _render_msg(role: str, content: object) -> None:"
end_anchor_marker = '    st.markdown("</div></div>", unsafe_allow_html=True)'
start_pos = content.find(start_anchor)
assert start_pos > 0
end_pos = content.find(end_anchor_marker, start_pos) + len(end_anchor_marker)

# Build new function source with explicit double quotes via chr(34) substitution at runtime.
# To avoid quoting hell, use a helper function that takes a template and escapes.
def esc_q(s):
    """Replace literal double-quote with backslash-double-quote for use inside Python double-quoted f-strings."""
    return s.replace('"', chr(92) + '"')

NEW_MSG = '''def _render_msg(msg):
    """Render a single LLM message as a structured card.

    msg is the full normalized message dict (potentially OI-wrapped with top-level
    'message' and 'tool_calls'). Renders: role chip + meta line (tool_calls count,
    part count) + body content (str OR Anthropic-style parts list) + inline tool
    call expanders + raw-JSON expander.
    """
    if isinstance(msg, dict) and isinstance(msg.get("message"), dict):
        inner = msg["message"]
        tool_calls = msg.get("tool_calls") or []
    else:
        inner = msg if isinstance(msg, dict) else {"content": msg}
        tool_calls = []
    role = (inner.get("role") or "user").lower()
    content_val = inner.get("content") or ""
    palette = {
        "user":      ("USER_ICON", "USER_COLOR", "USER_LABEL"),
        "human":     ("USER_ICON", "USER_COLOR", "USER_LABEL"),
        "assistant": ("ASSIST_ICON", "ASSIST_COLOR", "ASSIST_LABEL"),
        "ai":        ("ASSIST_ICON", "ASSIST_COLOR", "ASSIST_LABEL"),
        "system":    ("SYS_ICON", "SYS_COLOR", "SYS_LABEL"),
        "tool":      ("TOOL_ICON", "TOOL_COLOR", "TOOL_LABEL"),
        "function":  ("TOOL_ICON", "TOOL_COLOR", "TOOL_LABEL"),
    }
    key = role or "user"
    icon, color, label = palette.get(key, ("DEFAULT_ICON", "DEFAULT_COLOR", key.title() if key else "MESSAGE_LABEL"))
    # Open card with role chip
    st.markdown(
        f'<div class="msg-card" style="border-left:3px solid {color};">'
        f'<div class="msg-head">'
        f'<span>{icon}</span>'
        f'<span class="msg-role-label" style="color:{color}">{_esc(label)}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )
    meta_bits = []
    if tool_calls:
        meta_bits.append(f"{TOOL_ICON} {len(tool_calls)} TOOL_CALLS_LABEL")
    if isinstance(content_val, list):
        meta_bits.append(f"{PARTS_ICON} {len(content_val)} PARTS_LABEL")
    if meta_bits:
        st.markdown(
            f'<div class="msg-meta">{" &nbsp;MIDDOT_T&nbsp; ".join(meta_bits)}</div>',
            unsafe_allow_html=True,
        )
    st.markdown('<div class="msg-body">', unsafe_allow_html=True)
    if not content_val:
        st.markdown("<em style=QC#6b7280Q>EMPTY_LABEL</em>", unsafe_allow_html=True)
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
                    f'<div class="msg-part-block">'
                    f'<b>{TOOL_ICON} TOOL_USE_LABEL</b>: '
                    f'<code>{_esc(part.get("name", "?"))}</code><br/>'
                    f'<pre style="margin:4px 0;padding:6px 8px;background:rgba(0,0,0,0.25);'
                    f'border-radius:4px;font-size:11.5px;white-space:pre-wrap;'
                    f'word-break:break-all">'
                    f'{_esc(json.dumps(inp, ensure_ascii=False, indent=2)[:600])}</pre></div>',
                    unsafe_allow_html=True,
                )
            elif ptype == "tool_result":
                res = part.get("content", "")
                st.markdown(
                    f'<div class="msg-part-block">'
                    f'<b>{RESULT_ICON} TOOL_RESULT_LABEL</b>:'
                    f'<pre style="margin:4px 0;padding:6px 8px;background:rgba(0,0,0,0.25);'
                    f'border-radius:4px;font-size:11.5px;white-space:pre-wrap;'
                    f'word-break:break-all">'
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
            with st.expander(f"{TOOL_ICON} CALL_LABEL {name}"):
                st.json(args)
    st.markdown("</div>", unsafe_allow_html=True)
    with st.expander(f"{RAW_ICON} RAW_JSON_LABEL"):
        st.json(msg)
    st.markdown("</div>", unsafe_allow_html=True)
'''
# Substitute placeholder strings (uppercase ASCII tokens) with the actual unicode escapes.
subs = {
    'USER_ICON':     '"\\U0001F464"',
    'USER_COLOR':    '"#10b981"',
    'USER_LABEL':    '"\\u7528\\u6237"',
    'ASSIST_ICON':   '"\\U0001F916"',
    'ASSIST_COLOR':  '"#3b82f6"',
    'ASSIST_LABEL':  '"\\u52a9\\u624b"',
    'SYS_ICON':      '"\\u2699\\ufe0f"',
    'SYS_COLOR':     '"#9ca3af"',
    'SYS_LABEL':     '"\\u7cfb\\u7edf"',
    'TOOL_ICON':     '"\\U0001F527"',
    'TOOL_COLOR':    '"#f59e0b"',
    'TOOL_LABEL':    '"\\u5de5\\u5177"',
    'DEFAULT_ICON':  '"\\U0001F4AC"',
    'DEFAULT_COLOR': '"#6b7280"',
    'MESSAGE_LABEL': '"\\u6d88\\u606f"',
    'TOOL_CALLS_LABEL':   '"\\u4e2a\\u5de5\\u5177\\u8c03\\u7528"',
    'PARTS_ICON':    '"\\U0001F4DC"',
    'PARTS_LABEL':   '"\\u4e2a\\u5185\\u5bb9\\u5757"',
    'MIDDOT_T':      '"\\u00b7"',
    'QC':            '"',
    'EMPTY_LABEL':   '"\\uff08\\u7a7a\\uff09"',
    'TOOL_USE_LABEL':    '"\\u5de5\\u5177\\u8c03\\u7528"',
    'TOOL_RESULT_LABEL': '"\\u5de5\\u5177\\u7ed3\\u679c"',
    'RESULT_ICON':   '"\\U0001F4E5"',
    'CALL_LABEL':    '"\\u8c03\\u7528"',
    'RAW_ICON':      '"\\U0001F4CB"',
    'RAW_JSON_LABEL':    '"\\u539f\\u59cb JSON"',
}
for k, v in subs.items():
    NEW_MSG = NEW_MSG.replace(k, v)
content = content[:start_pos] + NEW_MSG + content[end_pos:]
print("Phase 7: _render_msg replaced, length:", len(NEW_MSG))


# ============================================================
# Update call sites in _render_run_tab to pass the full message dict
# ============================================================
old_call_in = (
    "                    role = (m.get('role') or 'user').lower()\n"
    "                    content_val = m.get('content') or ''\n"
    "                    _render_msg(role, content_val)"
)
new_call_in = "                    _render_msg(m)"
if old_call_in in content:
    content = content.replace(old_call_in, new_call_in, 1)
    print("Phase 7a: input call site updated")
else:
    print("Phase 7a: input call site pattern not found")

old_call_out = (
    "                    role = (m.get('role') or 'assistant').lower()\n"
    "                    content_val = m.get('content') or ''\n"
    "                    _render_msg(role, content_val)"
)
new_call_out = "                    _render_msg(m)"
if old_call_out in content:
    content = content.replace(old_call_out, new_call_out, 1)
    print("Phase 7b: output call site updated")
else:
    print("Phase 7b: output call site pattern not found")


# ============================================================
# Phase 8: Update _render_input_fallback to parse JSON strings
# ============================================================
old_fallback = (
    'def _render_input_fallback(attrs: dict, key: str) -> None:\n'
    '    val = attrs.get(key)\n'
    '    if val is None:\n'
    "        st.caption(f\"(no {key.split(chr(46))[0]} captured)\")\n"
    '        return\n'
    '    if isinstance(val, str):\n'
    '        if len(val) > 4000:\n'
    "            st.code(val[:4000] + \"\\n\\u2026(truncated)\")\n"
    '        else:\n'
    '            st.code(val)\n'
    '    else:\n'
    '        st.json(val)'
)
new_fallback = (
    'def _render_input_fallback(attrs: dict, key: str) -> None:\n'
    '    val = attrs.get(key)\n'
    '    if val is None:\n'
    "        st.caption(f\"\\uff08\\u672a\\u6355\\u83b7 {key.split(chr(46))[0]} \\uff09\")\n"
    '        return\n'
    '    if isinstance(val, str):\n'
    '        # Try to parse as JSON for structured display\n'
    '        parsed = None\n'
    '        try:\n'
    '            parsed = json.loads(val)\n'
    '            if not isinstance(parsed, (dict, list)):\n'
    '                parsed = None\n'
    '        except (json.JSONDecodeError, TypeError, ValueError):\n'
    '            parsed = None\n'
    '        if parsed is not None:\n'
    '            st.json(parsed)\n'
    '        elif len(val) > 800:\n'
    "            st.code(val[:800] + \"\\n\\u2026(\\u88ab\\u622a\\u65ad)\")\n"
    '        else:\n'
    '            st.code(val)\n'
    '    else:\n'
    '        st.json(val)'
)
if old_fallback in content:
    content = content.replace(old_fallback, new_fallback, 1)
    print("Phase 8: _render_input_fallback updated")
else:
    print("Phase 8: fallback pattern not found")


# Write
open(p, "w", encoding="utf-8", newline="\n").write(content)
print("Bytes:", len(content.encode("utf-8")))