# -*- coding: utf-8 -*-
# This file was split out of the original ``viewer.py`` single-file app.
# Do not edit by hand where avoidable; keep the module boundaries clean.
from __future__ import annotations

import json

import streamlit as st

from .format import _esc
from .structured import _render_structured, _try_parse_envelope, _try_parse_json_string


def _render_msg(msg):

    """Render a single LLM message as a structured card."""

    if isinstance(msg, dict) and isinstance(msg.get("message"), dict):

        inner = msg["message"]

        tool_calls = msg.get("tool_calls") or []

    else:

        inner = msg if isinstance(msg, dict) else {"content": msg}

        tool_calls = []

    role = (inner.get("role") or "user").lower()

    content_val = inner.get("content") or ""

    palette = {

        "user":      ("👤", "#10b981", "用户"),

        "human":     ("👤", "#10b981", "用户"),

        "assistant": ("🤖", "#3b82f6", "助手"),

        "ai":        ("🤖", "#3b82f6", "助手"),

        "system":    ("⚙️", "#9ca3af", "系统"),

        "tool":      ("🔧", "#f59e0b", "工具"),

        "function":  ("🔧", "#f59e0b", "工具"),

    }

    key = role or "user"

    icon, color, label = palette.get(key, ("💬", "#6b7280", key.title() if key else "消息"))

    st.markdown(

        f'<div class="msg-card" style="border-left:3px solid {color};">'

        f'<div class="msg-head"><span>{icon}</span>'

        f'<span class="msg-role-label" style="color:{color}">{_esc(label)}</span></div>',

        unsafe_allow_html=True,

    )

    meta_bits = []

    if tool_calls:

        meta_bits.append(f"🔧 {len(tool_calls)} 个工具调用")

    if isinstance(content_val, list):

        meta_bits.append(f"📜 {len(content_val)} 个内容块")

    if meta_bits:

        st.markdown('<div class="msg-meta">' + " &nbsp;·&nbsp; ".join(meta_bits) + '</div>', unsafe_allow_html=True)

    st.markdown('<div class="msg-body">', unsafe_allow_html=True)

    if not content_val:

        st.markdown("<em style='color:#6b7280'>（空）</em>", unsafe_allow_html=True)

    elif isinstance(content_val, str):

        # First try LangGraph-style envelope, then fenced JSON, then plain.

        _env = _try_parse_envelope(content_val)

        if _env is None:

            _env = _try_parse_json_string(content_val)

        if _env is not None:

            _render_structured(_env)

        else:

            st.markdown(_esc(content_val))

    elif isinstance(content_val, list):

        for part in content_val:

            if not isinstance(part, dict):

                st.markdown(_esc(str(part)))

                continue

            ptype = part.get("type")

            if ptype == "text":

                _part = part.get("text", "")

                _env = _try_parse_envelope(_part)

                if _env is None:

                    _env = _try_parse_json_string(_part)

                if _env is not None:

                    _render_structured(_env)

                else:

                    st.markdown(_esc(_part))

            elif ptype == "tool_use":

                inp = part.get("input", {})

                if not isinstance(inp, dict):

                    inp = {"value": inp}

                st.markdown(

                    f'<div class="msg-part-block"><b>🔧 工具调用</b>: '

                    f'<code>{_esc(part.get("name", "?"))}</code><br/>'

                    f'<pre style="margin:4px 0;padding:6px 8px;background:rgba(0,0,0,0.25);'

                    f'border-radius:4px;font-size:11.5px;white-space:pre-wrap;word-break:break-all">'

                    f'{_esc(json.dumps(inp, ensure_ascii=False, indent=2)[:600])}</pre></div>',

                    unsafe_allow_html=True,

                )

            elif ptype == "tool_result":

                res = part.get("content", "")

                st.markdown(

                    f'<div class="msg-part-block"><b>📥 工具结果</b>:'

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

            with st.expander(f"🔧 调用 {name}"):

                st.json(args)

    st.markdown("</div>", unsafe_allow_html=True)

    with st.expander("📋 原始 JSON"):

        st.json(msg)

    st.markdown("</div>", unsafe_allow_html=True)


__all__ = ['_render_msg']
