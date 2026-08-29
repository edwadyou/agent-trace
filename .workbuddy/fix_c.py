import sys
sys.stdout.reconfigure(encoding="utf-8")
p = r"D:\my-projects\agent-monitor\viewer.py"
content = open(p, encoding="utf-8").read()

# === Phase C: fix Mermaid click + remove manual select expander ===
# C1: update focusSpan JS to use window.top with fallbacks
old_focus_js = (
    "  window.focusSpan = function(nodeId) {\\n\"\n"
    "    var spanId = (nodeId || \\"\\").replace(/^n_/, \\"\\").replace(/_/g, \\"-\\");\\n\"\n"
    "    if (!spanId) return;\\n\"\n"
    "    var url = new URL(window.parent.location.href);\\n\"\n"
    "    url.searchParams.set(\\"focus\\", spanId);\\n\"\n"
    "    window.parent.location.href = url.toString();\\n\"\n"
    "  };\\n"
)
new_focus_js = (
    "  window.focusSpan = function(nodeId) {\\n\"\n"
    "    var spanId = (nodeId || \\"\\").replace(/^n_/, \\"\\").replace(/_/g, \\"-\\");\\n\"\n"
    "    if (!spanId) return;\\n\"\n"
    "    var url = new URL(window.top.location.href);\\n\"\n"
    "    url.searchParams.set(\\"focus\\", spanId);\\n\"\n"
    "    var target = window.top;\\n\"\n"
    "    try { target.location.href = url.toString(); }\\n\"\n"
    "    catch (e1) {\\n\"\n"
    "      try { window.parent.location.href = url.toString(); }\\n\"\n"
    "      catch (e2) { window.location.href = url.toString(); }\\n\"\n"
    "    }\\n\"\n"
    "  };\\n"
)
if old_focus_js in content:
    content = content.replace(old_focus_js, new_focus_js, 1)
    print("C1: focusSpan JS now uses window.top with fallbacks")
else:
    print("C1: focusSpan JS pattern not found")

# C2: also update DOM delegation click in same render function
old_dom_click = (
    "        const url = new URL(window.parent.location.href);\\n\"\n"
    "        url.searchParams.set('focus', spanId);\\n\"\n"
    "        window.parent.location.href = url.toString();\\n\"\n"
    "      });\\n\"\n"
    "    });\\n\"\n"
    "  });\\n\"\n"
    "  });\\n\"\n"
)
new_dom_click = (
    "        var url = new URL(window.top.location.href);\\n\"\n"
    "        url.searchParams.set('focus', spanId);\\n\"\n"
    "        try { window.top.location.href = url.toString(); }\\n\"\n"
    "        catch (e1) {\\n\"\n"
    "          try { window.parent.location.href = url.toString(); }\\n\"\n"
    "          catch (e2) { window.location.href = url.toString(); }\\n\"\n"
    "        }\\n\"\n"
    "      });\\n\"\n"
    "    });\\n\"\n"
    "  });\\n\"\n"
)
# Look at the exact pattern - it appears in DOM delegation. Let me handle it more carefully.
# The old_dom_click is hard to match exactly. Let me find it first.
import re
m = re.search(r"const url = new URL\(window\.parent\.location\.href\);.*?window\.parent\.location\.href = url\.toString\(\);", content, re.DOTALL)
if m:
    new_block = m.group(0).replace("window.parent", "window.top", 1)
    # Add try/catch
    new_block = new_block.replace(
        "window.top.location.href = url.toString();",
        "try { window.top.location.href = url.toString(); }\n        catch (e1) { try { window.parent.location.href = url.toString(); } catch (e2) { window.location.href = url.toString(); } }"
    )
    content = content[:m.start()] + new_block + content[m.end():]
    print("C2: DOM delegation click updated to use window.top with fallbacks")
else:
    print("C2: DOM delegation click block not found")

# C3: remove the manual focus selectbox expander
old_expander = (
    "    with st.expander(\\n\"\n"
    "        \"\\u5982\\u679c\\u70b9\\u51fb\\u65e0\\u6548\\uff0c\\u53ef\\u4ee5\\u5728\\u8fd9\\u91cc\\u624b\\u52a8\\u9009\\u62e9\\u4e00\\u4e2a span\\u805a\\u7126\\",\\n\"\n"
    "        expanded=False,\\n\"\n"
    "    ):\\n\"\n"
    "        span_options = [(s[\\"span_id\\"], _span_display_name(s)) for s in sel_spans]\\n\"\n"
    "        labels = [name for _, name in span_options]\\n\"\n"
    "        if not labels:\\n\"\n"
    "            st.caption(\"\\u65e0\\u53ef\\u9009 span\")\\n\"\n"
    "        else:\\n\"\n"
    "            picked = st.selectbox(\\n\"\n"
    "                \"\\u9009\\u62e9 span\",\\n\"\n"
    "                options=labels,\\n\"\n"
    "                key=\\"manual_focus_pick\\",\\n\"\n"
    "                index=0,\\n\"\n"
    "            )\\n\"\n"
    "            if st.button(\"\\u805a\\u7126\\u5230\\u8be5 span\", key=\\"manual_focus_btn\\"):\\n\"\n"
    "                target_id = next(sid for sid, n in span_options if n == picked)\\n\"\n"
    "                _jump_to_span(target_id)\\n\"\n"
)
if old_expander in content:
    content = content.replace(old_expander, "", 1)
    print("C3: manual focus expander removed")
else:
    print("C3: expander pattern not found - searching...")

open(p, "w", encoding="utf-8", newline="\n").write(content)