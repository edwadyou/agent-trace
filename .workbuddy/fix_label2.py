import sys
sys.stdout.reconfigure(encoding="utf-8")
content = open(r"D:\my-projects\agent-monitor\viewer.py", encoding="utf-8").read()
old = "    name = re.sub(r'[\\[\\](){}<>|`]', ' ', name).strip()"
new = "    name = re.sub(r'[\\\"\\\\#;|]', ' ', name).strip()"
count = content.count(old)
print("Count:", count)
if count:
    content = content.replace(old, new, 1)
    print("Fixed")
open(r"D:\my-projects\agent-monitor\viewer.py", "w", encoding="utf-8").write(content)