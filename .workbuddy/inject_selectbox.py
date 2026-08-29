import sys
sys.stdout.reconfigure(encoding="utf-8")
content = open(r"D:\my-projects\agent-monitor\viewer.py", encoding="utf-8").read()

# Find the else branch and insert selectbox fallback AFTER the _render_mermaid_html call
old_block = (
    "        _render_mermaid_html(\n"
    "            _build_mermaid(sel_spans, focus=None),\n"
    "            height=720, key_prefix='full',\n"
    "        )\n"
    "        if focus and focus not in all_by_id:\n"
    "            if 'focus' in st.query_params:\n"
    "                del st.query_params['focus']\n"
    "            st.rerun()\n"
)

new_block = (
    "        _render_mermaid_html(\n"
    "            _build_mermaid(sel_spans, focus=None),\n"
    "            height=720, key_prefix='full',\n"
    "        )\n"
    "        # Manual fallback selector (in case Mermaid click is blocked)\n"
    "        with st.expander('\\u5982\\u679c\\u70b9\\u51fb\\u65e0\\u6548\\uff0c\\u53ef\\u4ee5\\u5728\\u8fd9\\u91cc\\u624b\\u52a8\\u9009\\u62e9\\u4e00\\u4e2a span \\u805a\\u7126', expanded=False):\n"
    "            span_options = [(s['span_id'], _span_display_name(s)) for s in sel_spans]\n"
    "            span_map = dict(span_options)\n"
    "            labels = [name for _, name in span_options]\n"
    "            picked = st.selectbox('\\u9009\\u62e9 span', options=labels, key='manual_focus_pick', index=0)\n"
    "            if st.button('\\u805a\\u7126\\u5230\\u8be5 span', key='manual_focus_btn') and picked:\n"
    "                target_id = next(sid for sid, n in span_options if n == picked)\n"
    "                st.query_params['focus'] = target_id\n"
    "                st.rerun()\n"
    "        if focus and focus not in all_by_id:\n"
    "            if 'focus' in st.query_params:\n"
    "                del st.query_params['focus']\n"
    "            st.rerun()\n"
)

if old_block in content:
    content = content.replace(old_block, new_block, 1)
    print("selectbox fallback added")
else:
    print("Pattern not found")
open(r"D:\my-projects\agent-monitor\viewer.py", "w", encoding="utf-8").write(content)