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

- The packaged `instrument.py` scaffold now opens one `AGENT` root span around
  your entry point, so a single run is a single trace with a readable name
  instead of one trace per LLM call. An unedited scaffold still exits cleanly.
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
- **One trace per run, even across threads**: `monitor()` now copies the OTel
  context into `ThreadPoolExecutor.submit()` tasks and `threading.Thread`
  instances, so an agent that fans out over threads no longer emits one orphan
  trace per task (the "184 spans, 56 traces" shape). Opt out with
  `--no-thread-context` or `AGENT_MONITOR_THREAD_CONTEXT=0`; `run` now also warns
  on stderr and names the orphan roots when a run still fragments, and `verify`
  gained `--max-traces` so CI can assert a single tree.
- **`JsonlFileExporter` is safe under concurrent export**: `monitor()` installs a
  `SimpleSpanProcessor`, so `export()` runs on whichever thread ends a span. The
  old text-mode append handle let a thread-pool fan-out splice one record across
  two lines, or drop it outright. Each batch is now serialized and emitted as a
  single binary-append `write()` under a process-wide lock (which also stops
  Windows from translating `\n` into `\r\n`).
- **`run` reports success for the normal CLI exit path**: a script ending in
  `raise SystemExit(main())` used to leave the root span `UNSET` (OpenTelemetry
  records `Exception`, never `BaseException`), and every viewer renders `UNSET`
  as "unfinished". Exit `0`/`None` now marks the root `OK`; any other code marks
  it `ERROR` and still propagates.
- **Viewer: one activity diagram instead of a trace list + a capped flowchart.**
  The left trace-card list and the centre flowchart are merged into a single
  UML-activity-diagram-style tree that shows *every* span of the source, rooted
  at the trace's root span (`▶`/`■` for the initial/final node, rounded
  rectangles for activities, hexagons for parallel fork/join bars, and a virtual
  root only when the source genuinely holds several root spans). Clicking a node
  still opens it in the detail column. The old "too many nodes, switch back to
  list mode" 80-node cap is gone; a 2000-node safety valve remains so a runaway
  run cannot lock up the browser tab.

### v1.1.2 maintenance

- **The activity diagram folds repeated calls.** Every round of an agent loop
  produces a *structurally identical* subtree, so a literal one-node-per-span
  graph is mostly 28 copies of the same 4-node pattern laid out side by side --
  the real trace came out as 211 nodes and tens of thousands of pixels wide,
  which is both messy and impossible to read as a whole. Siblings that share a
  subtree shape are now merged into a single node labelled `×N` when (a) they
  are a **parallel fan-out** and (b) the group holds **at least 3** members; the
  multiplicity is carried down the subtree, so the 13 remaining activity nodes
  still stand for all 195 spans -- `sum(multiplicity) == span count` is a
  test-pinned invariant. Folded nodes are drawn as **double-bordered boxes**
  (UML's predefined process). Sequential siblings are never folded (they are
  already a single column and create no width) and a 2-member group is not
  either (saving one node is not worth losing the branch split).
  Unfold on demand with the "expand all spans" checkbox above the diagram, by
  clicking a `×N` node to unfold just that group, or via the "collapse all"
  button that appears while anything is unfolded.
- **`--instrumentors` / `AGENT_MONITOR_INSTRUMENTORS` allow-list.** Two
  instrumentors can cover the *same* call: a langchain-openai app gets
  `ChatOpenAI` from the langchain instrumentor and `ChatCompletion` from the
  openai instrumentor wrapping the very same HTTP request (and the latter is
  parented to the root, adding another top-level branch). Keep just one:

  ```bash
  python -m agent_monitor run --instrumentors langchain run.py
  # or process-wide:  AGENT_MONITOR_INSTRUMENTORS=langchain
  ```

  Comma-separated; `all` / `auto` / `*` mean "no restriction". The allow-list is
  a *filter*, not a substitute -- a name only takes effect if this environment
  actually has that instrumentor, and filtering down to nothing warns on stderr
  instead of silently instrumenting nothing. On the real trace this took the
  duplicate `ChatCompletion` spans from 28 to **0** and LLM spans from 56 to 27.
