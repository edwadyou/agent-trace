# -*- coding: utf-8 -*-
"""Phase 4-9: view-mode radio, body wrap, IO side-by-side, msg card, fallback, CSS."""
import sys, re
sys.stdout.reconfigure(encoding="utf-8")

p = r"D:\my-projects\agent-monitor\viewer.py"
content = open(p, encoding="utf-8").read()

def replace_once(text, old, new, label):
    if old in text:
        text = text.replace(old, new, 1)
        print(f"  [OK] {label}")
    else:
        print(f"  [SKIP] {label}")
    return text


# ===== Phase 4: View-mode switcher =====
anchor = "# Build filtered span list + tree structure"
radio = (
    "\n# ---------------------------------------------------------------------------\n"
    "# View-mode switcher\n"
    "# ---------------------------------------------------------------------------\n"
    "st.session_state.setdefault('view_mode', '\u5217\u8868')\n"
    "_view_opts = ['\u5217\u8868', '\u6d41\u7a0b\u56fe']\n"
    "_view_idx = _view_opts.index(st.session_state.view_mode) if st.session_state.view_mode in _view_opts else 0\n"
    "st.radio(\n"
    "    '\u89c6\u56fe\u6a21\u5f0f',\n"
    "    options=_view_opts,\n"
    "    index=_view_idx,\n"
    "    horizontal=True,\n"
    "    key='view_mode',\n"
    "    label_visibility='collapsed',\n"
    ")\n\n"
)
content = replace_once(content, anchor, radio + anchor, "View-mode switcher")


# ===== Phase 5: Body wrap (if/else for view modes) =====
body_start_marker = "col_tree, col_detail, col_meta = st.columns([1.1, 2.6, 1.3])"
end_marker = "_render_metadata_panel(kpi, sel_spans, by_id_all={s[\"span_id\"]: s for s in sel_spans})\n"
body_start = content.find(body_start_marker)
body_end_search = content.find(end_marker, body_start)
assert body_start > 0 and body_end_search > body_start, "Phase 5: body markers not found"
body_end = body_end_search + len(end_marker)
old_body = content[body_start:body_end]
new_body = (
    "if st.session_state.view_mode == '\u5217\u8868':\n"
    "    col_tree, col_detail, col_meta = st.columns([1.1, 2.6, 1.3])\n"
    "\n"
    "    # =======================================================================\n"
    "    # LEFT column - navigation tree\n"
    "    # =======================================================================\n"
    "    with col_tree:\n"
    "        st.markdown(\n"
    "            f'#### \U0001F5C2 \u5bfc\u822a\u6811 '\n"
    "            f'<span style=\"color:#9ca3af;font-size:11px;font-weight:400\">'\n"
    "            f'\u00b7 {len(filtered_spans)} spans</span>',\n"
    "            unsafe_allow_html=True,\n"
    "        )\n"
    "\n"
    "        def _select_only(sid):\n"
    "            st.session_state.selected_span = sid\n"
    "\n"
    "        def _toggle_expand(sid):\n"
    "            if sid in st.session_state.expanded_spans:\n"
    "                st.session_state.expanded_spans.discard(sid)\n"
    "            else:\n"
    "                st.session_state.expanded_spans.add(sid)\n"
    "\n"
    "        _render_tree(roots, children_map, depth=0)\n"
    "\n"
    "    # =======================================================================\n"
    "    # CENTER column - detail panel\n"
    "    # =======================================================================\n"
    "    with col_detail:\n"
    "        st.markdown('#### \U0001F50D Span \u8be6\u60c5')\n"
    "        _render_detail_panel(sel_spans, by_id_all={s['span_id']: s for s in sel_spans})\n"
    "\n"
    "    # =======================================================================\n"
    "    # RIGHT column - metadata indicator panel\n"
    "    # =======================================================================\n"
    "    with col_meta:\n"
    "        st.markdown('#### \U0001F4CA \u5143\u6570\u636e\u9762\u677f')\n"
    "        _render_metadata_panel(kpi, sel_spans, by_id_all={s['span_id']: s for s in sel_spans})\n"
    "\n"
    "else:  # \u6d41\u7a0b\u56fe mode\n"
    "    _render_flowchart_mode(\n"
    "        sel_spans,\n"
    "        kpi,\n"
    "        all_by_id={s['span_id']: s for s in sel_spans},\n"
    "    )\n"
)
content = content[:body_start] + new_body + content[body_end:]
print(f"Phase 5: body wrap inserted; new bytes = {len(content.encode('utf-8'))}")


