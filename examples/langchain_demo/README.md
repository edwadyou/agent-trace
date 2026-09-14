# langchain_demo

Minimal demo of the SDK's "add a few lines to your entry point" workflow with a
real LangChain chain. No API key required -- uses ``FakeListLLM``.

## Run

In one terminal:

```bash
pip install -e ../..                # install agent-monitor SDK
pip install langchain-core langchain-community
python instrument.py                # runs the agent, writes latest_traces.jsonl
```

In a second terminal:

```bash
pip install streamlit streamlit-autorefresh
streamlit run ../../viewer.py
```

Open http://localhost:8501 in your browser. You will see:

- A sidebar showing the watched file path + last-modified time
- One row per run in the trace list, labelled with the root span name
  (``claim_verification``), refreshing every 3s
- The selected trace's span tree on the right, with ``[CHAIN]`` /
  ``[LLM]`` spans auto-emitted by OpenInference-instrumentation-langchain

## What it proves

- The user only wrote `agent.py` (LangChain business logic) and
  `instrument.py` (`monitor()` + one root span + the entry-point import).
- ``main()`` invokes the chain 3 times; the root span makes all 3 land in a
  single trace, so the dropdown shows one business-labelled row instead of
  three.
- All monitoring spans were produced automatically by the SDK -- zero
  manual `@span` decorators in business code.
