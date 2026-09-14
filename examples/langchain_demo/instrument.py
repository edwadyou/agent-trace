"""Demo: wrap a LangChain agent in one traced run and stream it to the viewer.

Run the agent:
    python instrument.py

In another terminal, run the viewer:
    streamlit run ../../viewer.py
"""
from opentelemetry.trace import Status, StatusCode

from agent_monitor import monitor

SERVICE_NAME = "langchain-demo"
ROOT_SPAN = "claim_verification"

with monitor(
    service_name=SERVICE_NAME,
    auto_instrument=True,
    instrumentors=["langchain"],
    exporter="jsonl",      # <-- writes spans to ./latest_traces.jsonl
) as tracer:
    # Imported INSIDE the monitor context so the OpenInference monkey-patches
    # are in effect before the LangChain objects are constructed, and OUTSIDE
    # the root span so import time is not counted as agent runtime.
    from agent import main

    # One root span for the whole run. main() invokes the chain 3 times; without
    # this they would become 3 separate traces (one per invoke), which is what
    # the viewer's trace dropdown would then list.
    with tracer.start_as_current_span(
        ROOT_SPAN,
        attributes={"openinference.span.kind": "AGENT"},
    ) as root:
        main()
        root.set_status(Status(StatusCode.OK))
