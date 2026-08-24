"""LangChain agent under test.

Uses ``FakeListLLM`` so the demo runs without an OPENAI_API_KEY.
OpenInference-instrumentation-langchain still emits ``[CHAIN]`` and ``[LLM]``
spans because it hooks into LangChain itself, not into a specific provider.
"""
from __future__ import annotations
import time

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableLambda

try:
    from langchain_community.llms.fake import FakeListLLM
except ImportError:  # pragma: no cover
    raise SystemExit(
        "Please `pip install langchain-community` to run this demo."
    )

# Fake LLM responses (cycled if more claims than responses).
FAKE_RESPONSES = [
    '{"verdict": "TRUE", "confidence": 0.85, "rationale": "Multiple credible sources confirm."}',
    '{"verdict": "UNCERTAIN", "confidence": 0.55, "rationale": "Sources conflict on the acquisition price."}',
    '{"verdict": "FALSE", "confidence": 0.93, "rationale": "No public announcement matches this claim."}',
    '{"verdict": "TRUE", "confidence": 0.78, "rationale": "Press release corroborates the date."}',
]

CLAIMS = [
    "Acme Corp announced on 2026-08-05 that it will acquire Beta Inc for $5B in an all-stock deal.",
    "Tesla will release a $25K Model 2 in 2027.",
    "Apple unveiled the Vision Pro 2 at WWDC 2026.",
]


def _retrieve(payload: dict) -> dict:
    """Pretend to retrieve evidence for a claim. Sleeps so trace timings look real."""
    claim = payload.get("input", "")
    time.sleep(0.15)
    return {
        "claim": claim,
        "evidence": (
            f"Evidence for: {claim[:40]}... "
            "-- snippet 1: 'company sources indicate the deal is in progress.' "
            "-- snippet 2: 'regulatory filings reference a $5B all-stock structure.'"
        ),
    }


def main() -> None:
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a news claim verifier. Respond as JSON with "
                   "{verdict, confidence, rationale}."),
        ("user", "Claim: {claim}\n\nEvidence: {evidence}"),
    ])
    llm = FakeListLLM(responses=FAKE_RESPONSES)
    parser = StrOutputParser()

    # LCEL chain: input -> retrieve -> prompt -> llm -> string
    chain = RunnableLambda(_retrieve) | prompt | llm | parser

    for claim in CLAIMS:
        result = chain.invoke({"input": claim})
        print(f"\nClaim  : {claim[:70]}{'...' if len(claim) > 70 else ''}")
        print(f"Verdict: {result}")
        time.sleep(0.3)  # spacing so the viewer sees traces come in one by one


if __name__ == "__main__":
    main()
