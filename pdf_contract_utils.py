"""Shared PDF and contract-review helpers for the two agent examples.

The LangChain agent and the pure-handwritten agent intentionally keep their
agent logic separate. This module only contains PDF extraction, text chunking,
prompt construction, and result parsing/formatting that both can reuse.
"""
from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable


@dataclass
class PdfDocument:
    path: str
    page_count: int
    text: str


@dataclass
class ReviewResult:
    summary: str
    risks: list[str]
    key_clauses: list[str]
    recommendations: list[str]
    source_path: str = ""
    page_count: int = 0
    model: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


REVIEW_SYSTEM_PROMPT = (
    "You are a senior commercial contract reviewer. Analyze the supplied "
    "contract text for risk, missing protections, ambiguous language, and "
    "actionable improvements.\n\n"
    "Return only a JSON object with exactly these keys:\n"
    '- "summary": a short paragraph describing the contract.\n'
    '- "risks": an array of specific risk strings.\n'
    '- "key_clauses": an array of important clause summaries.\n'
    '- "recommendations": an array of concrete negotiation or drafting suggestions.\n\n'
    "Do not include markdown fences, explanations, or text outside the JSON object."
)


def extract_pdf(
    pdf_path: str | os.PathLike[str],
    *,
    max_chars: int = 120_000,
    max_pages: int | None = None,
) -> PdfDocument:
    """Extract readable text from a PDF, with a hard cap on returned text."""
    from pypdf import PdfReader

    path = Path(pdf_path)
    if not path.is_file():
        raise FileNotFoundError(f"PDF file not found: {path}")

    reader = PdfReader(str(path))
    parts: list[str] = []
    total = 0

    for page_number, page in enumerate(reader.pages, start=1):
        if max_pages is not None and page_number > max_pages:
            break
        if total >= max_chars:
            break

        page_text = _clean_text(page.extract_text() or "")
        if not page_text:
            continue

        block = f"--- Page {page_number} ---\n{page_text}"
        remaining = max_chars - total
        block = block[:remaining]
        parts.append(block)
        total += len(block)

    text = "\n\n".join(parts).strip()
    if not text:
        raise ValueError(
            "No extractable text found. The PDF may be scanned or image-based."
        )

    return PdfDocument(
        path=str(path.resolve()),
        page_count=len(reader.pages),
        text=text,
    )


def chunk_text(
    text: str,
    *,
    max_chars: int = 8_000,
    overlap: int = 400,
) -> list[str]:
    """Split long contracts into overlapping chunks at paragraph boundaries."""
    normalized = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not normalized:
        return []
    if len(normalized) <= max_chars:
        return [normalized]

    chunks: list[str] = []
    start = 0
    while start < len(normalized):
        if len(normalized) - start <= max_chars:
            chunks.append(normalized[start:].strip())
            break

        end = start + max_chars
        boundary = normalized.rfind(
            "\n\n",
            start + int(max_chars * 0.6),
            end,
        )
        if boundary > start:
            end = boundary

        chunks.append(normalized[start:end].strip())
        next_start = max(end - overlap, start + 1)
        if next_start <= start:
            break
        start = next_start

    return [chunk for chunk in chunks if chunk]


def build_review_prompt(
    contract_text: str,
    *,
    chunk_label: str | None = None,
) -> str:
    """Build the user prompt for one contract chunk."""
    label = ""
    if chunk_label:
        label = f"\n\nThis is {chunk_label} of the contract."
    return (
        "Review the following contract text and return the JSON review object. "
        f"Quote exact clause language where relevant.{label}\n\n"
        "CONTRACT TEXT:\n"
        f"{contract_text}"
    )


def parse_review_json(raw: str) -> dict[str, Any]:
    """Parse an LLM JSON response even when markdown fences are present."""
    text = re.sub(r"<think>.*?</think>\s*", "", raw, flags=re.DOTALL).strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)

    try:
        return _first_json_object(text)
    except json.JSONDecodeError:
        pass

    repaired = _repair_truncated_json(text)
    if repaired is not None:
        return repaired

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    raise ValueError(f"LLM response was not valid JSON: {raw[:300]}") from None


def _first_json_object(text: str) -> dict[str, Any]:
    """Return the first complete JSON object in the text, ignoring extra prose."""
    decoder = json.JSONDecoder()
    start = text.find("{")
    while start != -1:
        try:
            value, _ = decoder.raw_decode(text[start:])
            if isinstance(value, dict):
                return value
        except json.JSONDecodeError:
            pass
        start = text.find("{", start + 1)
    raise json.JSONDecodeError("No JSON object found", text, 0)


