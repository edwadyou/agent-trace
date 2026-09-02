"""LangChain / LangGraph span-name translation rules.

All `display` strings are localised to Chinese; proper nouns (brand names,
framework class names, tool names) are preserved in English.
"""
from __future__ import annotations
import re
from typing import Match

from ._base import NamingRule


def _parallel_label(_raw, m, _kind):
    """``RunnableParallel<web_search,knowledge_base,social_listening>`` -> ``多任务并行: ...``."""
    inner = (m.group(1) or "").strip("<> ")
    if not inner:
        return "多任务并行", True
    items = [s.strip() for s in inner.split(",") if s.strip()]
    return "多任务并行：" + ", ".join(items), True


def _underscore_callable(raw, _m, _kind):
    """``_web_search`` -> ``Web search`` (drops the leading underscore, title-cases)."""
    body = raw.lstrip("_")
    if not body:
        return raw, True
    pretty = body.replace("_", " ").strip()
    if pretty == pretty.lower():
        pretty = pretty.title()
    return pretty, True


def _lc_chatmodel_label(raw, _m, _kind):
    """Choose model-specific LLM label by provider. Brand names stay English."""
    if "ChatOpenAI" in raw:        return "大模型调用（OpenAI）", True
    if "ChatAnthropic" in raw:     return "大模型调用（Anthropic）", True
    if "ChatGoogle" in raw:        return "大模型调用（Google）", True
    if "ChatBedrock" in raw:       return "大模型调用（Bedrock）", True
    if "ChatGroq" in raw:          return "大模型调用（Groq）", True
    if "ChatMistral" in raw:       return "大模型调用（Mistral）", True
    if "ChatFireworks" in raw:     return "大模型调用（Fireworks）", True
    return "大模型调用", True