# ===== Phase 6: IO side-by-side in _render_run_tab =====
io_old = (
    "    # --- Input block (collapsible) ------------------------------------------\n"
    "    input_open = True\n"
    "    with st.expander(\"\u2b07  \u8f93\u5165\", expanded=input_open):\n"
    "        if kind == \"LLM\":\n"
    "            msgs = to_messages(canon(attrs, \"messages.input\"))\n"
    "            if msgs:\n"
    "                for m in msgs:\n"
    "                    role = (m.get(\"role\") or \"user\").lower()\n"
    "                    content = m.get(\"content\") or \"\"\n"
    "                    _render_msg(role, content)\n"
    "                    for tc in m.get(\"tool_calls\") or []:\n"
    "                        nm = tc.get(\"name\") or \"tool\"\n"
    "                        with st.expander(f\"\U0001F527 {nm}\"):\n"
    "                            st.json(tc.get(\"arguments\"))\n"
    "            else:\n"
    "                _render_input_fallback(attrs, \"input.value\")\n"
    "        elif kind == \"TOOL\":\n"
    "            tp = canon(attrs, \"tool.parameters\")\n"
    "            st.markdown(\"**\u5de5\u5177\u53c2\u6570\uff1a**\")\n"
    "            if tp is None:\n"
    "                st.caption(\"\uff08\u672a\u6355\u83b7\u53c2\u6570\uff09\")\n"
    "            elif isinstance(tp, str):\n"
    "                try:\n"
    "                    st.json(json.loads(tp))\n"
    "                except (json.JSONDecodeError, TypeError):\n"
    "                    st.code(tp)\n"
    "            else:\n"
    "                st.json(tp)\n"
    "        else:\n"
    "            _render_input_fallback(attrs, \"input.value\")\n"
    "\n"
    "    # --- Output block (collapsible) -----------------------------------------\n"
    "    with st.expander(\"\u2b06  \u8f93\u51fa\", expanded=True):\n"
    "        if kind == \"LLM\":\n"
    "            msgs = to_messages(canon(attrs, \"messages.output\"))\n"
    "            if msgs:\n"
    "                for m in msgs:\n"
    "                    role = (m.get(\"role\") or \"assistant\").lower()\n"
    "                    content = m.get(\"content\") or \"\"\n"
    "                    _render_msg(role, content)\n"
    "            else:\n"
    "                _render_input_fallback(attrs, \"output.value\")\n"
    "        elif kind == \"TOOL\":\n"
    "            tout = canon(attrs, \"tool.output\")\n"
    "            if tout is None:\n"
    "                st.caption(\"\uff08\u672a\u6355\u83b7\u8fd4\u56de\u7ed3\u679c\uff09\")\n"
    "            elif isinstance(tout, (dict, list)):\n"
    "                st.json(tout)\n"
    "            elif isinstance(tout, str):\n"
    "                try:\n"
    "                    parsed = json.loads(tout)\n"
    "                    if isinstance(parsed, (dict, list)):\n"
    "                        st.json(parsed)\n"
    "                    else:\n"
    "                        st.code(str(parsed))\n"
    "                except (json.JSONDecodeError, TypeError):\n"
    "                    if len(tout) > 6000:\n"
    "                        st.code(tout[:6000] + \"\\n\u2026(truncated)\")\n"
    "                    else:\n"
    "                        st.code(tout)\n"
    "            else:\n"
    "                st.code(str(tout))\n"
    "        else:\n"
    "            _render_input_fallback(attrs, \"output.value\")\n"
)
io_new = (
    "    # --- Input / Output side-by-side (headers aligned; each side scrolls independently) --\n"
    "    c_in, c_out = st.columns(2, gap='medium')\n"
    "\n"
    "    with c_in:\n"
    "        st.markdown('<div class=\"io-col-head in-head\">\u2b07  \u8f93\u5165</div>', unsafe_allow_html=True)\n"
    "        if kind == 'LLM':\n"
    "            msgs = to_messages(canon(attrs, 'messages.input'))\n"
    "            if msgs:\n"
    "                for m in msgs:\n"
    "                    role = (m.get('role') or 'user').lower()\n"
    "                    content_val = m.get('content') or ''\n"
    "                    _render_msg(role, content_val)\n"
    "                    for tc in m.get('tool_calls') or []:\n"
    "                        nm = tc.get('name') or 'tool'\n"
    "                        with st.expander(f'\U0001F527 {nm}'):\n"
    "                            st.json(tc.get('arguments'))\n"
    "            else:\n"
    "                _render_input_fallback(attrs, 'input.value')\n"
    "        elif kind == 'TOOL':\n"
    "            tp = canon(attrs, 'tool.parameters')\n"
    "            st.markdown('**\u5de5\u5177\u53c2\u6570\uff1a**')\n"
    "            if tp is None:\n"
    "                st.caption('\uff08\u672a\u6355\u83b7\u53c2\u6570\uff09')\n"
    "            elif isinstance(tp, str):\n"
    "                try:\n"
    "                    st.json(json.loads(tp))\n"
    "                except (json.JSONDecodeError, TypeError):\n"
    "                    st.code(tp)\n"
    "            else:\n"
    "                st.json(tp)\n"
    "        else:\n"
    "            _render_input_fallback(attrs, 'input.value')\n"
    "\n"
    "    with c_out:\n"
    "        st.markdown('<div class=\"io-col-head out-head\">\u2b06  \u8f93\u51fa</div>', unsafe_allow_html=True)\n"
    "        if kind == 'LLM':\n"
    "            msgs = to_messages(canon(attrs, 'messages.output'))\n"
    "            if msgs:\n"
    "                for m in msgs:\n"
    "                    role = (m.get('role') or 'assistant').lower()\n"
    "                    content_val = m.get('content') or ''\n"
    "                    _render_msg(role, content_val)\n"
    "            else:\n"
    "                _render_input_fallback(attrs, 'output.value')\n"
    "        elif kind == 'TOOL':\n"
    "            tout = canon(attrs, 'tool.output')\n"
    "            if tout is None:\n"
    "                st.caption('\uff08\u672a\u6355\u83b7\u8fd4\u56de\u7ed3\u679c\uff09')\n"
    "            elif isinstance(tout, (dict, list)):\n"
    "                st.json(tout)\n"
    "            elif isinstance(tout, str):\n"
    "                try:\n"
    "                    parsed = json.loads(tout)\n"
    "                    if isinstance(parsed, (dict, list)):\n"
    "                        st.json(parsed)\n"
    "                    else:\n"
    "                        st.code(str(parsed))\n"
    "                except (json.JSONDecodeError, TypeError):\n"
    "                    if len(tout) > 6000:\n"
    "                        st.code(tout[:6000] + '\\n\u2026(truncated)')\n"
    "                    else:\n"
    "                        st.code(tout)\n"
    "            else:\n"
    "                st.code(str(tout))\n"
    "        else:\n"
    "            _render_input_fallback(attrs, 'output.value')\n"
)
content = replace_once(content, io_old, io_new, "IO side-by-side")


