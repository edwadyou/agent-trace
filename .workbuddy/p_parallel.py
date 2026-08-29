p = r"D:\my-projects\agent-monitor\viewer\naming\langchain.py"
with open(p, encoding="utf-8") as f:
    s = f.read()
old = chr(34) + "Parallel: " + chr(34) + " +"
new = chr(34) + chr(0x591a) + chr(0x4efb) + chr(0x52a1) + chr(0x5e76) + chr(0x884c) + chr(0xff1a) + " +"
print("Found:", s.count(old))
s = s.replace(old, new)
with open(p, "w", encoding="utf-8", newline="\n") as f:
    f.write(s)
print("Done")
