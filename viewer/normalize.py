"""Field-name normalization for the agent-monitor viewer.

Public functions:
    span_kind(attrs)              -> canonical OI enum value (LLM / CHAIN / ...)
    canon(attrs, key)             -> read a canonical field (model / tokens.* / ...)
    to_messages(raw)              -> normalize OpenAI / OI / Anthropic messages shape
    friendly_name(name, kind)     -> translate framework-internal span.name

These functions read raw ``span["attributes"]`` dict and return either a clean
python value or ``None``. They never raise on missing keys.
"""
from __future__ import annotations
import json
import re
from typing import Any

from .canonical import FIELD_ALIASES
from .naming import friendly_name as _naming_friendly_name


# -----------------------------------------------------------------------------
# Span kind
# -----------------------------------------------------------------------------
def span_kind(attrs: dict | None) -> str:
    """Return the canonical OI span.kind for an attributes dict.

    Looks at ``openinference.span.kind`` first, then ``kind`` if attrs is the
    raw top-level span record (we support both shapes).
    """
    if not isinstance(attrs, dict):
        return "UNKNOWN"
    val = attrs.get("openinference.span.kind")
    if val is None:
        val = attrs.get("kind")
    if val is None:
        return "UNKNOWN"
    return str(val).upper()


# -----------------------------------------------------------------------------
# Dotted path reader
# -----------------------------------------------------------------------------
def _read_dotted(d: Any, path: str) -> Any:
    """Read a dotted path against a nested dict, with a flat-key fallback.

    Two shapes are supported:

        1. Nested-dict form:   d["llm"]["token_count"]["prompt"]
        2. Flat-key form:      d["llm.token_count.prompt"]

    The OpenInference JSONL exporter (agent_monitor.jsonl_exporter) flattens
    LLM attributes to top-level dotted KEYS, so consumers must read both
    shapes. Nested walk is tried first; flat-key lookup is the fallback.
    """
    if not isinstance(d, dict):
        return None
    # 1) nested walk
    cur: Any = d
    for seg in path.split("."):
        if not isinstance(cur, dict):
            cur = None
            break
        cur = cur.get(seg)
        if cur is None:
            break
    if cur is not None and cur != "":
        return cur
    # 2) flat-key fallback (e.g. exporter wrote "llm.token_count.prompt" as one key)
    flat = d.get(path)
    if flat is not None and flat != "":
        return flat
    return None


# -----------------------------------------------------------------------------
# canon() - the workhorse
# -----------------------------------------------------------------------------
def canon(attrs: dict | None, key: str, default: Any = None) -> Any:
    """Read a canonical field from raw OpenInference attributes.

    Tries each alias path in ``FIELD_ALIASES[key]`` in order. Returns the first
    non-None / non-empty value. For ``tokens.*`` keys, also tries LangChain
    response JSON (where token counts often live inside the serialized
    ``output.value`` JSON, not as separate attributes).

    Args:
        attrs:   raw ``span["attributes"]`` dict (or top-level span dict)
        key:     one of the canonical keys in ``canonical.FIELD_ALIASES``
        default: returned when nothing matches

    Returns:
        python int / str / dict / list / None
    """
    if not isinstance(attrs, dict):
        return default

    # 1) explicit attribute paths (OI / OTel / raw)
    for path in FIELD_ALIASES.get(key, []):
        v = _read_dotted(attrs, path)
        if v is None or v == "":
            continue
        # OI stores messages.* as JSON strings; we parse on demand for canon().
        if key.startswith("messages.") and isinstance(v, str):
            try:
                parsed = json.loads(v)
                if parsed:
                    return parsed
            except (json.JSONDecodeError, TypeError):
                pass
            return v
        return v

    # 2) LangChain fallback: token counts inside the JSON output.value
    if key.startswith("tokens."):
        v = _lc_extract_token(attrs, key)
        if v is not None:
            return v

    return default