# ===== Phase 7: structured _render_msg =====
# Find existing _render_msg
old_msg = '''def _render_msg(role: str, content: object) -> None:
    """Render a single LLM message body inside a 4-line scrollable card.

    Replaces st.chat_message, which forced a single-line bubble and
    horizontally scrolled long unbreakable tokens.
    """
'''
assert old_msg in content, "Phase 7: old _render_msg not found"
new_msg = '''def _render_msg(msg):
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
        f'<div class="msg-head">'
        f'<span>{icon}</span>'
        f'<span class="msg-role-label" style="color:{color}">{_esc(label)}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )
    meta_bits = []
    if tool_calls:
        meta_bits.append(f"\U0001F527 {len(tool_calls)} \u4e2a\u5de5\u5177\u8c03\u7528")
    if isinstance(content_val, list):
        meta_bits.append(f"\U0001F4DC {len(content_val)} \u4e2a\u5185\u5bb9\u5757")
    if meta_bits:
        st.markdown(
            '<div class="msg-meta">' + " &nbsp;\u00b7&nbsp; ".join(meta_bits) + '</div>',
            unsafe_allow_html=True,
        )
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
                    f'<div class="msg-part-block">'
                    f'<b>\U0001F527 \u5de5\u5177\u8c03\u7528</b>: '
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
                    f'<b>\U0001F4E5 \u5de5\u5177\u7ed3\u679c</b>:'
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
            with st.expander(f"\U0001F527 \u8c03\u7528 {name}"):
                st.json(args)
    st.markdown("</div>", unsafe_allow_html=True)
    with st.expander("\U0001F4CB \u539f\u59cb JSON"):
        st.json(msg)
    st.markdown("</div>", unsafe_allow_html=True)


'''
content = content.replace(old_msg, new_msg, 1)
print("Phase 7: _render_msg replaced")


