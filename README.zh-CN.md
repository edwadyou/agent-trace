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

- 打包的 `instrument.py` 脚手架现在会在你的入口外开一个 `AGENT` root span，
  于是「一次运行 = 一条 trace，且名字可读」，而不是每次 LLM 调用各成一条 trace。
  未经编辑的脚手架仍然能正常跑完（不会抛 ImportError）。
- 三栏 Streamlit viewer 已从单文件 `viewer.py` 拆分为 `viewer_app/` 包
  （字段归一化相关的辅助函数仍留在 `viewer/`）。`viewer.py` 现在只是一个
  极薄的启动器，因此 `streamlit run viewer.py` 的用法完全不受影响。
- 修复了 viewer 中 KPI 聚合的崩溃（拆分时 `TraceKPI` 丢了 `@dataclass`
  装饰器，导致任何含 `AGENT` span 的 trace 都会抛 `TypeError`）。
- `agent_monitor run` 在未指定 `--service-name` 时，按文档所述改用脚本文件名
  作为 `service.name`。
- `pytest` 的收集范围被限定在 `tests/`，仓库根目录那些依赖具体环境的临时脚本
  不再被误收集。
- **一次运行 = 一条 trace，线程边界也不例外**：`monitor()` 现在会把 OTel context
  复制进 `ThreadPoolExecutor.submit()` 的任务与 `threading.Thread` 实例，因此
  用线程做扇出的 agent 不再「每个任务一条孤儿 trace」（也就是「184 spans、
  56 traces」那种形态）。可用 `--no-thread-context` 或
  `AGENT_MONITOR_THREAD_CONTEXT=0` 关闭；`run` 还会在轨迹仍然碎片化时把孤儿根
  打到 stderr 上，`verify` 新增 `--max-traces`，让 CI 能断言"只有一棵树"。
- **`JsonlFileExporter` 在并发导出下安全**：`monitor()` 装的是
  `SimpleSpanProcessor`，所以 `export()` 会在"结束该 span 的那个线程"上执行。
  过去的文本模式追加句柄会让线程池扇出把一条记录写断成两行，甚至整条丢掉。
  现在每批记录先完整序列化，再在进程级锁下以一次二进制追加 `write()` 写出
  （顺带避免了 Windows 把 `\n` 翻译成 `\r\n`）。
- **`run` 会把"常规 CLI 退出"记为成功**：以 `raise SystemExit(main())` 结尾的
  脚本过去会让 root span 停在 `UNSET`（OpenTelemetry 只记录 `Exception`，从不记录
  `BaseException`），而 viewer 会把 `UNSET` 显示成"未完成"。现在退出码为
  `0`/`None` 会标记 root 为 `OK`；其它退出码标记为 `ERROR` 并照旧向外传播。
- **viewer 改成「一张活动图」**：左栏的 trace 卡片列表与中栏的流程图合并成一张
  UML 活动图风格的一棵树，显示该数据源里的**全部** span，并以 trace 的 root span
  为根（`▶`/`■` 是起点/终点，圆角矩形是活动，六边形是并行分支与汇聚；只有当数据源
  里真的存在多个 root span 时，才会多一个虚拟根）。点击节点照旧在右栏看详情。
  原来「节点数过多，请切回 列表 模式查看」的 80 节点上限已移除，只保留 2000 个
  节点的安全阀，防止失控的运行把浏览器标签页卡死。

### v1.1.2 维护性改动

- **活动图会折叠重复调用**。agent 每一轮循环产生的子树是**同构**的，所以「一个 span
  一个节点」画出来基本就是 28 份同样的 4 节点图案并排铺开——真实轨迹因此得到 211 个
  节点、上万像素宽，既乱又不可能一眼看全。现在，同一父节点下**结构相同**的兄弟只要
  满足**并行扇出**且**个数 ≥ 3**，就合并成一个节点并标注 `×N`；重数会沿子树往下传递，
  所以折叠后的 13 个活动节点依然代表全部 195 个 span——`Σ重数 == span 数` 这个不变量
  被测试钉住。折叠出的节点画成**双线框**（UML 的 predefined process）。
  两条保护规则：顺序兄弟不折叠（它们本来就是一列纵向排列，不制造宽度），只有 2 个
  成员的组也不折叠（省 1 个节点却丢掉分支结构，不划算）。
  交互：图上方勾选「展开全部 span」回到全量视图；直接点某个 `×N` 节点只展开那一组；
  有展开时会出现「收起全部」按钮。
