import re
p = r"D:\my-projects\agent-monitor\viewer\naming\langchain.py"
with open(p, encoding="utf-8") as f:
    s = f.read()

# Use a list of (old, new) pairs and apply them sequentially
R = [
    ("\"Chain step\"", "\"\u94fe\u8def\u6b65\u9aa4\""),
    ("\"LLM call\"", "\"\u5927\u6a21\u578b\u8c03\u7528\""),
    ("\"Tool call\"", "\"\u5de5\u5177\u8c03\u7528\""),
    ("\"Agent\"", "\"\u667a\u80fd\u4f53\""),
    ("\"Retriever\"", "\"\u68c0\u7d22\""),
    ("\"Embedding\"", "\"\u5411\u91cf\u5316\""),
    ("\"Reranker\"", "\"\u91cd\u6392\u5e8f\""),
    ("\"Format prompt\"", "\"\u586b\u5145\u63d0\u793a\u8bcd\""),
    ("\"Parse response\"", "\"\u89e3\u6790\u54cd\u5e94\""),
    ("\"Evaluator\"", "\"\u8bc4\u4f30\""),
    ("\"Guardrail\"", "\"\u5b89\u5168\u68c0\u67e5\""),
    ("\"Unknown\"", "\"\u672a\u77e5\""),
    ("RunnableSequence\\n    \"\"\"Build a Mermaid `flowchart TD` source", "PLACEHOLDER"),  # avoid matching later
    ("\"Text splitter\"", "\"\u6587\u672c\u5206\u5272\""),
    ("\"Recursive text splitter\"", "\"\u9012\u5f52\u6587\u672c\u5206\u5272\""),
    ("\"PDF loader\"", "\"PDF \u52a0\u8f7d\u5668\""),
    ("\"Vector store retriever\"", "\"\u5411\u91cf\u5e93\u68c0\u7d22\""),
    ("\"Multi-query retriever\"", "\"\u591a\u67e5\u8be2\u68c0\u7d22\""),
    ("\"Contextual compressor\"", "\"\u4e0a\u4e0b\u6587\u538b\u7f29\""),
    ("\"Ensemble retriever\"", "\"\u878d\u5408\u68c0\u7d22\""),
    ("\"Self-query retriever\"", "\"\u81ea\u67e5\u8be2\u68c0\u7d22\""),
    ("\"Parent document retriever\"", "\"\u7236\u6587\u6863\u68c0\u7d22\""),
    ("\"Multi-task parallel\"", "\"\u591a\u4efb\u52a1\u5e76\u884c\""),
    ("\"Structured tool\"", "\"\u7ed3\u6784\u5316\u5de5\u5177\""),
    ("\"Base tool\"", "\"\u57fa\u7840\u5de5\u5177\""),
    ("\"Tool\"", "\"\u5de5\u5177\""),
    ("\"Parse pydantic\"", "\"\u7ed3\u6784\u5316\u6821\u9a8c\""),
    ("\"Parse JSON\"", "\"\u89e3\u6790 JSON\""),
    ("\"Retry parse\"", "\"\u91cd\u8bd5\u89e3\u6790\""),
    ("\"Output fixer\"", "\"\u8f93\u51fa\u4fee\u590d\""),
    ("\"Parse string\"", "\"\u89e3\u6790\u5b57\u7b26\u4e32\""),
    ("\"Parse XML\"", "\"\u89e3\u6790 XML\""),
    ("\"Format chat prompt\"", "\"\u586b\u5145\u5bf9\u8bdd\u63d0\u793a\u8bcd\""),
    ("\"Few-shot prompt\"", "\"\u5c11\u6837\u672c\u63d0\u793a\u8bcd\""),
    ("\"Pipeline prompt\"", "\"\u7ba1\u9053\u63d0\u793a\u8bcd\""),
    ("\"Messages placeholder\"", "\"\u6d88\u606f\u5360\u4f4d\u7b26\""),
    ("\"Base chat model\"", "\"\u57fa\u7840\u5bf9\u8bdd\u6a21\u578b\""),
    ("\"Base language model\"", "\"\u57fa\u7840\u8bed\u8a00\u6a21\u578b\""),
    ("\"Pass-through (assigned)\"", "\"\u900f\u4f20\uff08\u8d4b\u503c\uff09\""),
    ("\"Pass-through\"", "\"\u900f\u4f20\""),
    ("\"Lambda\"", "\"Lambda \u51fd\u6570\""),
    ("\"Assign input\"", "\"\u8f93\u5165\u8d4b\u503c\""),
    ("\"Argument binding\"", "\"\u53c2\u6570\u7ed1\u5b9a\""),
    ("\"Retry wrapper\"", "\"\u91cd\u8bd5\u5c01\u88c5\""),
    ("\"Fallback wrapper\"", "\"\u514d\u5e95\u8c03\u7528\""),
    ("\"With history\"", "\"\u5e26\u5386\u53f2\u8bb0\u5fc6\""),
    ("\"Conditional branch\"", "\"\u6761\u4ef6\u5206\u652f\""),
    ("\"Config wrapper\"", "\"Config \u5c01\u88c5\""),
    ("\"MRKL agent\"", "\"MRKL \u667a\u80fd\u4f53\""),
    ("\"ReAct agent\"", "\"ReAct \u667a\u80fd\u4f53\""),
    ("\"Plan and execute\"", "\"\u8ba1\u5212\u5e76\u6267\u884c\""),
    ("\"Self-ask with search\"", "\"\u81ea\u95ee\u81ea\u7b54\u641c\u7d22\""),
    ("\"Conversational agent\"", "\"\u5bf9\u8bdd\u667a\u80fd\u4f53\""),
    ("\"OpenAI Assistant agent\"", "\"OpenAI Assistant \u667a\u80fd\u4f53\""),
    ("\"Chain step (nested)\"", "\"\u94fe\u8def\u6b65\u9aa4\uff08\u5d4c\u5957\uff09\""),
    ("\"Parallel branches\"", "\"\u5e76\u884c\u5206\u652f\""),
    ("\"Parallel: \"", "\"\u591a\u4efb\u52a1\u5e76\u884c\uff1a\""),
    ("\"Agent executor\"", "\"\u667a\u80fd\u4f53\u6267\u884c\""),
]
# Translate the file by finding "Chain step" -> "\u94fe\u8def\u6b65\u9aa4" etc.
# But the file uses a different layout: "Chain step" appears as the value for NamingRule
# Look at the file structure - it has entries like:
#   NamingRule(re.compile(r"^RunnableSequence$"), "Chain step"),

