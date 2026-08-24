"""Demo: wrap a LangChain agent in 4 lines and stream its trace to the viewer.

Run the agent:
    python instrument.py

In another terminal, run the viewer:
    streamlit run viewer.py
"""
from agent_monitor import monitor

with monitor(
    service_name="langchain-demo",
    auto_instrument=True,
    instrumentors=["langchain"],
    exporter="jsonl",      # <-- writes spans to ./latest_traces.jsonl
):
    # Imported INSIDE the monitor context so OpenInference monkey-patches
    # are in effect before the LangChain objects are constructed.
    from agent import main
    main()
