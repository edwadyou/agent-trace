"""Regression tests for the langchain naming rules post-fireworks-dedup."""
from __future__ import annotations
import re

from viewer.naming.langchain import LANGCHAIN_RULES, _parallel_label


def test_each_chat_provider_matches():
    for name, kind in [
        ("ChatOpenAI.invoke", "OpenAI"),
        ("ChatAnthropic", "Anthropic"),
        ("ChatGoogleGenerativeAI", "Google"),
        ("ChatBedrock", "Bedrock"),
        ("ChatGroq", "Groq"),
        ("ChatMistral", "Mistral"),
        ("ChatFireworks", "Fireworks"),
    ]:
        matched = False
        for rule in LANGCHAIN_RULES:
            m = rule.pattern.match(name)
            if not m:
                continue
            if rule.require_kind and rule.require_kind != "LLM":
                continue
            if rule.computed is not None:
                label, _ = rule.computed(name, m, "LLM")
                assert kind in label, name + " -> " + repr(label)
                matched = True
                break
        assert matched, "no rule matched " + name


def test_fireworks_appears_once():
    n = 0
    for rule in LANGCHAIN_RULES:
        n += len(re.findall("Fireworks", rule.pattern.pattern))
    assert n == 1, "expected Fireworks to appear exactly once, found " + str(n)


def test_parallel_label_callable():
    m = re.match(r"^RunnableParallel(?P<inner>.*)$", "RunnableParallel<a,b>")
    label, vis = _parallel_label("RunnableParallel<a,b>", m, "CHAIN")
    assert isinstance(label, str)
    assert vis is True
    assert len(label) > 0