- **`--instrumentors` / `AGENT_MONITOR_INSTRUMENTORS` 插桩器白名单**。两个插桩器可以
  覆盖**同一次调用**：langchain-openai 应用会从 langchain 插桩器拿到 `ChatOpenAI`，
  又从 openai 插桩器拿到包住同一个 HTTP 请求的 `ChatCompletion`（而且后者会被挂到
  root 底下，成为 root 的又一个一级分支）。现在可以只留一个：

  ```bash
  python -m agent_monitor run --instrumentors langchain run.py
  # 或进程级生效： AGENT_MONITOR_INSTRUMENTORS=langchain
  ```

  逗号分隔，`all` / `auto` / `*` 表示不限制。白名单是**过滤器**而非替代品——只有当
  这个环境确实装了对应插桩器时才会生效；若过滤后一个都不剩，会打一条 stderr 告警
  而不是静默地什么都不插桩。实测那条真实轨迹：重复的 `ChatCompletion` 从 28 个降到
  **0**，LLM span 从 56 降到 27。
- 活动图的 `结束` 节点改为从**最后一个叶子活动**连出。此前它取所有 span 里结束最晚的
  那个，而 root span 覆盖整轮运行，于是每张图都被画成 `root --> 结束`。

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
| `agent_monitor/distro.py` | 零代码入口背后的 OpenTelemetry distro |
| `agent_monitor/templates/instrument.py` | 打包内的多框架脚手架模板 |
| `viewer.py` | Streamlit viewer 的入口启动器 |
| `viewer_app/` | Streamlit viewer 的具体实现（活动图布局） |
| `viewer/` | 与框架无关的归一化：span kind、字段别名、命名、可见性 |
| `flowchart_component/` | 双向联动的 Mermaid 流程图 Streamlit 组件 |
| `tests/` | pytest 回归测试集 |
| `examples/langchain_demo/` | 端到端 LangChain 示例 |

### `viewer_app/` 内部结构

| 模块 | 作用 |
|---|---|
| `__init__.py` | `run()` —— 页面组装 + 活动图布局（布局 "B"） |
| `config.py` | 页面配置、CSS、常量、价格表、默认 trace 路径 |
| `state.py` | 跨 rerun 共享的可变状态 |
| `data.py` | `load_traces`、`TraceKPI`、`_aggregate_kpi`、数据源发现 |
| `format.py` | 转义、时长 / token / 时间戳格式化、成本估算 |
| `structured.py` | JSON 信封识别 + 递归结构化渲染器 |
| `msg.py` | LLM 消息卡片渲染器 |
| `render_detail.py` | span 详情栏（Run / Feedback / Metadata 三个标签页） |
| `render_flowchart.py` | Mermaid 图构建 + 组件封装 |
| `render_tracelist.py` | 左侧 trace 卡片列表（保留，但已不再挂载） |
| `render_activity.py` | 活动图构建：把全部 span 连成一棵树、以 root span 为根，并把同构的重复子树折叠成 `×N` |

### `viewer/` 内部结构

| 模块 | 作用 |
|---|---|
| `canonical.py` | span kind 对照表 + `FIELD_ALIASES`（规范键 -> 属性路径） |
| `normalize.py` | `canon()`、`span_kind()`、`to_messages()`、`friendly_name()` |
| `visibility.py` | 管道型 span / 噪声属性的过滤 |
| `naming/` | 各框架的 span 名称翻译规则 |

## 监控你自己的 Agent

四种入口，从「什么都不用改」到「我要完全掌控」。四者写出的都是同一个
`latest_traces.jsonl`，也都由同一个 viewer 读取：