# Update call sites
old_call_in = (
    "                    role = (m.get('role') or 'user').lower()\n"
    "                    content_val = m.get('content') or ''\n"
    "                    _render_msg(role, content_val)"
)
new_call_in = "                    _render_msg(m)"
content = replace_once(content, old_call_in, new_call_in, "msg call site (input)")

old_call_out = (
    "                    role = (m.get('role') or 'assistant').lower()\n"
    "                    content_val = m.get('content') or ''\n"
    "                    _render_msg(role, content_val)"
)
new_call_out = "                    _render_msg(m)"
content = replace_once(content, old_call_out, new_call_out, "msg call site (output)")


# ===== Phase 8: smart _render_input_fallback =====
old_fallback = '''def _render_input_fallback(attrs: dict, key: str) -> None:
    val = attrs.get(key)
    if val is None:
        st.caption(f"\uff08\u672a\u6355\u83b7 {key.split(chr(46))[0]} \uff09")
        return
    if isinstance(val, str):
        if len(val) > 4000:
            st.code(val[:4000] + "\\n\u2026(truncated)")
        else:
            st.code(val)
    else:
        st.json(val)
'''
new_fallback = '''def _render_input_fallback(attrs: dict, key: str) -> None:
    """Smart fallback for input/output values.

    If `val` is a JSON string we parse and render via st.json() for
    structure; otherwise we fall back to st.code() with truncation.
    """
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
'''
content = replace_once(content, old_fallback, new_fallback, "_render_input_fallback")


# ===== Phase 9: CSS additions =====
old_css = "/* ----- right metadata panel ----- */"
new_css = (
    "/* ----- trace card list (flowchart explorer left column) ----- */\n"
    ".trace-card {\n"
    "    background: rgba(255,255,255,0.03);\n"
    "    border: 1px solid rgba(255,255,255,0.08);\n"
    "    border-radius: 8px;\n"
    "    padding: 6px 8px;\n"
    "    margin-bottom: 6px;\n"
    "}\n"
    ".trace-card-active {\n"
    "    border-color: rgba(59,130,246,0.55);\n"
    "    background: rgba(59,130,246,0.10);\n"
    "}\n"
    "\n"
    "/* ----- right metadata panel ----- */"
)
content = replace_once(content, old_css, new_css, "trace-card CSS")

# Also extend msg-body max-height
old_body = "    max-height: 6em;\n    overflow-y: auto;\n    overflow-wrap: anywhere;\n    word-break: break-word;\n    padding: 6px 10px 8px 10px;\n    margin: 0;\n    font-size: 12.5px;\n    line-height: 1.45;\n    color: #d1d5db;\n}"
new_body = "    max-height: 18em;\n    overflow-y: auto;\n    overflow-wrap: anywhere;\n    word-break: break-word;\n    padding: 6px 10px 8px 10px;\n    margin: 0;\n    font-size: 12.5px;\n    line-height: 1.45;\n    color: #d1d5db;\n}\n.msg-card .msg-meta {\n    padding: 3px 10px;\n    font-size: 10.5px;\n    color: #9ca3af;\n    background: rgba(255,255,255,0.02);\n    border-bottom: 1px solid rgba(255,255,255,0.05);\n}\n.msg-card .msg-part-block {\n    margin: 6px 0;\n    padding: 6px 8px;\n    border-left: 2px solid rgba(59,130,246,0.5);\n    background: rgba(59,130,246,0.06);\n    border-radius: 0 4px 4px 0;\n    font-size: 11.5px;\n}\n.mermaid .nodeLabel, .mermaid .node rect, .mermaid .node polygon {\n    cursor: pointer;\n}"
content = replace_once(content, old_body, new_body, "msg-body CSS + meta + part-block")


open(p, "w", encoding="utf-8", newline="\n").write(content)
print(f"After Phase 4-9: {len(content.encode('utf-8'))} bytes")