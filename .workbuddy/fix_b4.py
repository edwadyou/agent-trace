p = r"D:\my-projects\agent-monitor\viewer\naming\langchain.py"
with open(p, "rb") as f:
    data = f.read()
# Replace 0x5c 0x5c 0x62 with 0x5c 0x62 (remove one backslash)
# 3 bytes -> 2 bytes
three = bytes([0x5c, 0x5c, 0x62])
two = bytes([0x5c, 0x62])
# But we need to be careful: not all "\\\\b" should be replaced, only in regex context
# Actually, looking at the file, "\\\\b" only appears in regex patterns (re.compile)
# Let me just replace all occurrences
new = data.replace(three, two)
print("Replacements:", data.count(three))
with open(p, "wb") as f:
    f.write(new)
# Verify
data = open(p, encoding="utf-8").read()
print("After count of " + chr(0x5c)+chr(0x5c)+chr(0x62) + ":", data.count(chr(0x5c)+chr(0x5c)+chr(0x62)))