| # | 你的诉求 | 命令 | 是否改代码 | root span |
|---|---|---|---|---|
| A | 零代码改动 | `OTEL_PYTHON_DISTRO=agent-monitor opentelemetry-instrument python run.py` | 不改 | 无 —— 框架的每个顶层 run 各成一条 trace |
| B | 一条命令 | `python -m agent_monitor run run.py` | 不改 | 有 —— 每次运行一个 `AGENT` span |
| C | 一条命令，但框架自己已经产生 root | `python -m agent_monitor run --no-root-span run.py` | 不改 | 无 —— 用你框架自己的 root |
| D | 最精细的控制 | `python -m agent_monitor init`，然后手改 `instrument.py` | 改 1 个文件 | 有，且名字由你定 |

下面的 1-4 步讲的是 **D**（以及每条路都需要的安装步骤）。**A**、**B**、**C**
见[免改代码的入口](#免改代码的入口)。

`monitor()` 是可重入的，所以去包一个自己也调了 `monitor()` 的脚本是安全的：内层
会发现 provider 已经活着，于是退化成一个空操作，而不是去抢「一个进程只允许有一个」
的全局 provider。因此 B、C 包住已有的 `instrument.py` 式脚本没问题，A 包住直接调用
`monitor()` 的脚本也没问题。

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

生成的文件里已经带了一个 root span，所以「一次运行 = 一条 trace」。你只需改两处：

1. `ROOT_SPAN`（以及 `SERVICE_NAME`）—— `ROOT_SPAN` 就是 viewer 里 trace 下拉框
   显示的名字，请改成你的业务名。**不要**用 `run` / `agent` / `task` / `step` /
   `chain` 收尾：viewer 会把它们当通用后缀剥掉，标签会退化成一个词。
2. `from run import main` 那一行 —— 指向你自己的 Agent 入口。

这个 import 要放在 `monitor()` 内（让 OpenInference 的 monkey-patch 在你的框架
构造对象之前就生效）、但放在 root span 之外（import 耗时不算作 Agent 运行时间）。
如果被导入的模块在导入过程中就会产生 span，它们会各自成为独立 trace —— 所以请让
它保持「导入无副作用」。

如果 `instrument.py` 你已经改过，请**保留它、不要用新生成的覆盖**，改用与框架匹配
的组合 extras 去更新它的依赖。

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

# 断言「一次 agent 运行 = 一棵 trace 树」，而不是一堆孤儿
python -m agent_monitor verify --trace-file latest_traces.jsonl --max-traces 1
```

`--min-traces` 回答的是「到底有没有导出东西」。它没法告诉你这次运行有没有散架 ——
因为散架的运行只会让 trace 数变**多**，不会变少。`--max-traces 1` 才能，导出里出现
多棵树时它返回 1。

## 免改代码的入口

上面表格里的 **A**、**B**、**C** 三条路都不需要 `instrument.py`，唯一的前置条件
就是第 1 步（安装）。

### B / C —— `python -m agent_monitor run`

```bash
# 给整次运行包一个 AGENT root span，名字默认取脚本文件名
python -m agent_monitor run run.py

# 自己指定 root span 名（viewer 下拉框里显示的就是它）
python -m agent_monitor run --root-span "Support Triage" run.py

# 你的框架自己已经产生 root（FastAPI / Celery / LangGraph）：
# 关掉我们这层，否则会出现双层根
python -m agent_monitor run --no-root-span run.py

# 脚本路径之后的所有参数都会原样转发给脚本
python -m agent_monitor run run.py --query hello --top-k 3
```

| 参数 | 默认值 | 作用 |
|---|---|---|
| `--root-span NAME` | 脚本文件名（不含扩展名） | 那个唯一 `AGENT` root span 的名字 |
| `--no-root-span` | 开启 root span | 让脚本自己框架产生的 span 当根 |
| `--no-thread-context` | 开启 context 传播 | 不再把 trace context 复制进 `ThreadPoolExecutor` / `threading.Thread` 的任务 |
| `--auto-detect` / `--no-auto-detect` | 开启 | 开 = 只激活框架可导入的 instrumentor；关 = 尝试所有已安装的 instrumentor |
| `--instrumentors LIST` | 不限制 | 逗号分隔的插桩器白名单（如 `langchain` 或 `openai,anthropic`）。用在 langchain-openai 应用上只留 `langchain`，就能去掉每次 LLM 调用重复出现的 `ChatCompletion` span。等价环境变量：`AGENT_MONITOR_INSTRUMENTORS` |
| `--service-name NAME` | 脚本文件名（不含扩展名） | OTel resource 上的 `service.name` |
| `--trace-file PATH` | `latest_traces.jsonl` | JSONL 写到哪 |
| `--exporter jsonl\|console` | `jsonl` | `console` 改为把 span 打到 stdout |

**所有参数都必须写在脚本路径之前。** `script_args` 用的是 `argparse.REMAINDER`，
所以写在脚本名之后的东西会原样交给脚本，我们这边根本不会去解析：

```bash
python -m agent_monitor run --root-span X run.py    # 对
python -m agent_monitor run run.py --root-span X    # --root-span X 进了 run.py
```

root span 就是「一次运行 = 一条 trace」的原因：OpenInference 对一个没有父 run 的
框架顶层 run 会传 `parent_context=None`，于是 SDK 回落到当前 context，把我们的
span 认作父节点。异常不会被吞掉 —— root span 会被标成 `ERROR`，traceback 照原样
往上抛。

### 为什么一次运行会出现很多条 trace？

trace 不是容器，它是**一棵树**：每个没有父节点的 span 都是自己那棵树的根。所以
「184 个 span、56 条 trace」的意思是 56 棵树，而不是一棵树里的 56 个分组。

最常见的原因是线程边界。OpenTelemetry 把「当前 span」存在一个
`contextvars.ContextVar` 里，而标准库的线程原语不复制它：
`ThreadPoolExecutor.submit()` 把可调用对象交给一个长寿命的 worker 线程，用的是
**worker 自己的**（空）context；`threading.Thread.start()` 则开一个全新的 context。
于是 agent 只要往线程上分发任务，每个任务就各自成为一条 trace —— root span 注入得
再仔细也没用，因为它根本到不了 worker。

所以 `monitor()` 默认会把这两处都打上补丁，按任务粒度做 `copy_context().run(...)`
—— 和 `langchain_core` 的 `ContextThreadPoolExecutor` 完全同一套做法。
`Executor.map()` 与 `loop.run_in_executor()` 都走 `submit()`，因此一并覆盖；
`asyncio` 的 Task 本来就原生复制 context，不需要处理。如果它和你自己的补丁冲突，
可以用 `--no-thread-context`（B/C 路线）或 `AGENT_MONITOR_THREAD_CONTEXT=0`
（任何路线）关掉。

如果运行仍然散架，`run` 会在 stderr 上说明，并把孤儿根列出来：

```text
[run] warning: this run produced 4 separate traces (12 spans), not one.
[run]   expected root 'fanout_root', found 3 orphan root(s):
[run]     - 'sub_task' (TOOL) trace 3f2a9c11
[run]   Orphan roots mean trace context was lost. Usual causes:
[run]     * a thread or pool worker started before monitoring was active;
[run]     * multiprocessing / Celery -- contextvars cannot cross processes;
[run]     * --no-thread-context, or AGENT_MONITOR_THREAD_CONTEXT=0.
```

`opentelemetry-instrumentation-threading` **不能**替代它。那个包只 patch
`threading.Thread`，而且是在线程**创建时**抓 context —— 对线程池来说这个粒度是错的：
worker 只创建一次然后反复复用，于是所有任务都会继承「第一个提交者」的 context
（如果池是在 import 期建的，继承到的就是空的）。

### A —— 零代码，走 OpenTelemetry distro

```bash
OTEL_PYTHON_DISTRO=agent-monitor opentelemetry-instrument python run.py
```

`opentelemetry-instrument` 会注入一个 `sitecustomize`，其中调用
`auto_instrumentation.initialize()`，而它会去加载 `OTEL_PYTHON_DISTRO` 指定的
distro。我们的 distro（`agent_monitor/distro.py`）把 JSONL exporter 装成整个进程的
后端，并把这个上下文一直持有到进程退出 —— 所以在你的脚本执行第一行之前，tracing
就已经生效了。这一层没有 CLI 钩子，配置只能走环境变量：

| 环境变量 | 默认值 |
|---|---|
| `AGENT_MONITOR_TRACE_FILE` | `latest_traces.jsonl`，相对于当前工作目录 |
| `AGENT_MONITOR_SERVICE_NAME` | 先取 `OTEL_SERVICE_NAME`，再退到当前目录名 |
| `AGENT_MONITOR_EXPORTER` | `jsonl`（`console` 也可用） |
| `AGENT_MONITOR_VERBOSE` | 未设置；设为 `1` 会把解析后的配置打到 stderr |
| `AGENT_MONITOR_THREAD_CONTEXT` | 开启；`0` / `false` / `no` / `off` 关闭线程 context 传播 |

两个注意点：

- **没有 root span。** 这一层没法包住你的 `main()`，所以框架的每个顶层 run 各自成为
  一条 trace，viewer 里一次运行会列出好几行。需要「一次运行一条 trace」请用 B 或 D。
  线程 context 传播在这一层依然生效，所以那几行各自都是**完整的一棵树**，而不是一棵树
  被切碎后的碎片。
- **入口点是从已安装的 `dist-info` 读的，不是从源码树读的。** 改完 `pyproject.toml`
  必须重装（`pip install -e .`）；否则 `_load_distro()` 找不到 `agent-monitor`，会
  静默回落到什么都不配置的 `DefaultDistro`。

`opentelemetry-instrument` 加载的是环境里**所有**的 `opentelemetry_instrumentor`
入口点，不只是 OpenInference 的那些。不想要的可以排除掉：

```bash
OTEL_PYTHON_DISABLED_INSTRUMENTATIONS=requests,urllib3 \
OTEL_PYTHON_DISTRO=agent-monitor opentelemetry-instrument python run.py
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
- 两者取交集，作为候选 `instrumentors`；之后若设了
  `AGENT_MONITOR_INSTRUMENTORS`，还会再取一次交集（见上文的插桩器白名单）

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
| `instrumentors` | list[str] | `None` | 显式的 instrumentor 名称白名单。注意它同时会被 `AGENT_MONITOR_INSTRUMENTORS`（逗号分隔）**进一步收窄** |
| `exporter` | str 或 SpanExporter | `None` | `"jsonl"`、`"console"`，或一个 SpanExporter 实例 |
| `trace_file` | str/Path | `"latest_traces.jsonl"` | exporter 为 jsonl 时的输出路径 |
| `thread_context` | bool 或 None | `None` | 是否把 trace context 复制进 `ThreadPoolExecutor` / `threading.Thread` 的任务；`None` 表示读 `AGENT_MONITOR_THREAD_CONTEXT`，除非它是 `0`/`false`/`no`/`off`，否则为开 |
| `verbose` | bool | `False` | 是否打印实际激活了哪些 instrumentor |

`monitor()` 是可重入的。嵌套调用是安全的：最外层持有 provider、processor 与
instrumentor，内层只是把深度计数加一、并 yield 出同一个 tracer。内层如果传了不同的
`service_name` / `trace_file` / `exporter`，会往 stderr 打一行告警，然后被忽略 ——
一个进程只有一个全局 TracerProvider，所以只有最外层能决定 span 写到哪。清理动作只在
深度归零时执行。

**先后**两次调用 `monitor()` 则是另一回事：OpenTelemetry 一个进程只接受一次
`set_tracer_provider()`，所以第二个块拿不到自己的 provider —— 它的 span 会继续写进
第一个块的文件、它自己的文件是空的，同时会打一行告警说明这一点。请改成嵌套，或者整个
进程只用一个 `monitor()`（`python -m agent_monitor run` 就是这么做的）。


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

- **活动图布局（"B"）**：一张 UML 活动图风格的树（左）/ span 详情（右）。
  整个数据源被画成一棵树，以 trace 的 root span 为根 —— `▶` 起点、`■` 终点、
  圆角矩形是活动、**双线框是折叠的 `×N` 组**、六边形是并行分支与汇聚 —— 于是
  100+ span 的运行也能完整显示，不会再出现「节点数过多」。
- **同构子树默认折叠**：`Σ重数 == span 数` 保证没有任何 span 被藏起来，只是不再
  逐个画 N 遍。图上方「展开全部 span」可切回全量；点某个 `×N` 节点只展开那一组，
  此时会出现「收起全部」按钮。
- **点击活动图里的节点**即可选中对应 span（点 `×N` 组则是选中代表 span 并展开该组），
  且不会触发整页刷新（一个双向的 Streamlit 组件会把 span id 回传）。同时支持
  `?focus=<span_id>` 深链。
- **成本估算**用的是 `viewer_app/config.py` 里的静态 `_COST_PER_1K` 表；表中
  没有的 (provider, model) 组合就直接不显示成本。
- **Feedback 标签页**目前是占位实现 —— SDK 尚未记录反馈分数，但如果 span 属性
  里存在 `feedback` / `feedback.score`，仍会渲染出来。

## 测试

```bash
pip install -e ".[viewer,test]"
python -m pytest            # 166 个测试，收集范围由 pyproject.toml 限定在 tests/
```

测试覆盖：schema 迁移、JSONL 导出器的截断语义、框架自动探测、CLI 的 `init`
脚手架、`monitor()` 的可重入性、线程边界的 context 传播、`verify` 的 trace 树校验、
`run` 的 root span 与零代码 distro（均在子进程里做端到端验证）、插桩器白名单的解析
与收窄、活动图的折叠不变量（`Σ重数 == span 数`）、`viewer/` 的归一化与命名，以及
针对 viewer 的源码级回归断言。

## 已知限制

- span 级别的成本是静态查表，不是各 provider 的实时价格。
- `trace_renderer.build_span_tree()` 在传入空 span 列表时会抛异常（viewer
  不会以空列表调用它）。
- 仓库根目录仍保留了若干依赖具体环境的临时脚本（`test_app.py`、
  `test_detail.py`、`smoke_test.py`），其中写死了本机路径。它们已被排除在
  pytest 收集范围之外，但不具备可移植性。
- OpenTelemetry 一个进程只接受一次 `set_tracer_provider()`。因此**先后**两个
  `monitor()` 块没法各写一个文件 —— 第二个块会继续导出到第一个块的文件里，并在
  stderr 上告警。请改成嵌套（嵌套调用是空操作），或者整个进程只用一个 `monitor()`。
- `run` 的所有参数都必须写在脚本路径之前：`script_args` 用的是
  `argparse.REMAINDER`，写在脚本名之后的东西会被转发给脚本，而不是被解析。
- 线程 context 传播止步于进程边界。`contextvars` 无法跨进 `multiprocessing` 子进程
  或 Celery worker，所以那些地方仍会各自开一条 trace；要做到需要往子进程环境里注入
  `TRACEPARENT`，本次没有实现。
- 加了 `--no-thread-context`（或 `AGENT_MONITOR_THREAD_CONTEXT=0`）就回到旧行为：
  丢给线程池的每个任务各成一条孤儿 trace。此时 `run` 只会在 stderr 上告警，不会失败。
- 丢进池子的任务可能在提交方的 span 已经结束之后就才开始跑。OpenTelemetry 接受这种
  情况 —— `trace_id` 共享、`parent_span_id` 照记 —— 但 viewer 里的时间轴看起来可能
  是反的。
- JSONL 的并发写只在**进程内**串行化。`JsonlFileExporter` 现在把每批 span 以一次
  二进制追加 `write()` 写出，并持有进程级锁，因此线程池扇出不会再把一条记录
  写成两行、也不会整条丢掉。两个**进程**同时导出到同一个文件仍然不安全——请给
  每个进程单独的 `--trace-file`。
