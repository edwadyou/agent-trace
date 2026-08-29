# -*- coding: utf-8 -*-
"""Complete langchain.py rewrite with all Chinese."""
LC = """\"\"\"LangChain / LangGraph span-name translation rules.

All `display` strings are localised to Chinese; proper nouns (brand names,
framework class names, tool names) are preserved in English.
\"\"\"
from __future__ import annotations
import re
from typing import Match

from ._base import NamingRule


def _parallel_label(_raw, m, _kind):
    \"\"\"``RunnableParallel<web_search,knowledge_base,social_listening>`` -> ``\u591a\u4efb\u52a1\u5e76\u884c: ...``.\"\"\"
    inner = (m.group(1) or "").strip("<> ")
    if not inner:
        return "\u591a\u4efb\u52a1\u5e76\u884c", True
    items = [s.strip() for s in inner.split(",") if s.strip()]
    return "\u591a\u4efb\u52a1\u5e76\u884c\uff1a" + ", ".join(items), True


def _underscore_callable(raw, _m, _kind):
    \"\"\"``_web_search`` -> ``Web search`` (drops the leading underscore, title-cases).\"\"\"
    body = raw.lstrip("_")
    if not body:
        return raw, True
    pretty = body.replace("_", " ").strip()
    if pretty == pretty.lower():
        pretty = pretty.title()
    return pretty, True


def _lc_chatmodel_label(raw, _m, _kind):
    \"\"\"Choose model-specific LLM label by provider. Brand names stay English.\"\"\"
    if "ChatOpenAI" in raw:        return "\u5927\u6a21\u578b\u8c03\u7528\uff08OpenAI\uff09", True
    if "ChatAnthropic" in raw:     return "\u5927\u6a21\u578b\u8c03\u7528\uff08Anthropic\uff09", True
    if "ChatGoogle" in raw:        return "\u5927\u6a21\u578b\u8c03\u7528\uff08Google\uff09", True
    if "ChatBedrock" in raw:       return "\u5927\u6a21\u578b\u8c03\u7528\uff08Bedrock\uff09", True
    if "ChatGroq" in raw:          return "\u5927\u6a21\u578b\u8c03\u7528\uff08Groq\uff09", True
    if "ChatMistral" in raw:       return "\u5927\u6a21\u578b\u8c03\u7528\uff08Mistral\uff09", True
    if "ChatFireworks" in raw:     return "\u5927\u6a21\u578b\u8c03\u7528\uff08Fireworks\uff09", True
    return "\u5927\u6a21\u578b\u8c03\u7528", True


LANGCHAIN_RULES = [
    NamingRule(re.compile(r"^RunnableSequence$"),               "\u94fe\u8def\u6b65\u9aa4"),
    NamingRule(re.compile(r"^RunnableSequence\(RunnableSequence"), "\u94fe\u8def\u6b65\u9aa4\uff08\u5d4c\u5957\uff09"),
    NamingRule(re.compile(r"^RunnableParallel(?P<inner>.*)$"),     computed=_parallel_label),
    NamingRule(re.compile(r"^RunnableBranch\b"),                  "\u6761\u4ef6\u5206\u652f"),
    NamingRule(re.compile(r"^RunnablePassthroughThrough\..*$"),   "\u900f\u4f20\uff08\u8d4b\u503c\uff09"),
    NamingRule(re.compile(r"^RunnablePassthrough$"),              "\u900f\u4f20"),
    NamingRule(re.compile(r"^RunnableLambda$"),                   "Lambda \u51fd\u6570"),
    NamingRule(re.compile(r"^RunnableAssign$"),                   "\u8f93\u5165\u8d4b\u503c"),
    NamingRule(re.compile(r"^RunnableBinding$"),                  "\u53c2\u6570\u7ed1\u5b9a"),
    NamingRule(re.compile(r"^RunnableRetry$"),                    "\u91cd\u8bd5\u5c01\u88c5"),
    NamingRule(re.compile(r"^RunnableWithFallbacks$"),            "\u514d\u5e95\u8c03\u7528"),
    NamingRule(re.compile(r"^RunnableConfig$"),                   "Config \u5c01\u88c5"),
    NamingRule(re.compile(r"^RunnableWithMessageHistory$"),       "\u5e26\u5386\u53f2\u8bb0\u5fc6"),
    NamingRule(re.compile(r"^__start__$"),                       "\u5f00\u59cb", visible=False),
    NamingRule(re.compile(r"^__end__$"),                         "\u7ed3\u675f", visible=False),
    NamingRule(re.compile(r"^Channel(Read|Write)\b"),            "Channel op", visible=False),
    NamingRule(re.compile(r"^_RoutedNode"),                       "Routing wrapper", visible=False),
    NamingRule(re.compile(r"^Chat(OpenAI|Anthropic|GoogleGenerativeAI|Bedrock|Groq|Mistral|Fireworks|Ollama|Fireworks|VertexAI)\b.*"), computed=_lc_chatmodel_label, require_kind="LLM"),
    NamingRule(re.compile(r"^ChatOpenAI$|^ChatAnthropic$|^ChatGoogle.*$|^ChatBedrock.*$|^ChatGroq$|^ChatMistral.*$"), "\u5927\u6a21\u578b\u8c03\u7528", require_kind="LLM"),
    NamingRule(re.compile(r"^BaseChatModel$|^BaseLanguageModel$"), "\u8bed\u8a00\u6a21\u578b", require_kind="LLM"),
    NamingRule(re.compile(r"^LLM\b"),                            "\u5927\u6a21\u578b\u8c03\u7528", require_kind="LLM"),
    NamingRule(re.compile(r"^ChatPromptTemplate\b.*"),           "\u586b\u5145\u5bf9\u8bdd\u63d0\u793a\u8bcd", require_kind="PROMPT"),
    NamingRule(re.compile(r"^PromptTemplate\b.*"),               "\u586b\u5145\u63d0\u793a\u8bcd", require_kind="PROMPT"),
    NamingRule(re.compile(r"^FewShotPromptTemplate\b.*"),         "\u5c11\u6837\u672c\u63d0\u793a\u8bcd", require_kind="PROMPT"),
    NamingRule(re.compile(r"^PipelinePromptTemplate\b.*"),       "\u7ba1\u9053\u63d0\u793a\u8bcd", require_kind="PROMPT"),
    NamingRule(re.compile(r"^MessagesPlaceholder\b.*"),          "\u6d88\u606f\u5360\u4f4d\u7b26", require_kind="PROMPT"),
    NamingRule(re.compile(r"^PydanticOutputParser\b.*"),          "\u7ed3\u6784\u5316\u6821\u9a8c"),
    NamingRule(re.compile(r"^JsonOutputParser\b.*"),             "\u89e3\u6790 JSON"),
    NamingRule(re.compile(r"^RetryOutputParser\b.*"),            "\u91cd\u8bd5\u89e3\u6790"),
    NamingRule(re.compile(r"^OutputFixingParser\b.*"),           "\u8f93\u51fa\u4fee\u590d"),
    NamingRule(re.compile(r"^StrOutputParser\b.*"),             "\u89e3\u6790\u5b57\u7b26\u4e32"),
    NamingRule(re.compile(r"^XMLOutputParser\b.*"),             "\u89e3\u6790 XML"),
    NamingRule(re.compile(r"^StructuredTool(\.[A-Za-z]+)?$"),    "\u5de5\u5177\u5b9a\u4e49"),
    NamingRule(re.compile(r"^BaseTool$"),                        "\u5de5\u5177\u5b9a\u4e49"),
    NamingRule(re.compile(r"^Tool(\.(invoke|ainvoke|run|arun))?$"), "\u5de5\u5177", require_kind="TOOL"),
    NamingRule(re.compile(r"^VectorStoreRetriever\b.*"),         "\u5411\u91cf\u5e93\u68c0\u7d22", require_kind="RETRIEVER"),
    NamingRule(re.compile(r"^MultiQueryRetriever\b.*"),          "\u591a\u67e5\u8be2\u68c0\u7d22", require_kind="RETRIEVER"),
    NamingRule(re.compile(r"^ContextualCompressionRetriever\b.*"), "\u4e0a\u4e0b\u6587\u538b\u7f29", require_kind="RETRIEVER"),
    NamingRule(re.compile(r"^EnsembleRetriever\b.*"),            "\u878d\u5408\u68c0\u7d22", require_kind="RETRIEVER"),
    NamingRule(re.compile(r"^SelfQueryRetriever\b.*"),           "\u81ea\u67e5\u8be2\u68c0\u7d22", require_kind="RETRIEVER"),
    NamingRule(re.compile(r"^ParentDocumentRetriever\b.*"),      "\u7236\u6587\u6863\u68c0\u7d22", require_kind="RETRIEVER"),
    NamingRule(re.compile(r"^BaseRetriever\b.*"),                "\u68c0\u7d22\u5668", require_kind="RETRIEVER"),
    NamingRule(re.compile(r"^AgentExecutor\b.*"),                "\u667a\u80fd\u4f53\u6267\u884c", require_kind="AGENT"),
    NamingRule(re.compile(r"^MRKLChain$"),                     "MRKL \u667a\u80fd\u4f53"),
    NamingRule(re.compile(r"^ReActChain$"),                     "ReAct \u667a\u80fd\u4f53"),
    NamingRule(re.compile(r"^PlanAndExecute(\..*)?$"),           "\u8ba1\u5212\u5e76\u6267\u884c", require_kind="AGENT"),
    NamingRule(re.compile(r"^SelfAskWithSearchChain$"),          "\u81ea\u95ee\u81ea\u7b54\u641c\u7d22"),
    NamingRule(re.compile(r"^ConversationalAgent\b.*"),          "\u5bf9\u8bdd\u667a\u80fd\u4f53", require_kind="AGENT"),
    NamingRule(re.compile(r"^OpenAIAssistantAgent\b.*"),        "OpenAI Assistant \u667a\u80fd\u4f53", require_kind="AGENT"),
    NamingRule(re.compile(r"^PyPDFLoader$"),                     "PDF \u52a0\u8f7d\u5668"),
    NamingRule(re.compile(r"^CharacterTextSplitter\b.*"),       "\u6587\u672c\u5206\u5272"),
    NamingRule(re.compile(r"^RecursiveCharacterTextSplitter\b.*"), "\u9012\u5f52\u6587\u672c\u5206\u5272"),
    NamingRule(re.compile(r"^_(?P<rest>[a-z][a-z0-9_]*)$"),     computed=_underscore_callable),
]
"""
p = r"D:\my-projects\agent-monitor\viewer\naming\langchain.py"
with open(p, "w", encoding="utf-8", newline="\n") as f:
    f.write(LC)
print("langchain.py rewritten")
