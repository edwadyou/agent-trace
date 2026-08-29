p = r"D:\my-projects\agent-monitor\viewer\naming\langchain.py"
with open(p, "rb") as f:
    data = f.read()
# 4-byte pattern: 0x5c 0x5c 0x5c 0x5c 0x62 = "\\\\\\\\b" in Python string
# Wait, let me check what I actually want to replace
# Currently: b"\\b"  (2 chars: backslash + b, but in Python source as b"\\\\b" 4 bytes)
# Desired: same
# Let me just look at the raw bytes
idx = data.find(b"ChatPromptTemplate")
print("Raw bytes at this position:")
print("  hex:", data[idx:idx+25].hex())
print("  raw:", data[idx:idx+25])
