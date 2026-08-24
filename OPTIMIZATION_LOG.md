# Optimization log

This document describes the v1.0 -> v1.1 optimization pass. Every file
touched is listed, the change summarized, and the rationale given.

---

## Goal

> "Make every agent, regardless of framework, automatically produce a local
> JSONL trace file. No third-party platform. No magic."

Two pillars:

1. **Automation**: sniff the framework; provide per-framework templates; CLI
   scaffolder.
2. **Standardization**: unified JSONL schema with version; verifier; local-only
   default exporter.

---

## What changed (file-by-file)

### NEW files

| File | Purpose |
|---|---|
| `agent_monitor/_detect.py` | Detect which frameworks are importable AND which OpenInference instrumentors are installed; return the intersection. |
| `agent_monitor/_schema_migrations.py` | Upgrade old JSONL records to the current schema in-place. |
| `agent_monitor/_verify_export.py` | Validate a JSONL export (existence, parseability, span/trace counts, required kinds). |
| `agent_monitor/__main__.py` | CLI: `init` scaffolds instrument.py, `run` wraps a script in monitor(), `detect` prints detection, `verify` validates an export. |
| `examples/_templates/instrument_<framework>.py` (x14) | Drop-in `instrument.py` for every supported framework plus a hand-rolled template. |
| `examples/_templates/README.md` | Index of templates and how to use them. |
| `OPTIMIZATION_LOG.md` | This document. |

### CHANGED files

| File | Change |
|---|---|
| `agent_monitor/monitor.py` | Added `auto_detect`, `trace_file` parameters; default exporter switched from `ConsoleSpanExporter` to `JsonlFileExporter`; `_resolve_named_exporter` honors `trace_file`. |
| `agent_monitor/jsonl_exporter.py` | New `SCHEMA_VERSION = "1.1.0"`; every record now has `schema_version` + `service_name`; `_flatten_llm_attrs` lifts `llm.model_name` / `llm.token_count.*` / `llm.provider` from nested `output.value` JSON into top-level `attributes`. |
| `agent_monitor/__init__.py` | Exports `JsonlFileExporter`, `SCHEMA_VERSION`, `migrate`, `detect_*`, `verify_export`, `list_supported_frameworks`. |
| `viewer.py` | `load_traces` calls `_migrate_record` on every line; UI shows `service_name`; sidebar header rewritten. |
| `README.md` | Local-only statement; new v1.1 section; auto_detect docs; CLI reference; schema v1.1 record shape. |
| `D:\agent\complex-agent-langchain\render.py` (your project) | `_load_spans` calls `_migrate_record`; tree renderer shows `svc=...`; output indicators cleaned up. |

### UNTOUCHED files

| File | Why |
|---|---|
| `agent_monitor/console_exporter.py` | Still used when `exporter="console"`; not on the default path. |
| `agent_monitor/trace_renderer.py` | Already a generic ANSI renderer; orthogonal to JSONL changes. |
| `pyproject.toml` | No dependency changes; extras already cover all 13 frameworks. |
| `examples/langchain_demo/` | Pre-existing demo; still works. |
| `viewer.py` content other than `load_traces` + sidebar | Cosmetic; core behavior unchanged. |
| `D:\agent\complex-agent-langchain\**` (your project) other than `render.py` | Per scope; only `render.py` needs to consume the v1.1 schema. |

---

## Design decisions

### Why `JsonlFileExporter` became the default

Before:
```python
if exporter is None:
    exporter = ConsoleSpanExporter(service_name=service_name)  # nested JSON to traces/
```

After:
```python
if exporter is None:
    path = os.fspath(trace_file) if trace_file is not None else DEFAULT_TRACE_FILE
    exporter = JsonlFileExporter(file_path=path)  # streaming JSONL to ./latest_traces.jsonl
```

Rationale: "user opens terminal, runs python instrument.py, expects a file"
is the dominant case. The nested console exporter is still available via
`exporter="console"` for users who explicitly want it.

### Why `auto_detect=True` rather than `auto_instrument=True` auto-sniffing

`auto_instrument=True` already exists and walks every registered
OpenInference instrumentor. That's the wrong default -- if the user has
installed crewai instrumentor but their agent is LangChain, they get both
activated, and crewai's patchers touch unrelated code.

The new `auto_detect=True` is opt-in, runs **before** auto_instrument, and
uses Layer A (importable frameworks) ∩ Layer B (installed instrumentors) to
produce a narrow whitelist. Explicit `instrumentors=[...]` always wins.

### Why schema versioning and not just ad-hoc fields