def _lc_extract_token(attrs: dict, key: str) -> int | None:
    """Find token counts hidden inside a JSON-serialized ``output.value``.

    LangChain stores response token info on the AIMessage object, which the
    OpenInference instrumentor sometimes embeds as a JSON string. We walk that
    JSON looking for usage_metadata / response_metadata.token_usage fields.
    """
    raw_output = attrs.get("output.value")
    if not isinstance(raw_output, str):
        return None
    try:
        data = json.loads(raw_output)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(data, dict):
        return None

    # (list of paths-as-tuples; each path is a mix of dict-keys and int-indexes)
    CANDIDATES: dict[str, list[tuple[Any, ...]]] = {
        # LangChain serializes AIMessage as a langchain_core "lc" envelope:
        #   generations[0][0].message.kwargs.{usage_metadata|response_metadata.token_usage}
        # Older OpenInference payloads skip `.kwargs`. Try both shapes.
        "tokens.input": [
            ("generations", 0, 0, "message", "kwargs", "usage_metadata", "input_tokens"),
            ("generations", 0, 0, "message", "kwargs", "response_metadata", "token_usage", "prompt_tokens"),
            ("generations", 0, 0, "message", "kwargs", "response_metadata", "token_usage", "input_tokens"),
            ("generations", 0, 0, "message", "usage_metadata", "input_tokens"),
            ("generations", 0, 0, "message", "response_metadata", "token_usage", "prompt_tokens"),
            ("generations", 0, 0, "message", "response_metadata", "token_usage", "input_tokens"),
            ("usage_metadata", "input_tokens"),
            ("token_usage", "prompt_tokens"),
        ],
        "tokens.output": [
            ("generations", 0, 0, "message", "kwargs", "usage_metadata", "output_tokens"),
            ("generations", 0, 0, "message", "kwargs", "response_metadata", "token_usage", "completion_tokens"),
            ("generations", 0, 0, "message", "kwargs", "response_metadata", "token_usage", "output_tokens"),
            ("generations", 0, 0, "message", "usage_metadata", "output_tokens"),
            ("generations", 0, 0, "message", "response_metadata", "token_usage", "completion_tokens"),
            ("generations", 0, 0, "message", "response_metadata", "token_usage", "output_tokens"),
            ("usage_metadata", "output_tokens"),
            ("token_usage", "completion_tokens"),
        ],
        "tokens.total": [
            ("generations", 0, 0, "message", "kwargs", "usage_metadata", "total_tokens"),
            ("generations", 0, 0, "message", "kwargs", "response_metadata", "token_usage", "total_tokens"),
            ("generations", 0, 0, "message", "usage_metadata", "total_tokens"),
            ("generations", 0, 0, "message", "response_metadata", "token_usage", "total_tokens"),
            ("usage_metadata", "total_tokens"),
            ("token_usage", "total_tokens"),
        ],
        "tokens.cache_read": [
            ("generations", 0, 0, "message", "kwargs", "usage_metadata", "input_token_details", "cache_read"),
            ("generations", 0, 0, "message", "kwargs", "response_metadata", "token_usage",
             "prompt_tokens_details", "cached_tokens"),
            ("generations", 0, 0, "message", "usage_metadata", "input_token_details", "cache_read"),
            ("generations", 0, 0, "message", "response_metadata", "token_usage",
             "prompt_tokens_details", "cached_tokens"),
        ],
        "tokens.reasoning": [
            ("generations", 0, 0, "message", "kwargs", "usage_metadata", "output_token_details", "reasoning"),
            ("generations", 0, 0, "message", "kwargs", "response_metadata", "token_usage",
             "completion_tokens_details", "reasoning_tokens"),
            ("generations", 0, 0, "message", "usage_metadata", "output_token_details", "reasoning"),
            ("generations", 0, 0, "message", "response_metadata", "token_usage",
             "completion_tokens_details", "reasoning_tokens"),
        ],
    }
    for path in CANDIDATES.get(key, []):
        cur: Any = data
        ok = True
        for seg in path:
            if isinstance(seg, int):
                if not isinstance(cur, list) or seg >= len(cur):
                    ok = False
                    break
                cur = cur[seg]
            else:
                if not isinstance(cur, dict) or seg not in cur:
                    ok = False
                    break
                cur = cur[seg]
        if ok and isinstance(cur, (int, float)) and not isinstance(cur, bool):
            return int(cur)
    return None


