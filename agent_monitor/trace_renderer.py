"""
Trace tree builder and terminal renderer.

Builds a tree of spans from a flat list (as received from OTel SDK) and renders
it to the terminal with box-drawing characters, ANSI colors, timing info, and
key OpenInference-style attributes.
"""
from __future__ import annotations

import io
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, TextIO

from opentelemetry.sdk.trace import ReadableSpan

# ---------------------------------------------------------------------------
# OpenInference / GenAI semantic convention attribute keys we surface
# ---------------------------------------------------------------------------
OI_SPAN_KIND = "openinference.span.kind"
INPUT_VALUE = "input.value"
OUTPUT_VALUE = "output.value"
INPUT_MIME_TYPE = "input.mime_type"
OUTPUT_MIME_TYPE = "output.mime_type"
LLM_MODEL_NAME = "llm.model_name"
LLM_TOKEN_COUNT_PROMPT = "llm.token_count.prompt"
LLM_TOKEN_COUNT_COMPLETION = "llm.token_count.completion"
LLM_TOKEN_COUNT_TOTAL = "llm.token_count.total"
LLM_INVOCATION_PARAMETERS = "llm.invocation_parameters"
TOOL_NAME = "tool.name"
TOOL_DESCRIPTION = "tool.description"
EXCEPTION_MESSAGE = "exception.message"


@dataclass
class SpanNode:
    name: str
    span_id: str
    parent_id: str | None
    span_kind: str
    start_time: datetime
    end_time: datetime
    status: str
    status_message: str
    attributes: dict[str, Any]
    children: list[SpanNode] = field(default_factory=list)


@dataclass
class TraceTree:
    root: SpanNode
    trace_id: str


# ---------------------------------------------------------------------------
# Colors
# ---------------------------------------------------------------------------
_KIND_COLORS: dict[str, str] = {
    "LLM": "\033[36m",
    "TOOL": "\033[33m",
    "CHAIN": "\033[35m",
    "AGENT": "\033[34m",
    "RETRIEVER": "\033[32m",
    "EMBEDDING": "\033[90m",
    "RERANKER": "\033[95m",
    "EVALUATOR": "\033[96m",
    "GUARDRAIL": "\033[91m",
    "PROMPT": "\033[93m",
    "UNKNOWN": "\033[37m",
}
_RESET = "\033[0m"
_BOLD = "\033[1m"
_DIM = "\033[2m"


def _ensure_utf8(file: TextIO) -> TextIO:
    """Reconfigure stdout to use UTF-8 on Windows."""
    try:
        enc = getattr(file, "encoding", "")
        if enc and enc.lower() not in ("utf-8", "utf8"):
            file.reconfigure(encoding="utf-8")
    except Exception:
        pass
    return file


def build_span_tree(spans: list[ReadableSpan]) -> TraceTree:
    nodes: dict[str, SpanNode] = {}
    for span in spans:
        ctx = span.get_span_context()
        sid = f"{ctx.span_id:016x}"
        parent_ctx = span.parent
        pid = f"{parent_ctx.span_id:016x}" if parent_ctx else None

        attrs = dict(span.attributes or {})
        kind = _normalize_kind(attrs.pop(OI_SPAN_KIND, _infer_kind(span)))
        status = _status_name(span)

        node = SpanNode(
            name=span.name,
            span_id=sid,
            parent_id=pid,
            span_kind=kind,
            start_time=_as_datetime(span.start_time),
            end_time=_as_datetime(span.end_time),
            status=status,
            status_message=_status_message(span),
            attributes=attrs,
        )
        nodes[sid] = node

    root: SpanNode | None = None
    for node in nodes.values():
        if node.parent_id and node.parent_id in nodes:
            nodes[node.parent_id].children.append(node)
        elif node.parent_id is None:
            root = node

    for node in nodes.values():
        node.children.sort(key=lambda c: c.start_time)

    trace_id = f"{spans[0].get_span_context().trace_id:032x}" if spans else "unknown"

    if root is None:
        root = min(nodes.values(), key=lambda n: n.start_time)

    return TraceTree(root=root, trace_id=trace_id)


def render_tree(tree: TraceTree, *, file: TextIO | None = None) -> None:
    buf = io.StringIO()
    t = _format_time(tree.root.start_time)
    dur = _latency_str(tree.root.start_time, tree.root.end_time)
    buf.write(f"\n{_BOLD}| Trace {tree.trace_id[:16]}...{_RESET}")
    buf.write(f"  {_DIM}{t}  ({dur}){_RESET}\n")
    _render_node(tree.root, buf, prefix="", is_last=True, is_root=True)
    if file:
        _ensure_utf8(file)
        file.write(buf.getvalue() + "\n")
        file.flush()
    else:
        try:
            print(buf.getvalue())
        except UnicodeEncodeError:
            plain = buf.getvalue().encode("ascii", errors="replace").decode("ascii")
            print(plain)