The previous records had no version. Adding fields silently works for
forgiving consumers (Python's `.get()` defaults), but breaks any consumer
that does `record["new_field"]` directly. The version field lets consumers
say "I know about 1.1.0; anything older, please migrate first." The
migrator is idempotent and additive-only -- existing records always come
through with all original fields intact.

### Why `_flatten_llm_attrs` (instead of asking instrumentors to flatten)

OpenInference's `langchain` and `openai` instrumentors put `llm.model_name`
inside `output.value` as part of the OpenAI response payload. That's
correct OTel behavior (the model name IS a property of the response, not of
the span), but consumers like `viewer.py` and `render.py` want easy access
to `record["attributes"]["llm.model_name"]`. We do the flatten on the
**exporter side** so:

- The OTel payload stays OTel-standard
- Consumers stay simple
- No SDK dependency on a specific instrumentor version

### Why a CLI scaffolder (`python -m agent_monitor init`)

Frameworks have different INSTRUMENTORS strings. New users shouldn't have to
memorize that langchain-openai needs `"langchain", "openai"`, that
LlamaIndex is `"llama-index"` (with a dash), etc. The CLI:

- `--framework auto` runs detection and picks the first match
- `--framework <name>` selects a template by name
- copies the right file into `instrument.py`
- prints the next-step hint

The scaffolder is implemented in `__main__.py::_resolve_template`. Adding a
new framework means: drop a new `instrument_<x>.py` template; the scaffolder
finds it automatically.

### Why a CLI runner (`python -m agent_monitor run ...`) is included but not documented

It exists to wrap a user script in monitor() without requiring an
`instrument.py`. We did not push it as the default UX because:

- It obscures the framework import order (instrumentors must patch BEFORE
  the agent's framework is imported)
- It requires `runpy.run_path`, which has surprising behavior with
  `__main__` guards and stdin

Users who want it can read `agent_monitor/__main__.py::cmd_run`. Most should
stick with the template-then-`python instrument.py` flow.

### Why viewer.py gets a `service_name` column

Previously, all agents wrote to the same `latest_traces.jsonl`, so if two
agents ran in sequence their traces mixed together -- distinguishable only
by `trace_id` (random hex). With `service_name` in every record, the viewer
can filter or color-code by agent, and `verify_export` can require
`service_name` matches an expected value.

---

## Schema v1.0 -> v1.1 migration table

| Field | v1.0.0 | v1.1.0 | Migration behavior |
|---|---|---|---|
| `schema_version` | absent | `"1.1.0"` | Filled by producer; consumer migrate() fills it for old records. |
| `service_name` | absent | `<from OTel resource>` | Producer writes from `Resource.create({"service.name": ...})`; consumer migrate() sets `None` for old records. |
| `attributes.llm.model_name` | only inside `output.value` JSON | top-level attribute | Producer flattens; consumer migrate() leaves old records alone (still readable via output.value). |
| `attributes.llm.provider` | only inside `output.value` JSON | top-level attribute | Same. |
| `attributes.llm.token_count.*` | only inside `output.value` JSON | top-level attribute | Same. |
| `trace_id` / `span_id` / `parent_span_id` / `name` / `start_time` / `end_time` / `duration_ms` / `status` / `kind` / `attributes` / `events` | unchanged | unchanged | No migration needed. |

---

## Auto-detection coverage

| Framework key | Top-level module | Instrumentor package | Result if missing |
|---|---|---|---|
| langchain | langchain_core | openinference-instrumentation-langchain | Skipped silently |
| openai | openai | openinference-instrumentation-openai | Skipped silently |
| llama-index | llama_index.core | openinference-instrumentation-llama-index | Skipped silently |
| anthropic | anthropic | openinference-instrumentation-anthropic | Skipped silently |
| google-genai | google.genai | openinference-instrumentation-google-genai | Skipped silently |
| groq | groq | openinference-instrumentation-groq | Skipped silently |
| dspy | dspy | openinference-instrumentation-dspy | Skipped silently |
| autogen | autogen | openinference-instrumentation-autogen | Skipped silently |
| haystack | haystack | openinference-instrumentation-haystack | Skipped silently |
| smolagents | smolagents | openinference-instrumentation-smolagents | Skipped silently |
| crewai | crewai | openinference-instrumentation-crewai | Skipped silently |
| bedrock | boto3 | openinference-instrumentation-bedrock | Skipped silently |
| litellm | litellm | openinference-instrumentation-litellm | Skipped silently |

`detect_compatible()` returns the subset whose top-level module is
importable AND whose instrumentor entry_point is registered. This is the
list passed to `auto_instrument` when `auto_detect=True`.

---

## Smoke tests (all passing)

1. `import agent_monitor; from agent_monitor import (...)` -- all public
   symbols importable.
2. `monitor(service_name="x", auto_detect=True, verbose=True)` -- prints
   `[monitor] auto-detected instrumentors: ['langchain', 'openai']` and
   activates both.
3. `JsonlFileExporter` -- writes records with `schema_version="1.1.0"` and
   `service_name="x"`.
4. `_flatten_llm_attrs` -- lifts `llm.model_name=MiniMax-M3` from
   `output.value` JSON into `attributes["llm.model_name"]`.
5. `migrate(old_v1_0_record)` -- returns a record with `schema_version="1.1.0"`
   and `service_name=None`.
6. `verify_export(...)` -- reports `RESULT: OK` for a well-formed file.
7. `python -m agent_monitor detect` -- lists installed frameworks and
   compatible intersection.
8. `python -m agent_monitor init --framework langchain_openai` -- writes
   `instrument.py` from the right template.
9. `python -m agent_monitor init --framework auto` -- sniffs env and picks
   the first compatible template.
10. `python -m agent_monitor verify --trace-file X --require-kind LLM` --
    validates an export, exits 0 on pass.
11. `render.py` on the existing v1.0 `latest_traces.jsonl` -- loads,
    migrates, renders without error. Backward compatibility confirmed.
12. `viewer.py` parses; `load_traces` calls migrate on every line.

---

## What the user does now (the new default workflow)

```bash
# new agent, framework = LangChain + OpenAI
cd my-new-agent
python -m agent_monitor init --framework langchain_openai
# -> wrote instrument.py
# edit the 3 knobs

python instrument.py
# -> auto-detects (no, you gave it explicitly), writes latest_traces.jsonl

# verify it worked
python -m agent_monitor verify --min-spans 5 --require-kind LLM

# open the viewer
streamlit run D:/my-projects/agent-monitor/viewer.py
```

Three commands. No git changes to the SDK, no manual `exporter="jsonl"`
reminder, no third-party platform, no internet.