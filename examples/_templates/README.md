# Instrument templates

Drop-in `instrument.py` files for every supported framework. Each template is
~10 lines and only differs in which `INSTRUMENTORS=` are activated.

## Usage

```
# 1. pick the template that matches your agent
cp examples/_templates/instrument_langchain_openai.py instrument.py

# 2. edit the 3 knobs at the top of the file:
#      SERVICE_NAME, INSTRUMENTORS, and the body of the `with monitor(...)` block

# 3. run it
python instrument.py
# -> writes ./latest_traces.jsonl
```

## Or use the CLI scaffolder

```
python -m agent_monitor init                              # default: langchain
python -m agent_monitor init --framework langchain_openai # most common combo
python -m agent_monitor init --framework auto             # sniff your env
```

## Which template should I pick?

| Your agent | Use this template |
|---|---|
| LangChain LCEL only (no separate OpenAI SDK call) | `instrument_langchain.py` |
| LangChain + `langchain_openai.ChatOpenAI` (most common) | `instrument_langchain_openai.py` |
| Pure OpenAI SDK (`openai.OpenAI().chat.completions.create`) | `instrument_openai.py` |
| Anthropic SDK (Claude) | `instrument_anthropic.py` |
| LlamaIndex query engine | `instrument_llama_index.py` |
| CrewAI crew | `instrument_crewai.py` |
| DSPy program | `instrument_dspy.py` |
| Microsoft autogen | `instrument_autogen.py` |
| Haystack pipeline | `instrument_haystack.py` |
| HuggingFace smolagents | `instrument_smolagents.py` |
| Groq | `instrument_groq.py` |
| Google Generative AI (Gemini) | `instrument_google_genai.py` |
| AWS Bedrock | `instrument_bedrock.py` |
| Hand-rolled agent loop (no framework) | `instrument_pure_no_framework.py` |

## What they all have in common

```python
with monitor(
    service_name=SERVICE_NAME,
    auto_instrument=True,
    instrumentors=INSTRUMENTORS,
    exporter="jsonl",   # writes ./latest_traces.jsonl
):
    # your agent's main() goes here
```

That is the entire interface. Every template writes the same JSONL schema
(`schema_version` 1.1.0) and is read by the same `viewer.py` /
`render.py` / `agent_monitor verify` consumers.

## Adding a new framework template

Drop another `instrument_<your_framework>.py` in this directory and (optionally)
extend the `__main__.py --framework` registry. The template body is just the
HEADER pattern in the original generator (kept in git history).