def _render_node(
    node: SpanNode,
    buf: io.StringIO,
    prefix: str = "",
    is_last: bool = True,
    is_root: bool = False,
) -> None:
    connector = "L-- " if is_last else "|-- "

    color = _KIND_COLORS.get(node.span_kind, _KIND_COLORS["UNKNOWN"])
    kind_badge = f"{color}[{node.span_kind}]{_RESET}"
    lat = _latency_str(node.start_time, node.end_time)

    if node.status == "ERROR":
        status_icon = "\033[91mX\033[0m "
    elif node.status == "OK":
        status_icon = "\033[32m>\033[0m "
    else:
        status_icon = "\033[37mo\033[0m "

    line = f"{prefix}{connector}{status_icon}{kind_badge} {_BOLD}{node.name}{_RESET}  {_DIM}{lat}{_RESET}"
    buf.write(line + "\n")

    child_prefix = prefix + ("    " if is_last else "|   ")

    _render_attributes(node, buf, child_prefix)

    if node.status == "ERROR" and node.status_message:
        msg_prefix = child_prefix + "    "
        buf.write(f"{msg_prefix}\033[91merror: {node.status_message[:200]}\033[0m\n")

    for i, child in enumerate(node.children):
        _render_node(child, buf, child_prefix, is_last=(i == len(node.children) - 1))


def _render_attributes(node: SpanNode, buf: io.StringIO, prefix: str) -> None:
    attrs = node.attributes

    input_val = attrs.get(INPUT_VALUE)
    output_val = attrs.get(OUTPUT_VALUE)

    if input_val is not None:
        _attr_line(buf, prefix, "input", _truncate_json(input_val, 100))
    if output_val is not None:
        _attr_line(buf, prefix, "output", _truncate_json(output_val, 100))

    if "llm.model_name" in attrs:
        _attr_line(buf, prefix, "model", str(attrs["llm.model_name"]))
    if "llm.provider" in attrs:
        _attr_line(buf, prefix, "provider", str(attrs["llm.provider"]))

    tokens: list[str] = []
    for key, label in [
        (LLM_TOKEN_COUNT_TOTAL, "tokens"),
        (LLM_TOKEN_COUNT_PROMPT, "prompt"),
        (LLM_TOKEN_COUNT_COMPLETION, "completion"),
    ]:
        if key in attrs:
            tokens.append(f"{label}={attrs[key]}")
    if tokens:
        _attr_line(buf, prefix, "", ", ".join(tokens))

    if TOOL_NAME in attrs:
        _attr_line(buf, prefix, "tool", str(attrs[TOOL_NAME]))


def _attr_line(buf: io.StringIO, prefix: str, label: str, value: str) -> None:
    if label:
        buf.write(f"{prefix}    {_DIM}{label}:{_RESET} {value}\n")
    else:
        buf.write(f"{prefix}    {_DIM}{value}{_RESET}\n")


def _span_id_hex(span: ReadableSpan) -> str:
    return f"{span.get_span_context().span_id:016x}"


def _as_datetime(ns: int | None) -> datetime:
    if ns is None:
        return datetime.now(timezone.utc)
    return datetime.fromtimestamp(ns / 1e9, tz=timezone.utc)


def _normalize_kind(raw: str) -> str:
    return raw.strip().upper() if raw else "UNKNOWN"


def _infer_kind(span: ReadableSpan) -> str:
    name_lower = span.name.lower()
    if "llm" in name_lower or "chat" in name_lower or "completion" in name_lower:
        return "LLM"
    if "tool" in name_lower or "function" in name_lower:
        return "TOOL"
    if "retriev" in name_lower or "search" in name_lower or "embedding" in name_lower:
        return "RETRIEVER"
    if "agent" in name_lower:
        return "AGENT"
    if "chain" in name_lower:
        return "CHAIN"
    return "UNKNOWN"


def _status_name(span: ReadableSpan) -> str:
    sc = span.status.status_code
    if sc.name == "ERROR":
        return "ERROR"
    if sc.name == "OK":
        return "OK"
    return "UNSET"


def _status_message(span: ReadableSpan) -> str:
    return span.status.description or ""


def _latency_str(start: datetime, end: datetime) -> str:
    ms = max(0, (end - start).total_seconds() * 1000)
    if ms < 1:
        return f"{ms * 1000:.0f}us"
    if ms < 1000:
        return f"{ms:.1f}ms"
    return f"{ms / 1000:.2f}s"


def _format_time(dt: datetime) -> str:
    return dt.strftime("%H:%M:%S")


def _truncate_json(val: Any, max_len: int = 100) -> str:
    if isinstance(val, str):
        s = val
    elif isinstance(val, (dict, list)):
        s = json.dumps(val, ensure_ascii=False)
    else:
        s = str(val)
    if len(s) > max_len:
        return s[: max_len - 3] + "..."
    return s
