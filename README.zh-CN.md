# 本地 Agent 监控

**简体中文** | [English](README.md)

独立运行的本地 Agent 监控 —— 无需任何远程依赖即可追踪 Agent 的执行过程。
**所有 trace 都只存在本地**，不会有任何数据被发送到远程 collector。

当前版本：**1.1.1**（JSONL schema 版本 `1.1.0`）

```
Phoenix 原本的做法：
  OTel SDK -> OTLP Exporter -> Phoenix Collector -> 数据库 -> Web UI

本工具的做法：
  OTel SDK -> JsonlFileExporter -> ./latest_traces.jsonl -> viewer
```

从 Phoenix 中抽离出来的核心是 **OpenTelemetry + OpenInference 自动埋点层**。
OpenInference 的 instrumentor（OpenAI、LangChain 等）会产生带语义约定属性的
span（`input.value`、`output.value`、`llm.token_count.*` 等）。本工具不把这些
span 发往远程 collector，而是用自定义的 `JsonlFileExporter` 把每个 span 作为
一行 JSON 流式写入本地文件。

## v1.1 新增内容

- **Schema 版本化**：每条 JSONL 记录现在都带 `schema_version`。消费方
  （viewer、render、verify）会自动迁移旧记录。
- **自动探测**：给 `monitor()` 传 `auto_detect=True`，SDK 会嗅探哪些框架
  可导入、哪些 instrumentor 已安装，然后只激活命中的那些。
- **默认导出器改为 JSONL**：不带参数调用 `monitor()` 现在会写
  `latest_traces.jsonl`。如果你想要旧的行为（在 `traces/` 下生成嵌套 JSON
  树），传 `exporter="console"`。
- **模板**：一份打包内的 `instrument.py` 模板可适配任意框架组合，并会渲染出
  一份显式的 `INSTRUMENTORS` 列表。
- **CLI 脚手架**：`python -m agent_monitor init` 会自动探测所有已安装的框架，
  安装它们对应的 OpenInference extras，并生成一个 `instrument.py` 起步文件。
- **导出校验器**：`python -m agent_monitor verify` 用于检查 JSONL 文件格式
  是否合法、内容是否有意义。

### v1.1.1 维护性改动

- 三栏 Streamlit viewer 已从单文件 `viewer.py` 拆分为 `viewer_app/` 包
  （字段归一化相关的辅助函数仍留在 `viewer/`）。`viewer.py` 现在只是一个
  极薄的启动器，因此 `streamlit run viewer.py` 的用法完全不受影响。
- 修复了 viewer 中 KPI 聚合的崩溃（拆分时 `TraceKPI` 丢了 `@dataclass`
  装饰器，导致任何含 `AGENT` span 的 trace 都会抛 `TypeError`）。
- `agent_monitor run` 在未指定 `--service-name` 时，按文档所述改用脚本文件名
  作为 `service.name`。
- `pytest` 的收集范围被限定在 `tests/`，仓库根目录那些依赖具体环境的临时脚本
  不再被误收集。

## 文件说明

| 文件 | 作用 |
|---|---|
| `agent_monitor/monitor.py` | 带 `auto_detect` 与 JSONL 默认值的 `monitor()` 上下文管理器 |
| `agent_monitor/jsonl_exporter.py` | `JsonlFileExporter`（流式写入）+ `SCHEMA_VERSION` |
| `agent_monitor/console_exporter.py` | `ConsoleSpanExporter`（嵌套 JSON，每个 trace 一个文件） |
| `agent_monitor/trace_renderer.py` | 终端树状渲染器（ANSI） |
| `agent_monitor/_detect.py` | 框架与 instrumentor 自动探测 |
| `agent_monitor/_schema_migrations.py` | schema 版本升级逻辑 |
| `agent_monitor/_verify_export.py` | 校验 JSONL 导出文件 |
| `agent_monitor/__main__.py` | CLI：`init`、`run`、`detect`、`verify`、`view` |
| `agent_monitor/templates/instrument.py` | 打包内的多框架脚手架模板 |
| `viewer.py` | Streamlit viewer 的入口启动器 |
| `viewer_app/` | Streamlit viewer 的具体实现（三栏布局） |
| `viewer/` | 与框架无关的归一化：span kind、字段别名、命名、可见性 |
| `flowchart_component/` | 双向联动的 Mermaid 流程图 Streamlit 组件 |
| `tests/` | pytest 回归测试集 |
| `examples/langchain_demo/` | 端到端 LangChain 示例 |