- The activity diagram's final node now hangs off the **last leaf activity**.
  It used to hang off whichever span ended last, which is always the root, so
  every diagram was drawn as `root --> 结束`.

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
| `agent_monitor/distro.py` | OpenTelemetry distro behind the zero-code entry point |
| `agent_monitor/templates/instrument.py` | Packaged multi-framework scaffold template |
| `viewer.py` | Entry-point launcher for the Streamlit viewer |
| `viewer_app/` | Streamlit viewer implementation (activity-diagram layout) |
| `viewer/` | Framework-agnostic normalisation: span kind, field aliases, naming, visibility |
| `flowchart_component/` | Bidirectional Mermaid flowchart Streamlit component |
| `tests/` | pytest regression suite |
| `examples/langchain_demo/` | End-to-end LangChain example |

### Inside `viewer_app/`

| Module | Purpose |
|---|---|
| `__init__.py` | `run()` -- page assembly + activity-diagram layout ("B") |
| `config.py` | page config, CSS, constants, cost table, default trace paths |
| `state.py` | shared mutable state across reruns |
| `data.py` | `load_traces`, `TraceKPI`, `_aggregate_kpi`, source discovery |
| `format.py` | escaping, duration / token / timestamp formatting, cost estimate |
| `structured.py` | JSON-envelope detection + recursive structured renderer |
| `msg.py` | LLM message card renderer |
| `render_detail.py` | span detail column (Run / Feedback / Metadata tabs) |
| `render_flowchart.py` | Mermaid graph builder + component wrapper |
| `render_tracelist.py` | left-hand trace card list (retained, no longer mounted) |
| `render_activity.py` | activity-diagram builder: one tree over every span, rooted at the root span, with structurally identical subtrees folded into `×N` nodes |

### Inside `viewer/`

| Module | Purpose |
|---|---|
| `canonical.py` | span-kind table + `FIELD_ALIASES` (canonical key -> attribute paths) |
| `normalize.py` | `canon()`, `span_kind()`, `to_messages()`, `friendly_name()` |
| `visibility.py` | plumbing-span / noise-attribute filtering |
| `naming/` | per-framework span-name translation rules |

## Monitor Your Own Agent

Four ways in, from "touch nothing" to "I want full control". All four write the
same `latest_traces.jsonl` and are read by the same viewer:

| # | You want | Command | Edits your code | Root span |
|---|---|---|---|---|
| A | Zero code changes | `OTEL_PYTHON_DISTRO=agent-monitor opentelemetry-instrument python run.py` | no | none -- one trace per framework root run |
| B | One command | `python -m agent_monitor run run.py` | no | yes -- one `AGENT` span per run |
| C | One command, framework already emits a root | `python -m agent_monitor run --no-root-span run.py` | no | none -- your framework's own root is used |
| D | Full control | `python -m agent_monitor init`, then edit `instrument.py` | one file | yes, and you pick the name |

