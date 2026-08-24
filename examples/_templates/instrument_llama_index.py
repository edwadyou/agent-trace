"""instrument_llama_index.py

Use when your agent is built with LlamaIndex. The LlamaIndex instrumentor captures query engine, retriever and LLM spans.

Quick start::

    pip install "agent-monitor[llama-index]"
    cp instrument_llama_index.py instrument.py
    # edit the 3 knobs below
    python instrument.py
"""
from pathlib import Path


def _load_dotenv(path: Path) -> None:
    import os
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ[k.strip()] = v.strip().strip(chr(34)).strip(chr(39))


_load_dotenv(Path(__file__).parent / ".env")

from agent_monitor import monitor  # noqa: E402

# Adjust to match your agent module entry function.
# from my_agent import run


# ============== 3 KNOBS YOU EDIT ==============
SERVICE_NAME  = 'my-llamaindex-agent'            # (1) trace identifier
INSTRUMENTORS = ['llama-index']            # (2) frameworks
# (3) Replace the body below with a call to YOUR agent entry function.
# ===============================================

with monitor(
    service_name=SERVICE_NAME,
    auto_instrument=True,
    instrumentors=INSTRUMENTORS,
    exporter="jsonl",        # writes ./latest_traces.jsonl
):
    # >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
    # >>> Replace this with your agent call. <<<
    # >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
    # run("your input")
    print("[" + SERVICE_NAME + "] edit this file to call your agent entry function.")