### `viewer_app/` 内部结构

| 模块 | 作用 |
|---|---|
| `__init__.py` | `run()` —— 页面组装 + 三栏布局 |
| `config.py` | 页面配置、CSS、常量、价格表、默认 trace 路径 |
| `state.py` | 跨 rerun 共享的可变状态 |
| `data.py` | `load_traces`、`TraceKPI`、`_aggregate_kpi`、数据源发现 |
| `format.py` | 转义、时长 / token / 时间戳格式化、成本估算 |
| `structured.py` | JSON 信封识别 + 递归结构化渲染器 |
| `msg.py` | LLM 消息卡片渲染器 |
| `render_detail.py` | span 详情栏（Run / Feedback / Metadata 三个标签页） |
| `render_flowchart.py` | Mermaid 图构建 + 组件封装 |
| `render_tracelist.py` | 左侧 trace 卡片列表 |

### `viewer/` 内部结构

| 模块 | 作用 |
|---|---|
| `canonical.py` | span kind 对照表 + `FIELD_ALIASES`（规范键 -> 属性路径） |
| `normalize.py` | `canon()`、`span_kind()`、`to_messages()`、`friendly_name()` |
| `visibility.py` | 管道型 span / 噪声属性的过滤 |
| `naming/` | 各框架的 span 名称翻译规则 |

## 监控你自己的 Agent

### 1. 安装

```bash
# 在源码目录里用 editable 模式安装，并叠加需要的 extras：
pip install -e ".[langchain,openai]"

# 从已发布的 wheel 安装：
# SDK 核心（仅 OTel + monitor 上下文管理器）
pip install agent-monitor

# 再加上你实际使用的框架
pip install "agent-monitor[langchain,openai]"     # 最常见的组合
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

# 一次性装齐
pip install "agent-monitor[all-instruments]"

# 只装 viewer 与测试工具链
pip install -e ".[viewer,test]"
```

### 2. 生成 `instrument.py`

生成起步文件，然后把函数体改成调用你自己的 Agent：

```bash
python -m agent_monitor init --framework auto

# 或者明确指定框架集合
python -m agent_monitor init --framework langchain,openai

# 只写文件、不安装任何依赖（适用于 CI / 离线环境）
python -m agent_monitor init --framework auto --no-install-deps
```

修改其中的 `SERVICE_NAME`，并把 `with monitor(...)` 块里的占位调用换成你真实的
Agent 入口调用。如果 `instrument.py` 你已经改过，请**保留它、不要用新生成的
覆盖**，改用与框架匹配的组合 extras 去更新它的依赖。

### 3. 运行并查看

```bash
# 终端 A：跑 Agent
python instrument.py
# -> 写入 ./latest_traces.jsonl（流式，每个 span 一行）

# 终端 B：针对该文件启动 Streamlit viewer
python -m agent_monitor view
# 或者直接指向 viewer：
streamlit run viewer.py
# -> 打开 http://localhost:8501，每 3 秒自动刷新
```

`python -m agent_monitor view` 会相对于当前目录解析 trace 文件、相对于已安装的
包解析 viewer，因此在任何工作目录下都能用。加 `--no-launch` 可以只打印解析出的
命令而不真正启动。

viewer 按以下顺序查找 trace 文件：
`$TRACE_FILE` -> `./latest_traces.jsonl` -> `viewer_app/config.py` 里的两个兜底
路径（`_DEFAULT_TRACE_PATHS`）。

### 4. 校验（可选，在 CI 里很有用）

```bash
python -m agent_monitor verify --trace-file latest_traces.jsonl \
                               --min-spans 10 \
                               --require-kind LLM
```

## auto_detect=True

如果你不想把 `INSTRUMENTORS` 写死，可以让 SDK 自己判断：

```python
from agent_monitor import monitor
with monitor(service_name="my-agent", auto_instrument=True, auto_detect=True):
    # 所有「已安装且可导入」的框架，其 OpenInference instrumentor
    # 都会被自动激活。
    ...
```

探测逻辑依赖：

