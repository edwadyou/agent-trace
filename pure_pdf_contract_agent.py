"""Pure handwritten PDF contract review agent with @span monitoring.

Run::

    python pure_pdf_contract_agent.py path/to/contract.pdf

Set these environment variables before running::

    OPENAI_API_KEY=sk-...
    OPENAI_BASE_URL=https://api.deepseek.com   # optional
    LLM_MODEL=deepseek-chat                    # optional

This agent does not use LangChain. It calls the OpenAI-compatible chat API
directly and wraps each workflow step with the project's ``@span`` decorator,
so the terminal trace tree shows extraction, LLM review, and merge spans.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from openai import OpenAI
from opentelemetry import trace as otel_trace

from agent_monitor import monitor, span
from pdf_contract_utils import (
    REVIEW_SYSTEM_PROMPT,
    PdfDocument,
    ReviewResult,
    build_review_prompt,
    chunk_text,
    extract_pdf,
    format_review,
    merge_review_results,
    parse_review_json,
    require_api_key,
    resolve_llm_settings,
    review_from_data,
)


@span(
    "contract.extract_pdf",
    kind="RETRIEVER",
    capture_input=False,
    capture_output=False,
)
def extract_contract(
    pdf_path: str,
    *,
    max_chars: int = 120_000,
) -> PdfDocument:
    document = extract_pdf(pdf_path, max_chars=max_chars)
    current_span = otel_trace.get_current_span()
    current_span.set_attribute("pdf.path", document.path)
    current_span.set_attribute("pdf.pages", document.page_count)
    current_span.set_attribute("pdf.chars", len(document.text))
    return document


@span("llm.review_chunk", kind="LLM", capture_input=False)
def review_chunk(
    client: OpenAI,
    model: str,
    contract_chunk: str,
    chunk_index: int,
    chunk_count: int,
) -> dict[str, Any]:
    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": REVIEW_SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": build_review_prompt(
                    contract_chunk,
                    chunk_label=f"part {chunk_index} of {chunk_count}",
                ),
            },
        ],
        temperature=0.1,
        max_tokens=8_000,
    )
    raw = response.choices[0].message.content or "{}"

    current_span = otel_trace.get_current_span()
    current_span.set_attribute("contract.chunk_index", chunk_index)
    current_span.set_attribute("contract.chunk_count", chunk_count)
    current_span.set_attribute("llm.model_name", model)
    return parse_review_json(raw)


@span("contract.merge_reviews", kind="AGENT", capture_input=False, capture_output=False)
def merge_contract_reviews(reviews: list[ReviewResult]) -> ReviewResult:
    result = merge_review_results(reviews)
    current_span = otel_trace.get_current_span()
    current_span.set_attribute("contract.risk_count", len(result.risks))
    current_span.set_attribute("contract.clause_count", len(result.key_clauses))
    current_span.set_attribute("contract.recommendation_count", len(result.recommendations))
    return result


@span("contract.review", kind="AGENT", capture_input=False, capture_output=False)
def review_pdf_contract(
    pdf_path: str,
    client: OpenAI,
    model: str,
    *,
    max_chars: int = 120_000,
    chunk_size: int = 8_000,
) -> ReviewResult:
    document = extract_contract(pdf_path, max_chars=max_chars)
    chunks = chunk_text(document.text, max_chars=chunk_size)
    if not chunks:
        raise ValueError("Contract text is empty after PDF extraction.")

    reviews: list[ReviewResult] = []
    for index, chunk in enumerate(chunks, start=1):
        data = review_chunk(
            client,
            model,
            chunk,
            index,
            len(chunks),
        )
        reviews.append(
            review_from_data(
                data,
                source_path=document.path,
                page_count=document.page_count,
                model=model,
            )
        )

    result = merge_contract_reviews(reviews)
    current_span = otel_trace.get_current_span()
    current_span.set_attribute("pdf.path", document.path)
    current_span.set_attribute("pdf.pages", document.page_count)
    current_span.set_attribute("contract.chunk_count", len(chunks))
    current_span.set_attribute("contract.risk_count", len(result.risks))
    current_span.set_attribute("contract.clause_count", len(result.key_clauses))
    current_span.set_attribute("contract.recommendation_count", len(result.recommendations))
    return result


def _print_extract_only(document: PdfDocument) -> None:
    print(f"PDF: {document.path}")
    print(f"Pages: {document.page_count}")
    print(f"Characters: {len(document.text)}")
    print("---")
    print(document.text[:4_000])


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Pure handwritten PDF contract review agent with @span monitoring."
    )
    parser.add_argument("pdf_path", help="Path to the PDF contract to review.")
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=8_000,
        help="Maximum characters sent to the LLM in one chunk.",
    )
    parser.add_argument(
        "--max-chars",
        type=int,
        default=120_000,
        help="Maximum PDF text characters to extract.",
    )
    parser.add_argument(
        "--extract-only",
        action="store_true",
        help="Extract and print PDF text without calling the LLM.",
    )
    parser.add_argument(
        "--output",
        help="Optional JSON file path for the review result.",
    )
    args = parser.parse_args()

    sys.stdout.reconfigure(encoding="utf-8")
    _, base_url, model = resolve_llm_settings()
    api_key = ""
    if not args.extract_only:
        api_key = require_api_key()

    with monitor(service_name="pure-pdf-contract-reviewer"):
        if args.extract_only:
            document = extract_contract(args.pdf_path, max_chars=args.max_chars)
            _print_extract_only(document)
            return

        client = OpenAI(api_key=api_key, base_url=base_url)
        result = review_pdf_contract(
            args.pdf_path,
            client,
            model,
            max_chars=args.max_chars,
            chunk_size=args.chunk_size,
        )

    print(format_review(result))
    if args.output:
        Path(args.output).write_text(
            json.dumps(result.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
