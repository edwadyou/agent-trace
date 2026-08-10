"""PDF contract review agent built with LangChain and auto-instrumentation.

Run::

    python langchain_pdf_contract_agent.py path/to/contract.pdf

Set these environment variables before running::

    OPENAI_API_KEY=sk-...
    OPENAI_BASE_URL=https://api.deepseek.com   # optional
    LLM_MODEL=deepseek-chat                    # optional

The LangChain chain is invoked inside ``monitor(auto_instrument=True)``, so
OpenInference automatically records LangChain and LLM spans as terminal trace
trees.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from agent_monitor import monitor
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


class LangChainContractReviewAgent:
    """Review a PDF by invoking a LangChain prompt -> LLM -> parser chain."""

    def __init__(
        self,
        llm: ChatOpenAI,
        *,
        chunk_size: int = 8_000,
        max_chars: int = 120_000,
    ) -> None:
        self._llm = llm
        self._chunk_size = chunk_size
        self._max_chars = max_chars
        self._model = getattr(llm, "model_name", "unknown")
        self._chain = self._build_chain(llm)

    def review_pdf(self, pdf_path: str) -> ReviewResult:
        document = extract_pdf(pdf_path, max_chars=self._max_chars)
        chunks = chunk_text(document.text, max_chars=self._chunk_size)
        if not chunks:
            raise ValueError("Contract text is empty after PDF extraction.")

        reviews: list[ReviewResult] = []
        for index, chunk in enumerate(chunks, start=1):
            label = f"part {index} of {len(chunks)}"
            raw = self._chain.invoke(
                {
                    "contract_text": build_review_prompt(
                        chunk,
                        chunk_label=label,
                    )
                }
            )
            review = review_from_data(
                parse_review_json(raw),
                source_path=document.path,
                page_count=document.page_count,
                model=self._model,
            )
            reviews.append(review)

        return merge_review_results(reviews)

    def _build_chain(self, llm: ChatOpenAI) -> Any:
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", REVIEW_SYSTEM_PROMPT),
                ("human", "{contract_text}"),
            ]
        )
        return prompt | llm | StrOutputParser()


def build_llm(api_key: str, base_url: str | None, model: str) -> ChatOpenAI:
    kwargs: dict[str, Any] = {
        "model": model,
        "api_key": api_key,
        "temperature": 0.1,
        "max_tokens": 8_000,
        "timeout": 90,
        "max_retries": 2,
    }
    if base_url:
        kwargs["base_url"] = base_url
    return ChatOpenAI(**kwargs)


def _print_extract_only(document: PdfDocument) -> None:
    print(f"PDF: {document.path}")
    print(f"Pages: {document.page_count}")
    print(f"Characters: {len(document.text)}")
    print("---")
    print(document.text[:4_000])


def main() -> None:
    parser = argparse.ArgumentParser(
        description="LangChain PDF contract review agent with auto-instrumentation."
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

    with monitor(
        service_name="langchain-pdf-contract-reviewer",
        auto_instrument=True,
        instrumentors=["langchain"],
        verbose=True,
    ):
        if args.extract_only:
            document = extract_pdf(args.pdf_path, max_chars=args.max_chars)
            _print_extract_only(document)
            return

        api_key = require_api_key()
        llm = build_llm(api_key=api_key, base_url=base_url, model=model)
        agent = LangChainContractReviewAgent(
            llm,
            chunk_size=args.chunk_size,
            max_chars=args.max_chars,
        )
        result = agent.review_pdf(args.pdf_path)

    print(format_review(result))
    if args.output:
        Path(args.output).write_text(
            json.dumps(result.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
