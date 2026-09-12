# Local Agent Monitor

**English** | [简体中文](README.zh-CN.md)

Standalone local Agent monitoring -- trace execution without remote
dependencies. **All traces are stored locally**; no data is ever sent to a
remote collector.

Current version: **1.1.1** (JSONL schema version `1.1.0`).

```
Phoenix original:
  OTel SDK -> OTLP Exporter -> Phoenix Collector -> DB -> Web UI

This tool:
  OTel SDK -> JsonlFileExporter -> ./latest_traces.jsonl -> viewer
```

The core extracted from Phoenix is the **OpenTelemetry + OpenInference
auto-instrumentation layer**. OpenInference instrumentors (for OpenAI,
LangChain, etc.) produce spans with semantic convention attributes
(`input.value`, `output.value`, `llm.token_count.*`, etc.). Instead of
shipping those spans to a remote collector, the custom `JsonlFileExporter`
streams one JSON object per span to a local file.

## What is new in v1.1

- **Schema versioning**: every JSONL record now has `schema_version`.
  Consumers (viewer, render, verify) migrate older records automatically.
- **Auto-detection**: pass `auto_detect=True` to `monitor()` and the SDK
  will sniff which frameworks are importable + which instrumentors are
  installed, then activate exactly those.
- **Default exporter = JSONL**: `monitor()` without arguments now writes
  `latest_traces.jsonl`. Pass `exporter="console"` if you want the old
  nested JSON tree under `traces/` instead.
- **Templates**: one packaged `instrument.py` template works for any framework
  combination and renders an explicit `INSTRUMENTORS` list.
- **CLI scaffolder**: `python -m agent_monitor init` auto-detects every
  installed framework, installs their combined OpenInference extras, and writes
  a starter `instrument.py`.
- **Export verifier**: `python -m agent_monitor verify` checks that the
  JSONL file is well-formed and contains useful data.

### v1.1.1 maintenance

- The 3-column Streamlit viewer was split out of the single-file `viewer.py`
  into the `viewer_app/` package (field normalisation helpers stay in
  `viewer/`). `viewer.py` is now a thin launcher so
  `streamlit run viewer.py` keeps working unchanged.
- Fixed a crash in the viewer's KPI aggregation (`TraceKPI` had lost its
  `@dataclass` decorator during the split, so any trace containing an
  `AGENT` span raised `TypeError`).
- `agent_monitor run` now uses the script filename as `service.name` when
  `--service-name` is omitted, as documented.
- `pytest` is scoped to `tests/` so the environment-specific scratch scripts
  at the repo root are no longer collected.

## Files

| File | Purpose |
|---|---|
| `agent_monitor/monitor.py` | `monitor()` context manager with `auto_detect` + JSONL default |
| `agent_monitor/jsonl_exporter.py` | `JsonlFileExporter` (streaming) + `SCHEMA_VERSION` |
| `agent_monitor/console_exporter.py` | `ConsoleSpanExporter` (nested JSON, one file per trace) |
| `agent_monitor/trace_renderer.py` | Terminal tree renderer (ANSI) |
| `agent_monitor/_detect.py` | Framework + instrumentor auto-detection |
| `agent_monitor/_schema_migrations.py` | Schema version upgrade logic |
| `agent_monitor/_verify_export.py` | Validate a JSONL export |
| `agent_monitor/__main__.py` | CLI: `init`, `run`, `detect`, `verify`, `view` |
| `agent_monitor/templates/instrument.py` | Packaged multi-framework scaffold template |
| `viewer.py` | Entry-point launcher for the Streamlit viewer |
| `viewer_app/` | Streamlit viewer implementation (3-column layout) |
| `viewer/` | Framework-agnostic normalisation: span kind, field aliases, naming, visibility |
| `flowchart_component/` | Bidirectional Mermaid flowchart Streamlit component |
| `tests/` | pytest regression suite |
| `examples/langchain_demo/` | End-to-end LangChain example |

### Inside `viewer_app/`

