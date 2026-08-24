
"""LangChain / LangGraph span-name translation rules.

This file is the ONLY place you ever need to edit when adding a new LangChain
class to display. Common patterns:

  * LCEL internal primitives       -> Chain step / Parallel / Conditional / etc.
  * LLM chat model class names      -> LLM call (with provider chip)
  * Prompt template classes         -> Format prompt
  * Output parsers                  -> Parse response
  * Tool classes                    -> Tool call
  * Retriever classes               -> Retriever
  * Agent classes                   -> Agent run
  * LangGraph plumbing              -> hidden by default
  * User-defined underscore-prefix  -> friendly-readability tweak
"""
from __future__ import annotations
import re
from typing import Match

from ._base import NamingRule


# ---------------------------------------------------------------------------
# Dynamic label callbacks
# ---------------------------------------------------------------------------
def _parallel_label(_raw: str, m: Match[str], _kind: str) -> tuple[str, bool]:
    """``RunnableParallel<web_search,knowledge_base>`` -> ``Parallel: web_search, knowledge_base``."""
    inner = (m.group(1) or "").strip("<> ")
    if not inner:
        return "Parallel branches", True
    items = [s.strip() for s in inner.split(",") if s.strip()]
    return "Parallel: " + ", ".join(items), True


def _underscore_callable(raw: str, _m: Match[str], _kind: str) -> tuple[str, bool]:
    """``_web_search`` -> ``Web search`` (drops the leading underscore, title-cases)."""
    body = raw.lstrip("_")
    if not body:
        return raw, True
    pretty = body.replace("_", " ").strip()
    # Title-case if lower_snake_case; otherwise leave alone
    if pretty == pretty.lower():
        pretty = pretty.title()
    return pretty, True


def _lc_chatmodel_label(raw: str, _m: Match[str], _kind: str) -> tuple[str, bool]:
    """Choose model-specific LLM label by provider."""
    if "ChatOpenAI" in raw:        return "LLM (OpenAI)", True
    if "ChatAnthropic" in raw:     return "LLM (Anthropic)", True
    if "ChatGoogle" in raw:        return "LLM (Google)", True
    if "ChatBedrock" in raw:       return "LLM (Bedrock)", True
    if "ChatGroq" in raw:          return "LLM (Groq)", True
    if "ChatMistral" in raw:       return "LLM (Mistral)", True
    if "ChatFireworks" in raw:     return "LLM (Fireworks)", True
    return "LLM call", True


