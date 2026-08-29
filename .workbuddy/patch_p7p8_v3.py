# -*- coding: utf-8 -*-
"""Phase 7+8 patch: structured _render_msg + smart _render_input_fallback.

Approach: build NEW_MSG and NEW_FALLBACK as plain Python source by writing the
literal escape sequences like U+XXXX (NOT actual unicode characters).  This avoids
both literal-newline and shell-escape issues.
"""
import sys, re
sys.stdout.reconfigure(encoding="utf-8")

p = r"D:\my-projects\agent-monitor\viewer.py"
content = open(p, encoding="utf-8").read()


# ============================================================
# Phase 7: structured _render_msg
# ============================================================
# The string uses literal \\uXXXX for unicode; literal \n in source becomes the
# newline escape at runtime.
NEW_MSG = '''def _render_msg(msg):
    """Render a single LLM message as a structured card.

    `msg` is the full normalized message dict (possibly OI-wrapped with
    top-level 'message' and 'tool_calls').  Renders role chip + meta line
    + body content (str or Anthropic-style list of parts) + raw JSON.
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
        "user":      ("\\U0001F464", "#10b981", "\\u7528\\u6237"),
        "human":     ("\\U0001F464", "#10b981", "\\u7528\\u6237"),
        "assistant": ("\\U0001F916", "#3b82f6", "\\u52a9\\u624b"),
        "ai":        ("\\U0001F916", "#3b82f6", "\\u52a9\\u624b"),
        "system":    ("\\u2699\\ufe0f", "#9ca3af", "\\u7cfb\\u7edf"),
        "tool":      ("\\U0001F527", "#f59e0b", "\\u5de5\\u5177"),
        "function":  ("\\U0001F527", "#f59e0b", "\\u5de5\\u5177"),
    }
    key = role or "user"
    icon, color, label = palette.get(key, ("\\U0001F4AC", "#6b7280", key.title() if key else "\\u6d88\\u606f"))
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
        meta_bits.append(f"\\U0001F527 {len(tool_calls)} \\u4e2a\\u5de5\\u5177\\u8c03\\u7528")
    if isinstance(content_val, list):
        meta_bits.append(f"\\U0001F4DC {len(content_val)} \\u4e2a\\u5185\\u5bb9\\u5757")
    if meta_bits:
        st.markdown(
            '<div class="msg-meta">' + " &nbsp;\\u00b7&nbsp; ".join(meta_bits) + '</div>',
            unsafe_allow_html=True,
        )
    st.markdown('<div class="msg-body">', unsafe_allow_html=True)
    if not content_val:
        st.markdown("<em style=\'color:#6b7280\'>\\uff08\\u7a7a\\uff09</em>", unsafe_allow_html=True)
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
                    f'<b>\\U0001F527 \\u5de5\\u5177\\u8c03\\u7528</b>: '
                    f'<code>{_esc(part.get("name", "?"))}</code><br/>'
                    f'<pre style="margin:4px 0;padding:6px 8px;background:rgba(0,0,0,0.25);'
                    f'border-radius:4px;font-size:11.5px;white-space:pre-wrap;'
                    f'word-break:break-all">'
                    f'{_esc(json.dumps(inp, ensure_ascii=False, indent=2)[:600])}'
                    f'</pre></div>',
                    unsafe_allow_html=True,
                )
            elif ptype == "tool_result":
                res = part.get("content", "")
                st.markdown(
                    f'<div class="msg-part-block">'
                    f'<b>\\U0001F4E5 \\u5de5\\u5177\\u7ed3\\u679c</b>:'
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
            with st.expander(f"\\U0001F527 \\u8c03\\u7528 {name}"):
                st.json(args)
    st.markdown("</div>", unsafe_allow_html=True)
    with st.expander("\\U0001F4CB \\u539f\\u59cb JSON"):
        st.json(msg)
    st.markdown("</div>", unsafe_allow_html=True)


'''
# Find old function bounds
start_anchor = "def _render_msg(role: str, content: object) -> None:"
end_anchor = '    st.markdown("</div></div>", unsafe_allow_html=True)'
start_pos = content.find(start_anchor)
end_pos = content.find(end_anchor, start_pos) + len(end_anchor)
assert start_pos > 0 and end_pos > start_pos

old_block = content[start_pos:end_pos]
content = content[:start_pos] + NEW_MSG + content[end_pos:]
print("Phase 7: _render_msg replaced; old", len(old_block), "-> new", len(NEW_MSG))


# Update call sites
for old_call, label in [
    (
        "                    role = (m.get('role') or 'user').lower()\n"
        "                    content_val = m.get('content') or ''\n"
        "                    _render_msg(role, content_val)",
        "input",
    ),
    (
        "                    role = (m.get('role') or 'assistant').lower()\n"
        "                    content_val = m.get('content') or ''\n"
        "                    _render_msg(role, content_val)",
        "output",
    ),
]:
    if old_call in content:
        content = content.replace(old_call, "                    _render_msg(m)", 1)
        print(f"Phase 7 call site ({label}) updated")
    else:
        print(f"Phase 7 call site ({label}) NOT FOUND")


# ============================================================
# Phase 8: Smart _render_input_fallback
# ============================================================
NEW_FALLBACK = '''def _render_input_fallback(attrs: dict, key: str) -> None:
    """Smart fallback for input/output values.

    If `val` is a JSON string we parse and render via st.json() for
    structure; otherwise we fall back to st.code() with truncation.
    """
    val = attrs.get(key)
    if val is None:
        st.caption(f"\\uff08\\u672a\\u6355\\u83b7 {key.split(chr(46))[0]} \\uff09")
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
            st.caption("\\u2026\\uff08\\u88ab\\u622a\\u65ad\\uff09")
        else:
            st.code(val)
    else:
        st.json(val)


'''

m = re.search(
    r'def _render_input_fallback\(attrs: dict, key: str\) -> None:.*?(?=\n\ndef |\nclass )',
    content,
    re.DOTALL,
)
if m:
    old = m.group(0)
    content = content.replace(old, NEW_FALLBACK, 1)
    print("Phase 8: _render_input_fallback updated")
else:
    print("Phase 8: pattern not found")


open(p, "w", encoding="utf-8", newline="\n").write(content)
print("Bytes:", len(content.encode("utf-8")))