| Module | Purpose |
|---|---|
| `__init__.py` | `run()` -- page assembly + 3-column layout |
| `config.py` | page config, CSS, constants, cost table, default trace paths |
| `state.py` | shared mutable state across reruns |
| `data.py` | `load_traces`, `TraceKPI`, `_aggregate_kpi`, source discovery |
| `format.py` | escaping, duration / token / timestamp formatting, cost estimate |
| `structured.py` | JSON-envelope detection + recursive structured renderer |
| `msg.py` | LLM message card renderer |
| `render_detail.py` | span detail column (Run / Feedback / Metadata tabs) |
| `render_flowchart.py` | Mermaid graph builder + component wrapper |
| `render_tracelist.py` | left-hand trace card list |

### Inside `viewer/`

| Module | Purpose |
|---|---|
| `canonical.py` | span-kind table + `FIELD_ALIASES` (canonical key -> attribute paths) |
| `normalize.py` | `canon()`, `span_kind()`, `to_messages()`, `friendly_name()` |
| `visibility.py` | plumbing-span / noise-attribute filtering |
| `naming/` | per-framework span-name translation rules |

## Monitor Your Own Agent

### 1. Install

```bash
# From this source checkout, use editable mode and combine extras:
pip install -e ".[langchain,openai]"

# From an installed/wheel-based environment:
# SDK core (just OTel + the monitor context manager)
pip install agent-monitor

# + the framework(s) you use
pip install "agent-monitor[langchain,openai]"     # most common combo
pip install "agent-monitor[llama-index]"          # LlamaIndex
pip install "agent-monitor[crewai]"               # CrewAI
pip install "agent-monitor[dspy]"                 # DSPy
pip install "agent-monitor[autogen]"              # Microsoft autogen
pip install "agent-monitor[haystack]"             # Haystack
pip install "agent-monitor[smolagents]"           # HuggingFace smolagents
pip install "agent-monitor[anthropic]"            # Claude
pip install "agent-monitor[google-genai]"         # Gemini
pip install "agent-monitor[groq]"                 # Groq
pip install "agent-monitor[bedrock]"              # AWS Bedrock
pip install "agent-monitor[litellm]"              # LiteLLM

# all of them at once
pip install "agent-monitor[all-instruments]"

# viewer + test tooling only
pip install -e ".[viewer,test]"
```

### 2. Scaffold `instrument.py`

Generate the starter and edit the body to call your agent:

```bash
python -m agent_monitor init --framework auto

# or request the exact framework set
python -m agent_monitor init --framework langchain,openai

# write the file but install nothing (CI / air-gapped)
python -m agent_monitor init --framework auto --no-install-deps
```

Edit `SERVICE_NAME` and replace the placeholder in the `with monitor(...)`
block with your real agent entry-point call. Keep an existing customized
`instrument.py`; do not overwrite it with the scaffold. Update its dependency
installation with the matching combined extras instead.

### 3. Run + view

```bash
# terminal A: agent
python instrument.py
# -> writes ./latest_traces.jsonl  (streaming, one line per span)

# terminal B: launch the Streamlit viewer against that file
python -m agent_monitor view
# or, pointing at the viewer directly:
streamlit run viewer.py
# -> opens http://localhost:8501, refreshes every 3 s
```

`python -m agent_monitor view` resolves the trace file relative to the current
directory and the viewer relative to the installed package, so it works from
any working directory. Use `--no-launch` to print the resolved command only.

The viewer looks for the trace file in this order:
`$TRACE_FILE` -> `./latest_traces.jsonl` -> the two fallback paths in
`viewer_app/config.py` (`_DEFAULT_TRACE_PATHS`).

### 4. Verify (optional, useful in CI)

```bash
python -m agent_monitor verify --trace-file latest_traces.jsonl \
                               --min-spans 10 \
                               --require-kind LLM
```

## auto_detect=True

If you do not want to hard-code `INSTRUMENTORS`, let the SDK figure it out:

```python
from agent_monitor import monitor
with monitor(service_name="my-agent", auto_instrument=True, auto_detect=True):
    # OpenInference instrumentors for every installed+importable framework
    # are activated automatically.
    ...
```

The detector uses:
- `importlib.util.find_spec(...)` to see which framework modules are present
- `importlib.metadata.entry_points(group="openinference_instrumentor")` to see
  which instrumentors are installed
- intersection of the two for `instrumentors`

Run `python -m agent_monitor detect` to see the diagnostic output.

## API quick reference

```python
from agent_monitor import (
    monitor,                 # context manager
    span,                    # @span decorator
    trace,                   # @trace decorator
    JsonlFileExporter,       # streaming local exporter
    ConsoleSpanExporter,     # nested-tree local exporter
    SCHEMA_VERSION,          # current JSONL schema version
    migrate,                 # upgrade an old record to SCHEMA_VERSION
    verify_export,           # validate a JSONL export
    detect_compatible,       # sniff usable instrumentors
)
```

`monitor(...)` parameters:

| name | type | default | what |
|---|---|---|---|
| `service_name` | str | "agent" | OTel resource.service.name |
| `auto_instrument` | bool | False | activate OpenInference instrumentors |
| `auto_detect` | bool | False | sniff which instrumentors to activate |
| `instrumentors` | list[str] | None | explicit whitelist of instrumentor names |
| `exporter` | str or SpanExporter | None | "jsonl", "console", or a SpanExporter instance |
| `trace_file` | str/Path | "latest_traces.jsonl" | output path when exporter is jsonl |
| `verbose` | bool | False | print which instrumentors were activated |

## Schema v1.1 record shape

```jsonc
{
  "schema_version": "1.1.0",
  "service_name":   "my-agent",
  "trace_id":       "0" * 32 hex,
  "span_id":        "0" * 16 hex,
  "parent_span_id": "0" * 16 hex or null,
  "name":           "ChatOpenAI",
  "start_time":     1723712345678901234,   // ns since epoch
  "end_time":       1723712345678901234,
  "duration_ms":    1000.0,
  "status":         "OK",
  "kind":           "LLM",
  "attributes": {
    "input.value":   "...",
    "output.value":  "...",
    "llm.model_name": "MiniMax-M3",       // flattened from output.value
    "llm.token_count.prompt": 273,
    "llm.token_count.completion": 253,
    "llm.token_count.total": 526,
    "openinference.span.kind": "LLM"
  },
  "events": []
}
```

Records produced before v1.1 (no `schema_version`, no `service_name`) are
accepted and upgraded by `agent_monitor._schema_migrations.migrate()`.

## Viewer behaviour notes

- **3-column layout**: trace list (left) / Mermaid agent flow (centre) /
  span detail (right). The page itself does not scroll; the left and right
  columns scroll independently.
- **Click a node** in the flowchart to select that span without a full page
  reload (a bidirectional Streamlit component posts the span id back).
  `?focus=<span_id>` and `?trace=<trace_id>` deep links are supported.
- **Cost estimate** uses the static `_COST_PER_1K` table in
  `viewer_app/config.py`; unknown (provider, model) pairs simply show no cost.
- **Feedback tab** is a placeholder -- the SDK does not record feedback scores
  yet, but `feedback` / `feedback.score` attributes are rendered if present.

## Tests

```bash
pip install -e ".[viewer,test]"
python -m pytest            # 54 tests, scoped to tests/ via pyproject.toml
```

The suite covers schema migration, the JSONL exporter's truncate semantics,
framework auto-detection, the CLI `init` scaffolder, `viewer/` normalisation /
naming, and source-level regressions for the viewer.

## Known limitations

- Span-level cost is a static lookup table, not live provider pricing.
- `trace_renderer.build_span_tree()` raises on an empty span list (the viewer
  never calls it with one).
- The repo root still carries environment-specific scratch scripts
  (`test_app.py`, `test_detail.py`, `smoke_test.py`) with hard-coded local
  paths. They are excluded from pytest collection but are not portable.
