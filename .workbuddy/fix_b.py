p = r"D:\my-projects\agent-monitor\viewer\naming\langchain.py"
with open(p, "rb") as f:
    data = f.read()
# Replace literal backspace (0x08) with the 2 characters \\b (backslash + b)
# This is for re.compile patterns where \\b is the regex word boundary
data = data.replace(chr(0x08).encode("ascii"), b"\\\\b")
with open(p, "wb") as f:
    f.write(data)
print("Fixed 0x08 -> b in langchain.py")
# Verify
data = open(p, encoding="utf-8").read()
import sys
sys.stdout.reconfigure(encoding="utf-8")
for needle in ["\u94fe\u8def\u6b65\u9aa4", "\u5927\u6a21\u578b\u8c03\u7528"]:
    print(f"  {needle!r}: {data.count(needle)}")
