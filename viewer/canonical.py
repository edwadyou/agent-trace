"""Canonical schema for the agent-monitor viewer.

This is the single source of truth for:
  - Layer 1: SpanKind  -> (icon, color-name, display label)
  - Layer 3: canonical field name -> ordered attribute paths

OpenInference already collapses run_type / framework span.kind into the 11
enums below, so per-framework field-name tables are NOT needed in this file.
Adding a new framework requires NO edit here - only ``naming/<framework>.py``.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Layer 1: 11 canonical span kinds (from OpenInference SpanKind enum)
# ---------------------------------------------------------------------------
# value: (icon, color-name, display label)
SPAN_KINDS: dict[str, tuple[str, str, str]] = {
    "LLM":       ("\U0001F916", "blue",   "LLM call"),
    "CHAIN":     ("\U0001F517", "green",  "Chain step"),
    "TOOL":      ("\U0001F527", "orange", "Tool call"),
    "AGENT":     ("\U0001F9E0", "yellow", "Agent"),
    "RETRIEVER": ("\U0001F4DA", "purple", "Retriever"),
    "EMBEDDING": ("\U0001F4D0", "cyan",   "Embedding"),
    "RERANKER":  ("\U0001F3AF", "violet", "Reranker"),
    "PROMPT":    ("\U0001F4DD", "olive",  "Format prompt"),
    "PARSER":    ("\U0001F50D", "gray",   "Parse response"),
    "EVALUATOR": ("\u2696\uFE0F",  "tan",   "Evaluator"),
    "GUARDRAIL": ("\U0001F6E1\uFE0F", "red",    "Guardrail"),
    "UNKNOWN":   ("\u2754",   "gray",   "Unknown"),
}

# CSS colors per color-name (referenced by viewer.py)
COLORS: dict[str, str] = {
    "blue":   "#3b82f6",
    "green":  "#10b981",
    "orange": "#f59e0b",
    "yellow": "#eab308",
    "purple": "#a855f7",
    "cyan":   "#06b6d4",
    "violet": "#8b5cf6",
    "olive":  "#84cc16",
    "gray":   "#6b7280",
    "tan":    "#d6b985",
    "red":    "#ef4444",
}

# ---------------------------------------------------------------------------
# Layer 3: canonical key -> ordered list of OI / OTel / raw attribute paths.
#
# Order matters - first non-empty value wins. Adding a new framework or
# provider rarely requires editing this map; most agents already emit
# OpenInference attributes.
# ---------------------------------------------------------------------------
FIELD_ALIASES: dict[str, list[str]] = {
    # ---- LLM identity ----
    "model": [
        "llm.model_name",
        "llm.model",
        "gen_ai.request.model",
        "gen_ai.response.model",
        "response.model",
        "model",
    ],

    # ---- Token counts ----
    "tokens.input": [
        "llm.token_count.prompt",
        "gen_ai.usage.input_tokens",
        "usage.prompt_tokens",
        "usage.input_tokens",
        "usage.promptTokenCount",
        "response_metadata.token_usage.prompt_tokens",
        "response_metadata.token_usage.input_tokens",
    ],
    "tokens.output": [
        "llm.token_count.completion",
        "gen_ai.usage.output_tokens",
        "usage.completion_tokens",
        "usage.output_tokens",
        "usage.candidatesTokenCount",
        "response_metadata.token_usage.completion_tokens",
        "response_metadata.token_usage.output_tokens",
    ],
    "tokens.total": [
        "llm.token_count.total",
        "gen_ai.usage.total_tokens",
        "usage.total_tokens",
        "response_metadata.token_usage.total_tokens",
    ],
    "tokens.cache_read": [
        "llm.token_count.prompt_details.cache_read",
        "gen_ai.usage.cache_read_input_tokens",
        "usage.prompt_tokens_details.cached_tokens",
        "usage.input_token_details.cache_read",
    ],
    "tokens.reasoning": [
        "llm.token_count.completion_details.reasoning",
        "gen_ai.usage.reasoning_tokens",
        "usage.completion_tokens_details.reasoning_tokens",
        "usage.output_token_details.reasoning",
    ],

    # ---- Messages ----
    "messages.input": [
        "llm.input_messages",
        "gen_ai.input.messages",
    ],
    "messages.output": [
        "llm.output_messages",
        "gen_ai.output.messages",
    ],

    # ---- Tool ----
    "tool.name": [
        "tool.name",
        "gen_ai.tool.name",
    ],
    "tool.description": [
        "tool.description",
        "gen_ai.tool.description",
    ],
    "tool.parameters": [
        "tool.parameters",
        "tool.call.function.arguments",
        "gen_ai.tool.call.arguments",
    ],
    "tool.output": [
        "tool.call.function.output",
        "gen_ai.tool.call.result",
    ],

    # ---- Retrieval ----
    "retrieval.documents": [
        "retrieval.documents",
        "gen_ai.retrieval.documents",
    ],

    # ---- Invocation params ----
    "invocation.temperature": [
        "llm.invocation_parameters.temperature",
        "gen_ai.request.temperature",
        "invocation_parameters.temperature",
    ],
    "invocation.max_tokens": [
        "llm.invocation_parameters.max_tokens",
        "gen_ai.request.max_tokens",
        "invocation_parameters.max_tokens",
    ],
    "invocation_params_json": [
        "llm.invocation_parameters",
        "gen_ai.request",
        "invocation_parameters",
    ],

    # ---- Session / thread / user ----
    "session.id": [
        "metadata.session_id",
        "metadata.thread_id",
        "thread_id",
        "gen_ai.conversation.id",
        "session_id",
    ],
    "user.id": [
        "metadata.user_id",
        "user_id",
        "gen_ai.user.id",
    ],
    "tags": [
        "tag.tags",
        "metadata.tags",
        "tags",
        "opik.tags",
        "opik_tags",
    ],

    # ---- Model provider ----
    "model.provider": [
        "llm.provider",
        "llm.system",
        "gen_ai.system",
    ],
}
