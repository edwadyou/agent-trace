p = r"D:\my-projects\agent-monitor\viewer\naming\langchain.py"
with open(p, "rb") as f:
    data = f.read()
# Replace 4-byte \\\\b (from my over-replacement) with 2-byte \\b
old = b"\\\\\\\\b"  # was: 0x5c 0x5c 0x5c 0x5c 0x62 (4 backslashes + b)
# Actually let me just check raw bytes
idx = data.find(b"ChatPromptTemplate")
print("Before:", data[idx:idx+30].hex())
# Replace 0x5c5c5c62 (4 bytes) with 0x5c62 (2 bytes)
old_bytes = b"\\\\b"  # 4 bytes
new_bytes = b"\\\\b"  # 2 bytes... wait, in Python source the backslash counts
# Let me be explicit
old4 = bytes([0x5c, 0x5c, 0x5c, 0x5c, 0x62])  # \\\\b in file
new2 = bytes([0x5c, 0x62])  # \\b in file
data = data.replace(old4, new2)
print("After:", data[idx:idx+30].hex())
with open(p, "wb") as f:
    f.write(data)
print("Fixed")