# ---------------------------------------------------------------------------
# Rule list
# ---------------------------------------------------------------------------
LANGCHAIN_RULES = [
    # -------- LCEL internal wrappers / plumbing --------
    NamingRule(re.compile(r"^RunnableSequence$"),
               "Chain step"),
    NamingRule(re.compile(r"^RunnableSequence\(RunnableSequence"),
               "Chain step (nested)"),
    NamingRule(re.compile(r"^RunnableParallel(?P<inner>.*)$"),
               computed=_parallel_label),
    NamingRule(re.compile(r"^RunnableBranch\b"),
               "Conditional branch"),
    NamingRule(re.compile(r"^RunnablePassthroughThrough\..*$"),
               "Pass-through (assigned)"),
    NamingRule(re.compile(r"^RunnablePassthrough$"),
               "Pass-through"),
    NamingRule(re.compile(r"^RunnableLambda$"),
               "Lambda"),
    NamingRule(re.compile(r"^RunnableAssign$"),
               "Assign input"),
    NamingRule(re.compile(r"^RunnableBinding$"),
               "Bound args"),
    NamingRule(re.compile(r"^RunnableRetry$"),
               "Retry wrapper"),
    NamingRule(re.compile(r"^RunnableWithFallbacks$"),
               "Fallback wrapper"),
    NamingRule(re.compile(r"^RunnableConfig$"),
               "Config wrapper"),
    NamingRule(re.compile(r"^RunnableWithMessageHistory$"),
               "With message history"),

    # -------- LangGraph primitives (hidden by default) --------
    NamingRule(re.compile(r"^__start__$"),
               "Start", visible=False),
    NamingRule(re.compile(r"^__end__$"),
               "End", visible=False),
    NamingRule(re.compile(r"^Channel(Read|Write)\b"),
               "Channel op", visible=False),
    NamingRule(re.compile(r"^_RoutedNode"),
               "Routing wrapper", visible=False),

    # -------- LLM chat-model classes (kind == LLM) --------
    NamingRule(re.compile(r"^Chat(OpenAI|Anthropic|GoogleGenerativeAI|Bedrock|Groq|Mistral|Fireworks|Ollama|Fireworks|VertexAI)\b.*"),
               computed=_lc_chatmodel_label, require_kind="LLM"),
    NamingRule(re.compile(r"^ChatOpenAI$|^ChatAnthropic$|^ChatGoogle.*$|^ChatBedrock.*$|^ChatGroq$|^ChatMistral.*$"),
               "LLM call", require_kind="LLM"),
    NamingRule(re.compile(r"^BaseChatModel$|^BaseLanguageModel$"),
               "Language model", require_kind="LLM"),
    NamingRule(re.compile(r"^LLM\b"),
               "LLM call", require_kind="LLM"),

    # -------- Prompt templates (kind == PROMPT) --------
    NamingRule(re.compile(r"^ChatPromptTemplate\b.*"),
               "Format chat prompt", require_kind="PROMPT"),
    NamingRule(re.compile(r"^PromptTemplate\b.*"),
               "Format prompt", require_kind="PROMPT"),
    NamingRule(re.compile(r"^FewShotPromptTemplate\b.*"),
               "Few-shot prompt", require_kind="PROMPT"),
    NamingRule(re.compile(r"^PipelinePromptTemplate\b.*"),
               "Pipeline prompt", require_kind="PROMPT"),
    NamingRule(re.compile(r"^MessagesPlaceholder\b.*"),
               "Messages placeholder", require_kind="PROMPT"),

    # -------- Output parsers (often CHAIN; users expect "Parse response") --------
    NamingRule(re.compile(r"^PydanticOutputParser\b.*"),
               "Parse pydantic"),
    NamingRule(re.compile(r"^JsonOutputParser\b.*"),
               "Parse JSON"),
    NamingRule(re.compile(r"^RetryOutputParser\b.*"),
               "Retry parse"),
    NamingRule(re.compile(r"^OutputFixingParser\b.*"),
               "Output fixer"),
    NamingRule(re.compile(r"^StrOutputParser\b.*"),
               "Parse string"),
    NamingRule(re.compile(r"^XMLOutputParser\b.*"),
               "Parse XML"),

    # -------- Tools --------
    NamingRule(re.compile(r"^StructuredTool(\.[A-Za-z]+)?$"),
               "Tool definition"),
    NamingRule(re.compile(r"^BaseTool$"),
               "Tool definition"),
    NamingRule(re.compile(r"^Tool(\.(invoke|ainvoke|run|arun))?$"),
               "Tool", require_kind="TOOL"),

    # -------- Retrievers (kind == RETRIEVER) --------
    NamingRule(re.compile(r"^VectorStoreRetriever\b.*"),
               "Vector store retriever", require_kind="RETRIEVER"),
    NamingRule(re.compile(r"^MultiQueryRetriever\b.*"),
               "Multi-query retriever", require_kind="RETRIEVER"),
    NamingRule(re.compile(r"^ContextualCompressionRetriever\b.*"),
               "Contextual compressor", require_kind="RETRIEVER"),
    NamingRule(re.compile(r"^EnsembleRetriever\b.*"),
               "Ensemble retriever", require_kind="RETRIEVER"),
    NamingRule(re.compile(r"^SelfQueryRetriever\b.*"),
               "Self-query retriever", require_kind="RETRIEVER"),
    NamingRule(re.compile(r"^ParentDocumentRetriever\b.*"),
               "Parent document retriever", require_kind="RETRIEVER"),
    NamingRule(re.compile(r"^BaseRetriever\b.*"),
               "Retriever", require_kind="RETRIEVER"),

    # -------- Agents (kind == AGENT) --------
    NamingRule(re.compile(r"^AgentExecutor\b.*"),
               "Agent run", require_kind="AGENT"),
    NamingRule(re.compile(r"^MRKLChain$"),
               "MRKL agent"),
    NamingRule(re.compile(r"^ReActChain$"),
               "ReAct agent"),
    NamingRule(re.compile(r"^PlanAndExecute(\..*)?$"),
               "Plan and execute", require_kind="AGENT"),
    NamingRule(re.compile(r"^SelfAskWithSearchChain$"),
               "Self-ask with search"),
    NamingRule(re.compile(r"^ConversationalAgent\b.*"),
               "Conversational agent", require_kind="AGENT"),
    NamingRule(re.compile(r"^OpenAIAssistantAgent\b.*"),
               "OpenAI Assistant agent", require_kind="AGENT"),

    # -------- Document loaders / splitters --------
    NamingRule(re.compile(r"^PyPDFLoader$"),
               "PDF loader"),
    NamingRule(re.compile(r"^CharacterTextSplitter\b.*"),
               "Text splitter"),
    NamingRule(re.compile(r"^RecursiveCharacterTextSplitter\b.*"),
               "Recursive text splitter"),

    # -------- User-defined private callables (underscore-prefix convention) --------
    NamingRule(re.compile(r"^_(?P<rest>[a-z][a-z0-9_]*)$"),
               computed=_underscore_callable),
]