- `importlib.util.find_spec(...)` —— 判断哪些框架模块存在
- `importlib.metadata.entry_points(group="openinference_instrumentor")` ——
  判断哪些 instrumentor 已安装
- 两者取交集，作为最终的 `instrumentors`

运行 `python -m agent_monitor detect` 可以查看诊断输出。

## API 速查

```python
from agent_monitor import (
    monitor,                 # 上下文管理器
    span,                    # @span 装饰器
    trace,                   # @trace 装饰器
    JsonlFileExporter,       # 流式本地导出器
    ConsoleSpanExporter,     # 嵌套树状本地导出器
    SCHEMA_VERSION,          # 当前 JSONL schema 版本
    migrate,                 # 把旧记录升级到 SCHEMA_VERSION
    verify_export,           # 校验 JSONL 导出文件
    detect_compatible,       # 嗅探可用的 instrumentor
)
```

`monitor(...)` 的参数：

| 参数 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `service_name` | str | `"agent"` | OTel 的 resource.service.name |
| `auto_instrument` | bool | `False` | 是否激活 OpenInference instrumentor |
| `auto_detect` | bool | `False` | 是否嗅探该激活哪些 instrumentor |
| `instrumentors` | list[str] | `None` | 显式的 instrumentor 名称白名单 |
| `exporter` | str 或 SpanExporter | `None` | `"jsonl"`、`"console"`，或一个 SpanExporter 实例 |
| `trace_file` | str/Path | `"latest_traces.jsonl"` | exporter 为 jsonl 时的输出路径 |
| `verbose` | bool | `False` | 是否打印实际激活了哪些 instrumentor |

## Schema v1.1 记录结构

```jsonc
{
  "schema_version": "1.1.0",
  "service_name":   "my-agent",
  "trace_id":       "0" * 32 hex,
  "span_id":        "0" * 16 hex,
  "parent_span_id": "0" * 16 hex 或 null,
  "name":           "ChatOpenAI",
  "start_time":     1723712345678901234,   // Unix 纳秒时间戳
  "end_time":       1723712345678901234,
  "duration_ms":    1000.0,
  "status":         "OK",
  "kind":           "LLM",
  "attributes": {
    "input.value":   "...",
    "output.value":  "...",
    "llm.model_name": "MiniMax-M3",       // 由 output.value 展平而来
    "llm.token_count.prompt": 273,
    "llm.token_count.completion": 253,
    "llm.token_count.total": 526,
    "openinference.span.kind": "LLM"
  },
  "events": []
}
```

v1.1 之前产生的记录（没有 `schema_version`、没有 `service_name`）同样可以被
接受，并由 `agent_monitor._schema_migrations.migrate()` 升级。

## Viewer 行为说明

- **三栏布局**：trace 列表（左）/ Mermaid Agent 流程图（中）/ span 详情（右）。
  页面整体不滚动，左右两栏各自独立滚动。
- **点击流程图里的节点**即可选中对应 span，且不会触发整页刷新（一个双向的
  Streamlit 组件会把 span id 回传）。同时支持 `?focus=<span_id>` 与
  `?trace=<trace_id>` 深链。
- **成本估算**用的是 `viewer_app/config.py` 里的静态 `_COST_PER_1K` 表；表中
  没有的 (provider, model) 组合就直接不显示成本。
- **Feedback 标签页**目前是占位实现 —— SDK 尚未记录反馈分数，但如果 span 属性
  里存在 `feedback` / `feedback.score`，仍会渲染出来。

## 测试

```bash
pip install -e ".[viewer,test]"
python -m pytest            # 54 个测试，收集范围由 pyproject.toml 限定在 tests/
```

测试覆盖：schema 迁移、JSONL 导出器的截断语义、框架自动探测、CLI 的 `init`
脚手架、`viewer/` 的归一化与命名，以及针对 viewer 的源码级回归断言。

## 已知限制

- span 级别的成本是静态查表，不是各 provider 的实时价格。
- `trace_renderer.build_span_tree()` 在传入空 span 列表时会抛异常（viewer
  不会以空列表调用它）。
- 仓库根目录仍保留了若干依赖具体环境的临时脚本（`test_app.py`、
  `test_detail.py`、`smoke_test.py`），其中写死了本机路径。它们已被排除在
  pytest 收集范围之外，但不具备可移植性。
