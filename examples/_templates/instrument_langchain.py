"""instrument_langchain.py - self-contained LangChain LCEL demo.

This template runs WITHOUT any editing. It defines a tiny LCEL chain inline,
calls it once inside ``monitor()``, and writes a meaningful trace to
``./latest_traces.jsonl``. Replace the body of ``demo_chain()`` with your
real agent's entry call when ready.

Quick start::

    echo OPENAI_API_KEY=sk-... > .env
    python -m agent_monitor init --framework auto     # writes THIS file
    python instrument.py                              # writes latest_traces.jsonl
    streamlit run D:/my-projects/agent-monitor/viewer.py
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


# ============== 3 KNOBS YOU EDIT (optional) ==============
SERVICE_NAME  = 'my-langchain-agent'   # (1) trace identifier
INSTRUMENTORS = ['langchain']          # (2) frameworks
# (3) Replace demo_chain() below with a call to YOUR agent.
#     The demo runs a minimal LCEL chain so you can `python instrument.py`
#     without any editing and still get a real, multi-span trace.
# ========================================================


def demo_chain() -> None:
    """A self-contained LCEL chain. Runs out of the box - replace with yours."""
    from langchain_openai import ChatOpenAI
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.output_parsers import StrOutputParser

    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a helpful assistant. Be concise."),
        ("human",  "{question}"),
    ])
    llm    = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    parser = StrOutputParser()
    chain  = prompt | llm | parser

    answer = chain.invoke({"question": "In one sentence, what is the capital of France?"})
    print("[" + SERVICE_NAME + "]", answer)


with monitor(
    service_name=SERVICE_NAME,
    auto_instrument=True,
    instrumentors=INSTRUMENTORS,
    exporter="jsonl",        # writes ./latest_traces.jsonl
):
    demo_chain()
