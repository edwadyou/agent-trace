# Local Agent Monitor

Standalone local Agent monitoring -- prints OpenTelemetry trace trees to the terminal. Extracted from the Phoenix AI observability platform's tracing infrastructure. No database, no web UI, no cloud.

## Architecture

```
Phoenix original:
  OTel SDK -> OTLP Exporter -> Phoenix Collector -> DB -> Web UI

This tool:
  OTel SDK -> ConsoleSpanExporter -> traces/trace-<timestamp>-<id>.json
```

The core extracted from Phoenix is the **OpenTelemetry + OpenInference auto-instrumentation layer**. OpenInference instrumentors (for OpenAI, LangChain, etc.) produce spans with semantic convention attributes (`input.value`, `output.value`, `llm.token_count.*`, etc.). Instead of shipping those spans to a remote collector, the custom `ConsoleSpanExporter` writes each completed trace as a JSON file under the `traces/` directory.

## Files

| File | Purpose |
|---|---|
| `agent_monitor/monitor.py` | Context manager that sets up OTel TracerProvider + console exporter. Supports `auto_instrument=True` to activate OpenInference instrumentors. |
| `agent_monitor/console_exporter.py` | Custom `SpanExporter` -- buffers spans per trace and writes each completed trace to `traces/trace-<timestamp>-<id>.json`. |
| `agent_monitor/trace_renderer.py` | Builds span tree from flat list, renders with ANSI colors, timing, attributes. |
| `pdf_contract_utils.py` | Shared PDF extraction, chunking, prompt and result helpers for the PDF review agents. |
| `langchain_pdf_contract_agent.py` | LangChain PDF contract review agent with OpenInference auto-instrumentation. |
| `pure_pdf_contract_agent.py` | Pure handwritten PDF contract review agent with `@span` decorator monitoring. |

## Monitor Your Own Agent

### 1. Install dependencies

```bash
cd local-agent-monitor
pip install -e ".[instrument]"
pip install openai openinference-instrumentation-openai
```

### 2. Set API key

The `agent_monitor` package auto-loads `.env` from the project root, so all
agent examples can use it without terminal exports:

```env
OPENAI_API_KEY=sk-...
# Optional: leave blank for OpenAI's default endpoint.
OPENAI_BASE_URL=
# Optional: defaults to gpt-4o-mini.
LLM_MODEL=gpt-4o-mini
```

You can still export variables in the terminal; existing environment variables
take precedence over `.env`.

If no API key is found, the example agents exit before making an LLM call.

`.env` is ignored by git, so it will not be uploaded to GitHub. If you share
the project, copy `.env.example` to `.env` and fill in your own key. Never put
a real API key into a committed file.

```bash
export OPENAI_API_KEY=sk-...
# or PowerShell: $env:OPENAI_API_KEY="sk-..."
```

### 3. Integrate into your own Agent

```python
from agent_monitor import monitor
from openai import OpenAI

client = OpenAI()

with monitor(service_name="my-agent", auto_instrument=True):
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Hello"}],
    )
```

Every OpenAI API call inside the `with monitor(...)` block produces a span in the terminal trace tree. If you add manual spans with `openinference.span.kind` attributes, they appear with colored kind badges in the tree.

## PDF Contract Review Agents

Two PDF contract review agents are included. They both accept a PDF path and
return a structured review with a summary, risks, key clauses, and
recommendations.

The provided `.venv` already has the required packages. For a fresh
environment, install them directly:

```bash
pip install pypdf langchain-openai openinference-instrumentation-langchain
```

The pure handwritten agent needs the OpenAI SDK instead:

```bash
pip install pypdf openai
```

The project automatically loads `.env` from the project root, so you do not
need to set these variables in every terminal. Edit `.env` and replace the
placeholder with your API key:

```env
OPENAI_API_KEY=sk-...
# Optional: leave blank for OpenAI's default endpoint.
OPENAI_BASE_URL=
# Optional: defaults to gpt-4o-mini.
LLM_MODEL=gpt-4o-mini
```

Run the LangChain version:

```bash
python langchain_pdf_contract_agent.py path/to/contract.pdf
```

Run the pure handwritten version:

```bash
python pure_pdf_contract_agent.py path/to/contract.pdf
```

Both scripts support `--extract-only` to check PDF text extraction without an
API key, and `--output review.json` to save the review as JSON.

The LangChain version uses `monitor(auto_instrument=True,
instrumentors=["langchain"])`, so the terminal trace tree automatically
includes `[CHAIN]`, `[PROMPT]`, and `[LLM]` spans. The pure version uses
`@span` decorators around PDF extraction, LLM review, and result merge, so the
tree shows `[AGENT]`, `[RETRIEVER]`, and `[LLM]` spans.

## Choosing a Monitoring Approach

| Approach | When to use |
|---|---|
| `monitor(auto_instrument=True)` | Your agent uses OpenAI / LangChain / LlamaIndex SDKs. Spans are created automatically. |
| `monitor()` + manual spans | You write spans manually with `tracer.start_as_current_span()`. Good for custom agent frameworks. |
| `ConsoleSpanExporter` directly | You already have your own OTel setup and just want the trace dumped to JSON. |

## Supported OpenInference Instrumentors

Any package that registers an `openinference_instrumentor` entry point works:

- `openinference-instrumentation-openai`
- `openinference-instrumentation-langchain`
- `openinference-instrumentation-llama-index`
- `openinference-instrumentation-dspy`
- `openinference-instrumentation-crewai`
- etc.

Run `monitor(auto_instrument=True, verbose=True)` to see which instrumentors are detected and activated.
