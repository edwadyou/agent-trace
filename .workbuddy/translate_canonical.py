import io
p = r'D:\\my-projects\\agent-monitor\\viewer\\canonical.py'
with open(p, 'r', encoding='utf-8') as f:
    src = f.read()

replacements = [
    ('"LLM call"', '"\u5927\u6a21\u578b\u8c03\u7528"'),
    ('"Chain step"', '"\u94fe\u8def\u6b65\u9aa4"'),
    ('"Tool call"', '"\u5de5\u5177\u8c03\u7528"'),
    ('"Agent"', '"\u667a\u80fd\u4f53"'),
    ('"Retriever"', '"\u68c0\u7d22"'),
    ('"Embedding"', '"\u5411\u91cf\u5316"'),
    ('"Reranker"', '"\u91cd\u6392\u5e8f"'),
    ('"Format prompt"', '"\u586b\u5145\u63d0\u793a\u8bcd"'),
    ('"Parse response"', '"\u89e3\u6790\u54cd\u5e94"'),
    ('"Evaluator"', '"\u8bc4\u4f30"'),
    ('"Guardrail"', '"\u5b89\u5168\u68c0\u67e5"'),
    ('"Unknown"', '"\u672a\u77e5"'),
]
for old, new in replacements:
    if old not in src:
        print('NOT FOUND:', old)
        continue
    src = src.replace(old, new)

with open(p, 'w', encoding='utf-8') as f:
    f.write(src)
print('Done')
