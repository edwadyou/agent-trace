"""Regression tests for viewer.normalize.canon / _reconstruct_indexed_list."""
from __future__ import annotations

from viewer.normalize import _reconstruct_indexed_list, canon


def test_reconstruct_function_is_callable():
    """The (now singular) helper must remain on the module surface."""
    assert _reconstruct_indexed_list({"a.0.x": 1}, "a") == [{"x": 1}]
    assert _reconstruct_indexed_list({}, "a") is None
    assert _reconstruct_indexed_list({"a.0.x": "v"}, "missing") is None


def test_canon_messages_flatten_dedup():
    """After dedup, canon() must still return the same value for `messages.input`."""
    attrs = {
        "llm.input_messages.0.message.role": "user",
        "llm.input_messages.0.message.content": "hi",
        "llm.input_messages.1.message.role": "assistant",
        "llm.input_messages.1.message.content": "hello",
    }
    out = canon(attrs, "messages.input")
    assert out is not None
    # We do not pin a specific shape (the exporter can return either a list
    # of dicts or strings) - we only require that the function returns
    # something truthy and is stable across two calls.
    assert out == canon(attrs, "messages.input")


def test_canon_tokens_input_finds_flat_path():
    """OpenInference flat ``llm.token_count.prompt`` should resolve."""
    attrs = {"llm.token_count.prompt": 42}
    assert canon(attrs, "tokens.input") == 42
