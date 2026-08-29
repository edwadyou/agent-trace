# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding="utf-8")
content = open(r"D:\my-projects\agent-monitor\viewer.py", encoding="utf-8").read()
idx = content.find("def _render_msg(")
end_idx = content.find("def _render_run_tab", idx)
block = content[idx:end_idx]
print("Block length:", len(block))
print("Last 50 chars repr:", repr(block[-50:]))
# Find the line with closing </div></div>
import re
m = re.search(r'    st\.markdown\("</div></div>", unsafe_allow_html=True\)', block)
if m:
    print("Closing found at offset:", m.start(), "of block")
    print("After closing:", repr(block[m.end():m.end()+10]))