Steps 1-4 below walk through **D** (plus the install every route needs). **A**,
**B** and **C** are covered in [No-edit entry points](#no-edit-entry-points).

`monitor()` is re-entrant, so wrapping a script that already calls `monitor()`
itself is safe: the inner call sees the live provider and degrades to a no-op
instead of fighting over the single global provider a process is allowed to
have. B and C are therefore safe around an existing `instrument.py`-style
script, and A is safe around a script that calls `monitor()` directly.

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

The generated file already opens a root span, so one run is one trace. You
only edit two things:

1. `ROOT_SPAN` (and `SERVICE_NAME`) — `ROOT_SPAN` is the label the viewer shows
   in the trace dropdown, so give it a business name. Do not end it with
   `run` / `agent` / `task` / `step` / `chain`: the viewer strips those as
   generic suffixes and the label would collapse to a single word.
2. the `from run import main` line — point it at your own agent entry point.

Keep that import inside `monitor()` (so the OpenInference patches are active
before your framework builds its objects) but outside the root span (so import
time is not counted as agent runtime). If the module emits spans while being
imported, they land in their own trace — keep it import-side-effect free.

Keep an existing customized `instrument.py`; do not overwrite it with the
scaffold. Update its dependency installation with the matching combined extras
instead.

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

# assert that one agent run is ONE trace tree, not a pile of orphans
python -m agent_monitor verify --trace-file latest_traces.jsonl --max-traces 1
```

`--min-traces` answers "did anything get exported?". It cannot tell you whether
the run stayed in one piece, because a fragmented run has *more* traces, never
fewer. `--max-traces 1` does, and exits 1 when the export holds several trees.

## No-edit entry points

Routes **A**, **B** and **C** from the table in
[Monitor Your Own Agent](#monitor-your-own-agent) need no `instrument.py` at
all -- step 1 (install) is the only prerequisite.

### B / C -- `python -m agent_monitor run`

```bash
# one AGENT root span around the whole run, named after the script
python -m agent_monitor run run.py

# name the root span yourself (this is what the viewer's dropdown shows)
python -m agent_monitor run --root-span "Support Triage" run.py

# your framework already emits a root (FastAPI / Celery / LangGraph):
# skip ours, otherwise you get a double root
python -m agent_monitor run --no-root-span run.py

# everything after the script path is forwarded to the script
python -m agent_monitor run run.py --query hello --top-k 3
```

| flag | default | what it does |
|---|---|---|
| `--root-span NAME` | script filename stem | name of the single `AGENT` root span |
| `--no-root-span` | root span on | let the script's own framework span be the root |
| `--no-thread-context` | context propagation on | stop copying trace context into `ThreadPoolExecutor` / `threading.Thread` tasks |
| `--auto-detect` / `--no-auto-detect` | on | on = activate only the instrumentors whose framework is importable; off = try every installed instrumentor |
| `--instrumentors LIST` | no restriction | comma-separated allow-list of instrumentors (`langchain`, or `openai,anthropic`). On a langchain-openai app, `langchain` drops the duplicate `ChatCompletion` span the openai instrumentor adds to every LLM call. Env equivalent: `AGENT_MONITOR_INSTRUMENTORS` |
| `--service-name NAME` | script filename stem | `service.name` on the OTel resource |
| `--trace-file PATH` | `latest_traces.jsonl` | where the JSONL is written |
| `--exporter jsonl\|console` | `jsonl` | `console` prints spans to stdout instead |

**Every flag must come BEFORE the script path.** `script_args` is collected with
`argparse.REMAINDER`, so anything written after the script name is handed to the
script verbatim and never parsed by us:

```bash
python -m agent_monitor run --root-span X run.py    # ok
python -m agent_monitor run run.py --root-span X    # --root-span X goes to run.py
```

The root span is what makes a run show up as ONE trace: OpenInference passes
`parent_context=None` for a framework run that has no parent run, so the SDK
falls back to the ambient context and adopts our span as its parent. Exceptions
are not swallowed -- the root span gets `ERROR` status and the traceback
propagates exactly as it would without us.

### Why do I see many traces for one run?

A trace is not a container, it is a **tree**: every span without a parent is the
root of its own tree. So "184 spans, 56 traces" means 56 trees, not 56 groups
inside one tree.

The usual cause is a thread boundary. OpenTelemetry keeps the current span in a
`contextvars.ContextVar`, and the stdlib thread primitives do not copy it:
`ThreadPoolExecutor.submit()` hands the callable to a long-lived worker that runs
in the *worker's* (empty) context, and `threading.Thread.start()` starts a fresh
one. Every task an agent fans out over threads then becomes its own trace, no
matter how carefully a root span was injected -- the root simply never reaches
the worker.

`monitor()` therefore patches both, by default, with a per-task
`copy_context().run(...)` -- the same thing `langchain_core`'s
`ContextThreadPoolExecutor` does. `Executor.map()` and `loop.run_in_executor()`
both funnel through `submit()` and are covered too; `asyncio` tasks already copy
the context natively and need nothing. Turn it off with `--no-thread-context`
(route B/C) or `AGENT_MONITOR_THREAD_CONTEXT=0` (any route) if it conflicts with
a patch of your own.

When a run still fragments, `run` says so on stderr and names the orphan roots:

```text
[run] warning: this run produced 4 separate traces (12 spans), not one.
[run]   expected root 'fanout_root', found 3 orphan root(s):
[run]     - 'sub_task' (TOOL) trace 3f2a9c11
[run]   Orphan roots mean trace context was lost. Usual causes:
[run]     * a thread or pool worker started before monitoring was active;
[run]     * multiprocessing / Celery -- contextvars cannot cross processes;
[run]     * --no-thread-context, or AGENT_MONITOR_THREAD_CONTEXT=0.
```

`opentelemetry-instrumentation-threading` is *not* a substitute. It patches
`threading.Thread` only and captures the context when the thread is *created*,
which for a pool is the wrong granularity: workers are created once and reused,
so every task would inherit the first submitter's context (or an empty one when
the pool is built at import time).

### A -- zero code, via the OpenTelemetry distro

```bash
OTEL_PYTHON_DISTRO=agent-monitor opentelemetry-instrument python run.py
```

`opentelemetry-instrument` injects a `sitecustomize` that calls
`auto_instrumentation.initialize()`, which loads the distro named by
`OTEL_PYTHON_DISTRO`. Ours (`agent_monitor/distro.py`) installs the JSONL
exporter as the process-wide backend and keeps that context open until the
process exits, so tracing is already live before your script runs a single line.
There is no CLI hook at this level, so configuration is environment-only:

| variable | default |
|---|---|
| `AGENT_MONITOR_TRACE_FILE` | `latest_traces.jsonl`, relative to the CWD |
| `AGENT_MONITOR_SERVICE_NAME` | `OTEL_SERVICE_NAME`, else the CWD directory name |
| `AGENT_MONITOR_EXPORTER` | `jsonl` (`console` also works) |
| `AGENT_MONITOR_VERBOSE` | unset; `1` prints the resolved config to stderr |
| `AGENT_MONITOR_THREAD_CONTEXT` | on; `0` / `false` / `no` / `off` disables thread propagation |

Two caveats:

- **No root span.** Nothing at this level can wrap your `main()`, so every
  framework root run becomes its own trace and the viewer lists several rows for
  one run. Use B or D when one trace per run matters. Thread propagation is still
  active, so each of those rows is a *complete* tree rather than shards of one.
- **Entry points are read from the installed `dist-info`, not the source tree.**
  After changing `pyproject.toml`, re-install (`pip install -e .`); otherwise
  `_load_distro()` does not find `agent-monitor` and silently falls back to
  `DefaultDistro`, which configures nothing at all.

`opentelemetry-instrument` loads *every* `opentelemetry_instrumentor` entry
point in the environment, not just the OpenInference ones. Exclude the ones you
do not want:

```bash
OTEL_PYTHON_DISABLED_INSTRUMENTATIONS=requests,urllib3 \
OTEL_PYTHON_DISTRO=agent-monitor opentelemetry-instrument python run.py
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
- intersection of the two for the candidate `instrumentors`, then a second
  intersection with `AGENT_MONITOR_INSTRUMENTORS` when that is set (see the
  instrumentor allow-list above)

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
| `instrumentors` | list[str] | None | explicit whitelist of instrumentor names; further narrowed by `AGENT_MONITOR_INSTRUMENTORS` (comma-separated) when that is set |
| `exporter` | str or SpanExporter | None | "jsonl", "console", or a SpanExporter instance |
| `trace_file` | str/Path | "latest_traces.jsonl" | output path when exporter is jsonl |
| `thread_context` | bool or None | None | copy trace context into `ThreadPoolExecutor` / `threading.Thread` tasks; `None` reads `AGENT_MONITOR_THREAD_CONTEXT` and is on unless that is `0`/`false`/`no`/`off` |
| `verbose` | bool | False | print which instrumentors were activated |

`monitor()` is re-entrant. Nesting it is safe: the outermost call owns the
provider, the processor and the instrumentors, while every nested call only
bumps a depth counter and yields the very same tracer. A nested call that passes
a different `service_name` / `trace_file` / `exporter` prints one warning to
stderr and is otherwise ignored -- a process has exactly one global
TracerProvider, so only the outermost call decides where spans go. Cleanup runs
only when the depth returns to zero.

Calling `monitor()` twice *in sequence* is a different story: OpenTelemetry
accepts `set_tracer_provider()` once per process, so the second block cannot get
a provider of its own. Its spans keep going to the first block's file, its own
file stays empty, and it says so on stderr. Nest the calls instead, or use one
`monitor()` for the whole process (`python -m agent_monitor run` does that for
you).


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

- **Activity-diagram layout ("B")**: one UML-activity-diagram tree (left) /
  span detail (right). The whole source is drawn as a single tree rooted at the
  trace's root span -- start `▶` and end `■` nodes, rounded rectangles for
  activities, **double-bordered boxes for folded `×N` groups**, hexagons for
  parallel fork/join bars -- so a 100+ span run is shown in full instead of
  "too many nodes".
- **Structurally identical subtrees are folded by default.** `sum(multiplicity)
  == span count` guarantees nothing is hidden; the repeated rounds just are not
  drawn N times over. The "expand all spans" checkbox switches to the literal
  one-node-per-span graph, clicking a `×N` node unfolds only that group, and a
  "collapse all" button appears while anything is unfolded.
- **Click a node** in the diagram to select that span (clicking a `×N` group
  selects its representative *and* unfolds the group) without a full page
  reload (a bidirectional Streamlit component posts the span id back).
  `?focus=<span_id>` deep links are supported.
- **Cost estimate** uses the static `_COST_PER_1K` table in
  `viewer_app/config.py`; unknown (provider, model) pairs simply show no cost.
- **Feedback tab** is a placeholder -- the SDK does not record feedback scores
  yet, but `feedback` / `feedback.score` attributes are rendered if present.

## Tests

```bash
pip install -e ".[viewer,test]"
python -m pytest            # 166 tests, scoped to tests/ via pyproject.toml
```

The suite covers schema migration, the JSONL exporter's truncate semantics,
framework auto-detection, the CLI `init` scaffolder, `monitor()` re-entrancy,
thread-boundary context propagation, the `verify` trace-tree checks, the `run`
root span and the zero-code distro (all end-to-end, in subprocesses), `viewer/`
normalisation / naming, the instrumentor allow-list, the activity diagram's
folding invariant (`sum(multiplicity) == span count`), and source-level
regressions for the viewer.

## Known limitations

- Span-level cost is a static lookup table, not live provider pricing.
- `trace_renderer.build_span_tree()` raises on an empty span list (the viewer
  never calls it with one).
- The repo root still carries environment-specific scratch scripts
  (`test_app.py`, `test_detail.py`, `smoke_test.py`) with hard-coded local
  paths. They are excluded from pytest collection but are not portable.
- OpenTelemetry accepts `set_tracer_provider()` only once per process. Two
  *sequential* `monitor()` blocks therefore cannot write to two different files:
  the second one keeps exporting into the first one's file and warns on stderr.
  Nest them instead (nested calls are no-ops), or use a single `monitor()` per
  process.
- Every `run` flag must be written before the script path. `script_args` uses
  `argparse.REMAINDER`, so anything after the script name is forwarded to the
  script instead of being parsed.
- Thread propagation stops at the process boundary. `contextvars` cannot cross
  into a `multiprocessing` child or a Celery worker, so those still start their
  own traces; that needs `TRACEPARENT` injection into the child environment and
  is not implemented here.
- With `--no-thread-context` (or `AGENT_MONITOR_THREAD_CONTEXT=0`) you get the
  old behaviour back: one orphan trace per task handed to a thread pool. `run`
  warns about the resulting trees on stderr instead of failing.
- A task submitted to a pool may start after its submitter's span has ended.
  OpenTelemetry accepts that -- `trace_id` is shared and `parent_span_id` is
  recorded -- but the timeline in a viewer can look inverted.
- Concurrent JSONL writes are serialized in-process only. `JsonlFileExporter`
  emits each batch as a single binary-append `write()` under a process-wide
  lock, so a `ThreadPoolExecutor` fan-out can no longer splice one record
  across two lines or drop one outright. Two *processes* exporting to the same
  file at the same time are still unsafe -- give each its own `--trace-file`.
