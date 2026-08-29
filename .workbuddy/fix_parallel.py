p = r"D:\my-projects\agent-monitor\viewer\naming\langchain.py"
with open(p, encoding="utf-8") as f:
    s = f.read()
# Fix the broken line: "?????? + ", ".join(items), True
# Should be: "??????: " + ", ".join(items), True
# Replace "?????? +" (which is what got written) with the proper string
old = chr(34) + chr(0x591a) + chr(0x4efb) + chr(0x52a1) + chr(0x5e76) + chr(0x884c) + chr(0xff1a) + " + " + chr(34)
new = chr(34) + chr(0x591a) + chr(0x4efb) + chr(0x52a1) + chr(0x5e76) + chr(0x884c) + chr(0xff1a) + chr(34) + " + "
print("Found old:", s.count(old))
s = s.replace(old, new)
# Also fix "Parallel branches" in line 31
old2 = chr(34) + "Parallel branches" + chr(34)
new2 = chr(34) + chr(0x591a) + chr(0x4efb) + chr(0x52a1) + chr(0x5e76) + chr(0x884c) + chr(34)
print("Found Parallel branches:", s.count(old2))
s = s.replace(old2, new2)
with open(p, "w", encoding="utf-8", newline="\n") as f:
    f.write(s)
print("Done")
