p = r"D:\my-projects\agent-monitor\viewer\canonical.py"
with open(p, encoding="utf-8") as f:
    s = f.read()
R = [
    (chr(34) + "LLM call" + chr(34), chr(34) + "\u5927\u6a21\u578b\u8c03\u7528" + chr(34)),
    (chr(34) + "Chain step" + chr(34), chr(34) + "\u94fe\u8def\u6b65\u9aa4" + chr(34)),
    (chr(34) + "Tool call" + chr(34), chr(34) + "\u5de5\u5177\u8c03\u7528" + chr(34)),
    (chr(34) + "Agent" + chr(34), chr(34) + "\u667a\u80fd\u4f53" + chr(34)),
    (chr(34) + "Retriever" + chr(34), chr(34) + "\u68c0\u7d22" + chr(34)),
    (chr(34) + "Embedding" + chr(34), chr(34) + "\u5411\u91cf\u5316" + chr(34)),
    (chr(34) + "Reranker" + chr(34), chr(34) + "\u91cd\u6392\u5e8f" + chr(34)),
    (chr(34) + "Format prompt" + chr(34), chr(34) + "\u586b\u5145\u63d0\u793a\u8bcd" + chr(34)),
    (chr(34) + "Parse response" + chr(34), chr(34) + "\u89e3\u6790\u54cd\u5e94" + chr(34)),
    (chr(34) + "Evaluator" + chr(34), chr(34) + "\u8bc4\u4f30" + chr(34)),
    (chr(34) + "Guardrail" + chr(34), chr(34) + "\u5b89\u5168\u68c0\u67e5" + chr(34)),
    (chr(34) + "Unknown" + chr(34), chr(34) + "\u672a\u77e5" + chr(34)),
]
for old, new in R:
    if old in s:
        s = s.replace(old, new, 1)
with open(p, "w", encoding="utf-8", newline="\n") as f:
    f.write(s)
print("canonical.py done")