LANGCHAIN_RULES = [
    NamingRule(re.compile(r"^RunnableSequence$"),               "链路步骤"),
    NamingRule(re.compile(r"^RunnableSequence\(RunnableSequence"), "链路步骤（嵌套）"),
    NamingRule(re.compile(r"^RunnableParallel(?P<inner>.*)$"),     computed=_parallel_label),
    NamingRule(re.compile(r"^RunnableBranch\b"),                  "条件分支"),
    NamingRule(re.compile(r"^RunnablePassthroughThrough\..*$"),   "透传（赋值）"),
    NamingRule(re.compile(r"^RunnablePassthrough$"),              "透传"),
    NamingRule(re.compile(r"^RunnableLambda$"),                   "Lambda 函数"),
    NamingRule(re.compile(r"^RunnableAssign$"),                   "输入赋值"),
    NamingRule(re.compile(r"^RunnableBinding$"),                  "参数绑定"),
    NamingRule(re.compile(r"^RunnableRetry$"),                    "重试封装"),
    NamingRule(re.compile(r"^RunnableWithFallbacks$"),            "免底调用"),
    NamingRule(re.compile(r"^RunnableConfig$"),                   "Config 封装"),
    NamingRule(re.compile(r"^RunnableWithMessageHistory$"),       "带历史记忆"),
    NamingRule(re.compile(r"^__start__$"),                       "开始", visible=False),
    NamingRule(re.compile(r"^__end__$"),                         "结束", visible=False),
    NamingRule(re.compile(r"^Channel(Read|Write)\b"),            "Channel op", visible=False),
    NamingRule(re.compile(r"^_RoutedNode"),                       "Routing wrapper", visible=False),
    NamingRule(re.compile(r"^Chat(OpenAI|Anthropic|GoogleGenerativeAI|Bedrock|Groq|Mistral|Fireworks|Ollama|VertexAI)\b.*"), computed=_lc_chatmodel_label, require_kind="LLM"),
    NamingRule(re.compile(r"^ChatOpenAI$|^ChatAnthropic$|^ChatGoogle.*$|^ChatBedrock.*$|^ChatGroq$|^ChatMistral.*$"), "大模型调用", require_kind="LLM"),
    NamingRule(re.compile(r"^BaseChatModel$|^BaseLanguageModel$"), "语言模型", require_kind="LLM"),
    NamingRule(re.compile(r"^LLM\b"),                            "大模型调用", require_kind="LLM"),
    NamingRule(re.compile(r"^ChatPromptTemplate\b.*"),           "填充对话提示词", require_kind="PROMPT"),
    NamingRule(re.compile(r"^PromptTemplate\b.*"),               "填充提示词", require_kind="PROMPT"),
    NamingRule(re.compile(r"^FewShotPromptTemplate\b.*"),         "少样本提示词", require_kind="PROMPT"),
    NamingRule(re.compile(r"^PipelinePromptTemplate\b.*"),       "管道提示词", require_kind="PROMPT"),
    NamingRule(re.compile(r"^MessagesPlaceholder\b.*"),          "消息占位符", require_kind="PROMPT"),
    NamingRule(re.compile(r"^PydanticOutputParser\b.*"),          "结构化校验"),
    NamingRule(re.compile(r"^JsonOutputParser\b.*"),             "解析 JSON"),
    NamingRule(re.compile(r"^RetryOutputParser\b.*"),            "重试解析"),
    NamingRule(re.compile(r"^OutputFixingParser\b.*"),           "输出修复"),
    NamingRule(re.compile(r"^StrOutputParser\b.*"),             "解析字符串"),
    NamingRule(re.compile(r"^XMLOutputParser\b.*"),             "解析 XML"),
    NamingRule(re.compile(r"^StructuredTool(\.[A-Za-z]+)?$"),    "工具定义"),
    NamingRule(re.compile(r"^BaseTool$"),                        "工具定义"),
    NamingRule(re.compile(r"^Tool(\.(invoke|ainvoke|run|arun))?$"), "工具", require_kind="TOOL"),
    NamingRule(re.compile(r"^VectorStoreRetriever\b.*"),         "向量库检索", require_kind="RETRIEVER"),
    NamingRule(re.compile(r"^MultiQueryRetriever\b.*"),          "多查询检索", require_kind="RETRIEVER"),
    NamingRule(re.compile(r"^ContextualCompressionRetriever\b.*"), "上下文压缩", require_kind="RETRIEVER"),
    NamingRule(re.compile(r"^EnsembleRetriever\b.*"),            "融合检索", require_kind="RETRIEVER"),
    NamingRule(re.compile(r"^SelfQueryRetriever\b.*"),           "自查询检索", require_kind="RETRIEVER"),
    NamingRule(re.compile(r"^ParentDocumentRetriever\b.*"),      "父文档检索", require_kind="RETRIEVER"),
    NamingRule(re.compile(r"^BaseRetriever\b.*"),                "检索器", require_kind="RETRIEVER"),
    NamingRule(re.compile(r"^AgentExecutor\b.*"),                "智能体执行", require_kind="AGENT"),
    NamingRule(re.compile(r"^MRKLChain$"),                     "MRKL 智能体"),
    NamingRule(re.compile(r"^ReActChain$"),                     "ReAct 智能体"),
    NamingRule(re.compile(r"^PlanAndExecute(\..*)?$"),           "计划并执行", require_kind="AGENT"),
    NamingRule(re.compile(r"^SelfAskWithSearchChain$"),          "自问自答搜索"),
    NamingRule(re.compile(r"^ConversationalAgent\b.*"),          "对话智能体", require_kind="AGENT"),
    NamingRule(re.compile(r"^OpenAIAssistantAgent\b.*"),        "OpenAI Assistant 智能体", require_kind="AGENT"),
    NamingRule(re.compile(r"^PyPDFLoader$"),                     "PDF 加载器"),
    NamingRule(re.compile(r"^CharacterTextSplitter\b.*"),       "文本分割"),
    NamingRule(re.compile(r"^RecursiveCharacterTextSplitter\b.*"), "递归文本分割"),
    NamingRule(re.compile(r"^_(?P<rest>[a-z][a-z0-9_]*)$"),     computed=_underscore_callable),
]