def _repair_truncated_json(text: str) -> dict[str, Any] | None:
    """Try to close a JSON object that was cut off before the final brace."""
    cleaned = text.rstrip().rstrip(",").rstrip()
    if not cleaned.startswith("{"):
        return None

    repaired = _close_open_json(cleaned)
    try:
        value = json.loads(repaired)
        return value if isinstance(value, dict) else None
    except json.JSONDecodeError:
        return None


def _close_open_json(text: str) -> str:
    """Append missing quotes and closing brackets to truncated JSON text."""
    stack: list[str] = []
    in_string = False
    escaped = False

    for char in text:
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char in "{[":
            stack.append(char)
        elif char in "}]":
            if stack:
                last = stack[-1]
                if (char == "}" and last == "{") or (char == "]" and last == "["):
                    stack.pop()

    suffix = '"' if in_string else ""
    suffix += "".join("}" if char == "{" else "]" for char in reversed(stack))
    return text.rstrip().rstrip(",") + suffix


def review_from_data(
    data: dict[str, Any],
    *,
    source_path: str = "",
    page_count: int = 0,
    model: str = "",
) -> ReviewResult:
    """Normalize an LLM review dict into a ReviewResult."""
    if not isinstance(data, dict):
        raise ValueError("Review result must be a JSON object.")

    def string_list(key: str) -> list[str]:
        value = data.get(key, [])
        if isinstance(value, str):
            return [item.strip() for item in value.splitlines() if item.strip()]
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return []

    return ReviewResult(
        summary=str(data.get("summary", "") or "").strip(),
        risks=string_list("risks"),
        key_clauses=string_list("key_clauses"),
        recommendations=string_list("recommendations"),
        source_path=source_path,
        page_count=page_count,
        model=model,
    )


def merge_review_results(reviews: Iterable[ReviewResult]) -> ReviewResult:
    """Merge chunk-level reviews, preserving order and removing duplicates."""
    items = [review for review in reviews if review is not None]
    if not items:
        return ReviewResult(
            summary="No review content was produced.",
            risks=[],
            key_clauses=[],
            recommendations=[],
        )

    def unique(values: Iterable[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for value in values:
            normalized = value.strip()
            key = normalized.casefold()
            if normalized and key not in seen:
                seen.add(key)
                result.append(normalized)
        return result

    first = items[0]
    summaries = [item.summary for item in items if item.summary]
    summary = "\n".join(summaries) if len(summaries) > 1 else (summaries[0] if summaries else "")

    return ReviewResult(
        summary=summary,
        risks=unique(risk for item in items for risk in item.risks),
        key_clauses=unique(clause for item in items for clause in item.key_clauses),
        recommendations=unique(rec for item in items for rec in item.recommendations),
        source_path=first.source_path,
        page_count=first.page_count,
        model=first.model,
    )


def format_review(review: ReviewResult) -> str:
    """Render a ReviewResult as readable terminal output."""
    lines = [
        "=" * 64,
        "PDF Contract Review",
        "=" * 64,
        f"Source : {review.source_path}",
        f"Pages  : {review.page_count}",
        f"Model  : {review.model or 'unknown'}",
        "",
        "SUMMARY",
        review.summary or "(no summary)",
        "",
        "RISKS",
    ]
    if review.risks:
        lines.extend(f"- {risk}" for risk in review.risks)
    else:
        lines.append("(none)")
    lines.extend(["", "KEY CLAUSES"])
    if review.key_clauses:
        lines.extend(f"- {clause}" for clause in review.key_clauses)
    else:
        lines.append("(none)")
    lines.extend(["", "RECOMMENDATIONS"])
    if review.recommendations:
        lines.extend(f"- {rec}" for rec in review.recommendations)
    else:
        lines.append("(none)")
    return "\n".join(lines)


def resolve_llm_settings() -> tuple[str, str | None, str]:
    """Return api_key, base_url, model from environment variables."""
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    base_url = os.getenv("OPENAI_BASE_URL") or None
    model = os.getenv("LLM_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"
    return api_key, base_url, model


def require_api_key() -> str:
    api_key, _, _ = resolve_llm_settings()
    if not api_key or api_key == "sk-...":
        sys.exit(1)
    return api_key


def _clean_text(text: str) -> str:
    return re.sub(r"[ \t]+\n", "\n", text).strip()