# Let me do find/replace for each pattern
for old, new in R:
    if old in s:
        s = s.replace(old, new, 1)
        print(f"  OK: {old[:30]}")
# Also handle: "_parallel_label" return: "Parallel: " + -> "\u591a\u4efb\u52a1\u5e76\u884c\uff1a" +
# Need a separate replace
s = s.replace("\"Parallel: \" +\", \"\"\u591a\u4efb\u52a1\u5e76\u884c\uff1a\" +\"")
if "\"\u591a\u4efb\u52a1\u5e76\u884c\uff1a\" +\"" in s:
    print("  OK: parallel prefix")
s = s.replace("\"Parallel branches\"", "\"\u591a\u4efb\u52a1\u5e76\u884c\"")

# Also translate the docstring comments and other text
extra = [
    ("# -------- LCEL internal wrappers / plumbing --------",
     "# -------- LCEL internal wrappers / plumbing --------"),
    ("RunnableParallel<tools...>  -> \"Multi-task parallel (n)\"",
     "RunnableParallel<tools...>  -> \"\u591a\u4efb\u52a1\u5e76\u884c\uff08n\uff09\""),
    ("RunnableSequence with TOOL child spans -> \"Tool agent\"",
     "RunnableSequence with TOOL child spans -> \"\u5de5\u5177\u578b\u667a\u80fd\u4f53\""),
    ("RunnableSequence with RETRIEVER child spans -> \"Retrieval chain\"",
     "RunnableSequence with RETRIEVER child spans -> \"\u68c0\u7d22\u94fe\""),
    ("RunnableSequence (Prompt -> LLM -> Parser) -> \"LLM chain\"",
     "RunnableSequence (Prompt -> LLM -> Parser) -> \"LLM \u8c03\u7528\u94fe\""),
    ("RunnableSequence (just LLM) -> \"LLM call\"",
     "RunnableSequence (just LLM) -> \"\u5927\u6a21\u578b\u8c03\u7528\""),
]
for old, new in extra:
    if old in s and old != new:
        s = s.replace(old, new, 1)
        print(f"  OK extra: {old[:30]}")

with open(p, "w", encoding="utf-8", newline="\n") as f:
    f.write(s)
print("langchain.py done")