# -----------------------------------------------------------------------------
# to_messages()
# -----------------------------------------------------------------------------
def to_messages(raw: Any) -> list[dict]:
    """Normalize raw messages into a unified ``[{role, content, tool_calls}]`` list.

    Handles three input shapes:
      - OI normalized:   ``[{"message": {"role":..., "content":..., "tool_calls":[{"tool_call":{"function":...}}]}}]``
      - OpenAI raw:      ``[{"role":..., "content":..., "tool_calls":[{"function": {...}}]}]``
      - Anthropic raw:   ``[{"role":..., "content":[{"type":"text",...}]}]``

    Returns ``[]`` if input can't be parsed.
    """
    if raw is None or raw == "":
        return []
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return []
    if not isinstance(raw, list):
        return []

    out: list[dict] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue

        # --- OI shape ---
        if "message" in entry and isinstance(entry["message"], dict):
            m = entry["message"]
            out.append({
                "role":       _coerce_role(m.get("role")),
                "content":    _flatten_content(m.get("content")),
                "tool_calls": _normalize_tool_calls(m.get("tool_calls"), "tool_call.function")
                if m.get("tool_calls") else [],
            })
            continue

        # --- OpenAI shape ---
        if "role" in entry:
            out.append({
                "role":       _coerce_role(entry.get("role")),
                "content":    _flatten_content(entry.get("content")),
                "tool_calls": _normalize_tool_calls(entry.get("tool_calls"), "function")
                if entry.get("tool_calls") else [],
            })
            continue

    return out


def _coerce_role(role: Any) -> str:
    """Map raw role strings to a small canonical set."""
    if not role:
        return "user"
    r = str(role).lower()
    if r in {"ai", "assistant", "model", "bot"}:
        return "assistant"
    if r in {"human", "user", "person"}:
        return "user"
    if r in {"system", "developer", "instruction"}:
        return "system"
    if r in {"tool", "function", "tool_call"}:
        return "tool"
    return r


def _flatten_content(content: Any) -> str:
    """Stringify content (handles str / list-of-parts / multimodal)."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for piece in content:
            if not isinstance(piece, dict):
                parts.append(str(piece))
                continue
            ptype = piece.get("type")
            if ptype in ("text", "input_text", "output_text"):
                if "text" in piece:
                    parts.append(piece["text"])
            elif ptype in ("image_url", "input_image"):
                url = None
                if "image_url" in piece and isinstance(piece["image_url"], dict):
                    url = piece["image_url"].get("url")
                elif "image_url" in piece:
                    url = piece["image_url"]
                parts.append("\U0001F4F7 [" + (url or "image") + "]")
            elif ptype in ("tool_use", "tool_result"):
                parts.append(json.dumps(piece, ensure_ascii=False)[:200])
            else:
                parts.append("[" + str(ptype) + "] " +
                             json.dumps(piece, ensure_ascii=False)[:200])
        return "\n".join(parts)
    return str(content)


def _normalize_tool_calls(tool_calls: Any, nested_path: str) -> list[dict]:
    """Normalize tool_calls list to ``[{"name", "arguments"}]`` dicts."""
    if not isinstance(tool_calls, list):
        return []
    out: list[dict] = []
    for tc in tool_calls:
        if not isinstance(tc, dict):
            continue
        fn: Any = tc
        for seg in nested_path.split("."):
            if not isinstance(fn, dict):
                fn = None
                break
            fn = fn.get(seg)
        if not isinstance(fn, dict):
            continue
        name = fn.get("name", "")
        args = fn.get("arguments", "")
        if isinstance(args, str) and args.strip().startswith(("{", "[")):
            try:
                args = json.loads(args)
            except (json.JSONDecodeError, TypeError):
                pass
        out.append({"name": name, "arguments": args})
    return out


# -----------------------------------------------------------------------------
# friendly_name() (passthrough to .naming)
# -----------------------------------------------------------------------------
def friendly_name(name: str, kind: str) -> tuple[str, bool]:
    """Translate framework-internal span.name to (display_name, visible)."""
    return _naming_friendly_name(name or "", kind or "UNKNOWN")
