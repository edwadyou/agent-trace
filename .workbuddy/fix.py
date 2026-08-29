import sys
content = open(r"D:\my-projects\agent-monitor\.workbuddy\patch_p7p8.py", encoding="utf-8").read()
content = content.replace("+ NEW_msg +", "+ NEW_MSG +")
open(r"D:\my-projects\agent-monitor\.workbuddy\patch_p7p8.py", "w", encoding="utf-8").write(content)
print("Fixed")