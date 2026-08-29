import sys
sys.stdout.reconfigure(encoding="utf-8")
content = open(r"D:\my-projects\agent-monitor\viewer.py", encoding="utf-8").read()

# Find the safe regex inside _mermaid_label
idx = content.find("def _mermaid_label")
print("_mermaid_label at:", idx)
# Find the regex line after that
section = content[idx:idx+800]
import re
m = re.search(r"    name = re\.sub\(.*?strip\(\)", section, re.DOTALL)
if m:
    print("Found:", repr(m.group()))
else:
    print("not found in section")

# Replace it
old = "    name = re.sub(r\"[\\[\\](){}<>|`]\", \" \", name).strip()"
new = "    name = re.sub(r\"[\\\"\\\\#;|]\", \" \", name).strip()"
count = content.count(old)
print("Count of old pattern:", count)
if count:
    content = content.replace(old, new, 1)
    print("Fixed")
open(r"D:\my-projects\agent-monitor\viewer.py", "w", encoding="utf-8").write(content)