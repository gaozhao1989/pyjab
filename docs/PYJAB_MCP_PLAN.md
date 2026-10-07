# pyjab-mcp 完整计划

> 配套文档：`docs/TRIAGE.md`（问题分诊）、`docs/ROADMAP.md`（长期路线图）
> 前置依赖：**阶段 0 与阶段 1 必须先完成**。pyjab-mcp 的质量上限完全由 pyjab 的 DLL 定位、遍历性能和 DPI 正确性决定。

---

## 1. 产品定义

### 一句话

> **一个 MCP server，让 AI agent 直接操作 Java 桌面应用——不需要目标应用提供任何 API，也不需要修改它的启动方式。**

### 目标用户（按优先级）

| 优先级 | 用户 | 场景 | 为什么选 pyjab |
|---|---|---|---|
| P0 | 个人自动化者 / 测试工程师 | 公司内网有个老 Java 客户端，要批量录入或回归测试 | 没有 API，只能走 UI 自动化 |
| P0 | AI agent 使用者 | 想让 Claude/Cursor 帮忙操作一个 Java 工具 | MCP 是 2026 年最自然的接入方式 |
| P1 | 企业 RPA / 测试团队 | 银行/保险/电信的老 Swing 后台 | **不改目标应用**是关键——生产系统启动参数动不了 |
| P2 | Agent 框架开发者 | 需要"操作 Java 桌面"作为一个 capability | 有 Python 库可直接集成 |

### 不做的事（明确边界）

- 不做通用 Windows 自动化（那是 `FlaUI-MCP` 的地盘，见第 2 节）
- 不做视觉/像素方案（没有护城河）
- 不做 Web/浏览器自动化
- 不支持 canvas 手绘 UI、浏览器内嵌 Java、Applet（JAB 本身的限制）

---

## 2. 竞争分析：这个空位是真实的吗？

### 2.1 数据

拉取了 GitHub 上所有相关的 MCP server（按 star 排序）：

**通用 Windows 桌面自动化 —— 已经很拥挤**

| 项目 | Star | 创建 | 技术路线 |
|---|---|---|---|
| `shanselman/FlaUI-MCP` | **103** | 2026-02 | FlaUI + UIA |
| `sandraschi/windows-computer-use-mcp` | 41 | 2025-07 | 22 个工具的 Windows computer use |
| `manushi4/Screenhand` | 15 | 2026-03 | 通用桌面 |
| `deploymenttheory/windows-mcp-server` | 6 | 2026-07 | 通用 |
| `ilyafainberg/TotalControl-MCP-Server` | 5 | 2026-06 | 硬件级控制 |
| `trsdn/mcp-server-uiautomation` | 4 | 2026-03 | UIA |
| 其他 | 0–3 | 2026 | 至少 6 个 |

**Java / Swing 专属 —— 几乎是空的**

| 项目 | Star | 创建 | 技术路线 |
|---|---|---|---|
| `crosstech-solutions-bv/swing-mcp` | **2** | 2026-07 | Java agent 注入（需改启动参数） |
| `burnedpreadator/java-autopilot` | 1 | 2026-05 | 未见实现 |
| **pyjab-mcp** | — | — | **JAB 外部桥接（不改目标应用）** |

### 2.2 结论

**空位是真实的，但有时间窗。**

- 通用方案已经进入"知名开发者 + 100 star"阶段（`FlaUI-MCP` 的作者是 Scott Hanselman），说明品类在教育市场层面已经打开
- 但所有通用方案走 UIA。Java 应用要通过 **JAB → MSAA → UIA** 两次桥接才能被看到，**表格、文本、选择、role/states 的 Java 语义会丢失**
- Java 专属方案只有 1–2 个 star，且 `swing-mcp` 走的是 agent 注入路线，**需要改目标应用的启动参数**——在企业环境里这条路常常走不通

**pyjab 的生态位**：语义深度接近注入方案，但**不需要改目标应用**。

**时间窗估计 6–12 个月。** 一旦某个通用方案把"支持 Java"当 feature 加进去，或者 swing-mcp 积累起用户，这个位置就没了。**阶段 2 不能拖到 12 个月之后。**

### 2.3 ⚠️ 必须先验证的假设（M0 里程碑，go/no-go）

> **前提假设：在真实 Java 应用上，pyjab 的 JAB 直连明显优于 FlaUI-MCP 的 UIA 桥接。**

**这个假设目前没有任何证据。** 如果它不成立，整个 pyjab-mcp 方向的价值大幅下降，资源应该转向第 1 层（把库本身做好）。

**验证方法（预计 3–5 小时 + 一个云 Windows 实例）**

1. 准备 3 个代表性目标（用第 6 节的自建测试应用即可）：
   - T1：JDK 8 的 Swing 应用，含登录表单
   - T2：JDK 17 的应用，含大型 `JTable`
   - T3：含树、标签页、弹出对话框的应用
2. 分别用 `FlaUI-MCP` 和 `pyjab` 尝试：
   - 枚举窗口
   - 找到"登录"按钮
   - 读取表格第 3 行第 2 列的值
   - 读取单个元素的 role / states
3. **判定标准**

| 结果 | 决策 |
|---|---|
| pyjab 在表格/文本/语义上**明显更优**（例如 UIA 读不到表格单元格，pyjab 能） | ✅ 继续，这是核心卖点 |
| 两者**差别不大** | ⚠️ 降级：pyjab-mcp 仍可做，但定位改为"另一个可选后端"，不投入市场精力 |
| UIA **更好** | ❌ 停止 MCP 方向，资源全部转向第 1 层维护与第 3 层支持服务 |

**这一步必须在写任何 MCP 代码之前做。** 它是整份计划里唯一的高风险假设。

---

## 3. 架构设计

### 3.1 进程模型

```
┌──────────────────────────────┐
│ MCP Client                   │
│ (Claude Desktop / Code /     │
│  Cursor / 其他 host)          │
└───────────┬──────────────────┘
            │ stdio (JSON-RPC)
            ▼
┌──────────────────────────────┐
│ pyjab-mcp                    │
│  ├─ FastMCP 工具层 (async)    │
│  ├─ 句柄表 HandleTable (LRU)  │
│  ├─ 快照渲染器 (令牌预算)      │
│  └─ JAB 执行线程 (阻塞调用)    │
└───────────┬──────────────────┘
            │ ctypes / JAB DLL
            ▼
┌──────────────────────────────┐
│ 目标 Java 应用 (Swing/JavaFX) │
└──────────────────────────────┘
```

- **单进程 stdio**：MCP 本地工具的标准形态，用户配置里一行命令即可启动
- **必须运行在目标 Java 应用所在的 Windows 机器上**（JAB 是进程间通信，不能跨机器）

### 3.2 无状态协议 + 有状态世界：句柄表设计（核心）

MCP 规范 **2026-07-28** 做了重大改动：**移除了协议级 session 和 `initialize` 握手**，服务器需要跨调用状态时，应当 **"server-minted handles passed as ordinary tool arguments"**。

桌面自动化天然有状态（你得记住"用户上一次拿到的那个按钮"）。这正好与规范的指引吻合。

**设计**

```python
# 元素句柄：短、不透明、人类可读
"e:7f3a"   # 前缀固定，后缀 4-6 位十六进制

# 工具调用示例
java_click(handle="e:7f3a")
java_set_text(handle="e:91c2", text="admin")
```

**句柄表规则**

| 规则 | 值 | 理由 |
|---|---|---|
| 容量上限 | 256 个元素（可配） | 有界，防止无限增长 |
| 淘汰策略 | LRU | 最久未用的先释放 |
| 淘汰动作 | 调用 `release_jabelement()` | **顺带解决 issue #43 的资源泄漏** |
| 会话 TTL | 30 分钟无活动自动释放全部句柄 | 防止 agent 崩溃后泄漏 |
| 显式释放 | `java_release(handles=[...])` 或 session 结束 | |

**这个设计顺带修掉了一个老问题**：现在 pyjab 靠用户手动调用 `release_jabelement()`，issue #43「跑一小时就卡死」正是漏释放导致的。句柄表把**所有权集中到一个地方**，释放变成框架的责任而不是用户的责任。**这是 MCP 层反过来改善库本身的典型例子。**

### 3.3 令牌预算：最重要的设计约束

**问题**：一个 Java 应用的完整可访问性树可能有几千个节点，每个节点有 12+ 个属性。

- 全量遍历要 **40 秒**（issue #33 的原始抱怨）
- 全量返回会把**几十万 token** 塞进模型上下文，直接导致不可用

**设计原则：永不返回整棵树，只返回"有界视图"。**

```
java_snapshot(depth=2, max_nodes=120, only_interactive=True, fields=["name","role","states"])
```

**返回格式**（紧凑单行 / 节点，而不是 JSON 嵌套结构）

```
[e:7f3a] window "Java Control Panel"
  [e:7f3b] root pane
    [e:8a01] panel "Update"
      [e:8a02] push button "Update Now" (enabled,visible)
      [e:8a03] check box "Check for updates automatically" (checked)
    [e:8a11] panel "Temporary Files"
      [e:8a12] text "C:\Users\...\Temp" 
      [e:8a13] push button "Settings..." (enabled)
      [e:8a14] push button "Delete Files..." (enabled)
...
truncated: true (120/1,847 nodes) — 用 depth/max_nodes/only_interactive 收窄，或对某个 handle 再 snapshot
```

**预算控制**

| 机制 | 默认 | 说明 |
|---|---|---|
| `depth` | 2 | 限制递归深度 |
| `max_nodes` | 120 | 硬上限，超出即截断 |
| `only_interactive` | true | 只返回可交互/可见节点，过滤掉纯容器噪声 |
| `fields` | `["name","role","states"]` | 按需扩展（`bounds`/`description`/`text` 等），不默认返回 |
| 截断提示 | 必须 | 明确告诉 agent"被截断了"以及**如何收窄**，否则 agent 会以为树就这么大 |

**Token 估算**：每个节点约 30–50 tokens → 120 节点 ≈ **4–6k tokens**。
**设计目标：单次快照 < 4k tokens。** 这个预算要作为硬性验收标准写进测试。

**渲染层与 JAB 层分离**：`snapshot` 的遍历在 Python 侧完成，**遇到 `max_nodes` 立即停止遍历**（不要先遍历完再截断）。这让 MCP 场景下的延迟也同时受益——**这也是为什么 P1-1（遍历剪枝）必须在阶段 1 完成**。

### 3.4 工具面设计

**原则：不要把 pyjab 的 60+ 个方法直接映射成 60+ 个工具。** 工具过多会显著稀释模型的选择准确率。

设计为 **14 个工具**，覆盖完整工作流：

#### 环境与诊断

| 工具 | 注解 | 说明 |
|---|---|---|
| `java_diagnostics` | `readOnly` | 自检：JAB 是否已启用、DLL 路径与版本、JDK 版本、位数匹配。**这个工具直接解决阶段 0 的安装问题**——用户第一次接入 MCP 就能看到环境哪里不对 |

#### 会话管理

| 工具 | 注解 | 说明 |
|---|---|---|
| `java_list_windows` | `readOnly` | 列出当前所有 Java 窗口（title / hwnd / pid / vmid） |
| `java_attach_window` | — | 绑定到指定窗口，返回 `session_id` |

#### 观察与读取

| 工具 | 注解 | 说明 |
|---|---|---|
| `java_snapshot` | `readOnly` | **核心工具**。有界快照，返回带句柄的树视图（见 3.3） |
| `java_find` | `readOnly` | 按 `name` / `role` / `description` / `states` / `xpath` 查找，返回句柄列表（支持正则） |
| `java_get_element` | `readOnly` | 取单元素详情（`fields` 可控） |
| `java_get_text` | `readOnly` | 取文本内容（`AccessibleText`，支持取子串/范围） |
| `java_get_table` | `readOnly` | **差异化能力**。读表格：行列数 + 单元格值，支持分页（`row_start` / `row_count`） |
| `java_screenshot` | `readOnly` | 截图，返回图片内容块 |

#### 操作

| 工具 | 注解 | 说明 |
|---|---|---|
| `java_click` | `destructive` | 点击，支持 `left` / `right` / `double`，含 `simulate` 策略选择 |
| `java_set_text` | `destructive` | 输入文本 |
| `java_select` | `destructive` | 选择（combo / list / tab / 表格单元格） |
| `java_send_keys` | `destructive` | 发送快捷键（如 `alt+y`） |
| `java_fill_form` | `destructive` | **工作流级工具**：批量 `[{handle, value}]` 一次填完，减少往返 |

#### 同步

| 工具 | 注解 | 说明 |
|---|---|---|
| `java_wait_for` | `readOnly` | 等待条件：元素出现 / 文本变化 / 新窗口出现。**对应 issue #56 和 #74** |

**设计要点**

1. **`java_fill_form` 是"工作流工具"而非 API 包装**——一个 8 字段的登录表单，如果用 `java_set_text` 要 8 次往返，每次都要带上下文。批量工具显著降低延迟和 token 消耗。
2. **每个工具的 docstring 必须包含**：何时用、何时不用、返回结构、错误处理。这是 MCP 工具设计的基本要求，直接影响模型的调用准确率。
3. **错误信息要可操作**。不要返回 `JABException: element not found`，要返回 `"未找到 name='登录' 的元素。当前窗口有 3 个 push button：'确定'、'取消'、'登录(O)'。提示：用 java_find(name='登录.*') 或检查是否需要先切换窗口。"`

### 3.5 异步、线程模型与 Windows 消息泵（最高技术风险）

这一节有两个**互相关联**的硬要求，是本计划里最容易踩坑的地方。

#### 要求 1 — JAB 调用必须离开 asyncio 事件循环

MCP Python SDK 的工具是 `async def`，但 **JAB 调用是阻塞的跨进程 ctypes 调用**（一次树遍历可能几秒到几十秒）。

**必须把 JAB 调用放到专用线程池执行，绝不能阻塞 asyncio 事件循环。** 否则：

- 一个慢查询会让整个 MCP server 无响应
- 客户端超时后重试，造成调用堆积

```python
async def java_snapshot(...):
    return await asyncio.get_running_loop().run_in_executor(
        _jab_executor,     # 单线程 executor（见下方说明）
        _snapshot_sync, ...
    )
```

**用单线程 executor**：JAB 的 `CDLL` 句柄和 Java 对象引用不是线程安全的，跨线程使用可能崩溃。

> ⚠️ **一个必须纠正的误解**：`pyjab/common/actor_scheduler.py` **不是线程池**。
> 它名为 "ActorScheduler"，注释也写着 "run generator functions as thread"，但实现是**纯协作式的生成器调度器**——`run_actor()` 只是在一个 `while` 循环里同步调用 `actor.send()`，**不创建任何真实线程**。
> 因此它**不能**用来解决"不要阻塞事件循环"的问题。pyjab-mcp 必须自己引入真正的 `ThreadPoolExecutor(max_workers=1)`。
> 另外它被 `@singleton` 装饰，是**全局共享状态**，在长期存活的 MCP server 中多会话场景下有状态污染风险。

#### 要求 2 — 必须持续运行 Windows 消息泵（且 pyjab 当前做不到）

JAB 的许多能力依赖 Windows 消息循环。`win32utils.py` 的注释写得很明白：

> "Must be invoked before call JAB APIs, otherwise the JAB APIs will not work."

**但 pyjab 三个版本里没有任何一个实现了"持续运行"的消息泵**（完整分析见 `docs/TRIAGE.md` 第 3.9 节）：

1. `_run_actor_sched()` 只注册一个 actor，而 `ActorScheduler.run_actor()` 的循环是 `while self.deque:` → **每次调用只把泵推进一个 `yield`（约 200ms 一个切片）**
2. v1.1.7 靠"在窗口等待循环中反复调用 `_run_actor_sched()`"来补偿这一点；**HEAD 把这个补偿删掉了**，只在 `init_jab()` 里调用一次
3. HEAD 还把内核事件的创建移进了 `setup_msg_pump()` 函数体，且全包没有 `CloseHandle` → 每次 `JABDriver()` 泄漏 2 个句柄（v1.1.7 在类体中创建，配合 `@singleton`，不泄漏）

**这对 pyjab-mcp 是致命的前置依赖**：MCP server 是**长期存活**的进程，必须能随时响应"新窗口出现""对话框弹出"。短命的测试脚本靠"用之前把泵推一下"勉强能工作，但长驻 server 必须有一个真正持续运行的消息泵。**不要试图复用 pyjab 现有的 `ActorScheduler` 机制**——它是生成器滴灌，不是线程。

**架构含义**

```
┌─────────────────────────────────────────┐
│ pyjab-mcp 主线程：asyncio 事件循环        │
│   （FastMCP、工具分发、句柄表）            │
└──────────────┬──────────────────────────┘
               │ 任务投递
               ▼
┌─────────────────────────────────────────┐
│ JAB 工作线程（单线程 executor）           │
│   ├─ JAB API 调用                        │
│   └─ ★ 持续运行的 Windows 消息泵          │
│      MsgWaitForMultipleObjects 循环      │
│      （正确实现，含事件句柄回收）          │
└─────────────────────────────────────────┘
```

**因此 P1-0（消息泵重构）是 M2 的硬前置条件**，不能跳过。
具体做法建议：

- 消息泵在一个**真实线程**里跑 `while` 循环（不要用生成器滴灌）
- 只在该线程内调用 JAB API，保证线程亲和性
- 用 `threading.Event` 或 `CloseHandle` 正确实现停止与句柄回收
- 主线程通过 `asyncio.run_in_executor` + `queue` 与该线程通信

#### 其他需要早测的点

MCP server 作为 stdio 子进程运行时**没有 GUI 会话亲和性**，某些依赖窗口消息或前台状态的操作（如 `SetForegroundWindow`，issue #68）可能失败。这个问题应在 **M1** 阶段就用最小例子验证，失败的操作要在工具 docstring 里明确标注限制。

### 3.6 协议版本策略

- **规范最新版**：2026-07-28（无状态化、去 `initialize`、`server/discover`、MRTR、`resultType` 必填、可缓存结果带 `ttlMs`/`cacheScope`）
- **风险**：Python SDK 未必已跟进最新协议版本

**策略**

1. **编码目标用 SDK 实际支持最广的稳定协议版本**，不要为了最新版牺牲兼容性
2. **但架构按无状态设计**（句柄表 + 显式 session_id 参数），这样切版本几乎零成本——因为 2026-07-28 的核心变化恰好就是"去 session、用 server-minted handles"
3. 实现 `server/discover`（如果 SDK 支持），让客户端能做版本协商
4. `tools/list` 返回**确定性顺序**（规范 SHOULD），以提高客户端 prompt cache 命中率

---

## 4. 技术选型

| 项 | 选择 | 理由 |
|---|---|---|
| 语言 | Python ≥ 3.10 | 必须复用 pyjab |
| MCP SDK | 官方 `mcp`（FastMCP） | 官方推荐，装饰器式工具注册 |
| 输入校验 | Pydantic v2 | FastMCP 原生集成，`ConfigDict` + `Field` |
| 传输 | stdio（默认）；后续可选 streamable HTTP | 本地工具标准形态 |
| 打包 | `pyproject.toml`，entry point `pyjab-mcp` | 现代化，替代 pyjab 的 `setup.py` |
| 测试 | pytest + pytest-asyncio + 一个自建 Swing 测试应用 | 见第 6 节 |
| 许可 | **MIT / Apache-2.0**（若 pyjab 能改 LGPL）；否则 GPLv2 | 见 ROADMAP 第 5 节 |

**Server 命名**（遵循 MCP 约定 `{service}_mcp`）：`pyjab_mcp`
**PyPI 包名**：`pyjab-mcp`
**Registry 命名空间**：`io.github.gaozhao1989/pyjab-mcp`

---

## 5. 里程碑与排期

按**每周 4–6 小时**估算。对应 ROADMAP 第 13–24 周。

| 里程碑 | 周 | 内容 | 交付物 | 预计工时 |
|---|---|---|---|---|
| **M0** | W13 | **JAB vs UIA 对比验证（go/no-go）** | 一份对比结论，决定是否继续 | 4–6 h |
| **M1** | W14 | 骨架：pyproject、FastMCP、`java_diagnostics`、`java_list_windows`、`java_attach_window`、**单线程 JAB executor + 持续运行的消息泵线程**（依赖 P1-0） | 能列出窗口并自检环境 | 8–10 h |
| **M2** | W15–16 | **句柄表 + 快照渲染器**（核心） | `java_snapshot` 可用，token 预算达标 | 10–14 h |
| **M3** | W17 | 查找与读取：`java_find`、`java_get_element`、`java_get_text` | 能读表单文本 | 5–7 h |
| **M4** | W18 | **`java_get_table`**（差异化能力） | 能读 `JTable` 全表 + 分页 | 5–7 h |
| **M5** | W19–20 | 操作：`java_click`、`java_set_text`、`java_select`、`java_send_keys`、`java_fill_form` | 能完成端到端填表流程 | 8–10 h |
| **M6** | W21 | `java_wait_for`、`java_screenshot`、错误信息打磨 | 对应 #56 / #74 | 4–6 h |
| **M7** | W22 | 测试：单测 + Windows CI 集成 + 端到端脚本 | CI 绿，E2E 通过 | 6–8 h |
| **M8** | W23 | 文档 + 打包 + `server.json` | README 含客户端配置片段 | 4–6 h |
| **M9** | W24 | **发布 pyjab-mcp 0.1.0** + 上官方 MCP Registry + 提交 aggregator | 可被用户安装发现 | 4–6 h |

**累计约 65–85 小时**，按每周 4–6 小时算约 **13–17 周**。与 ROADMAP 的阶段 2 对齐。

**关键路径**：**P1-0（消息泵重构）→ M0 → M1 → M2**。

- **P1-0** 是硬前置：没有持续运行的消息泵，M2 之后所有"响应新窗口/对话框"的能力都无法实现（见 3.5 节）
- **M0** 是决策点：决定是否继续整个方向
- **M2** 是技术难点：句柄表与令牌预算决定产品是否可用
- 其余里程碑为常规工作

---

## 6. 测试策略（针对"没有 Windows 机器"）

这是整个计划里最现实的问题。分三层：

### L1 — 纯逻辑单测（macOS 可跑，覆盖率目标最高）

把不依赖 JAB 的部分全部抽出来，在 Mac 上跑：

- 句柄表：LRU 淘汰、TTL 过期、释放调用被正确触发（用 mock）
- 快照渲染器：给定一棵假的可访问性树 → 断言输出格式、截断行为、token 估算
- **令牌预算测试**：断言 120 节点的快照渲染结果 < 4k tokens（用 tiktoken 或字符估算）
- 参数校验：Pydantic 边界
- 错误信息格式

**这一层能覆盖 M2 的大部分逻辑**，是性价比最高的测试投入。

### L2 — Windows CI 集成测试（GitHub Actions `windows-latest`，免费）

- 打包与安装：`pip install .` 成功、entry point 存在
- 导入与启动：server 能启动并响应 `tools/list`
- 环境探测：`java_diagnostics` 在无 JAB 环境下给出正确的错误信息（而不是崩溃）
- 需要 JDK：CI 里用 `actions/setup-java` 装 JDK 8 / 17 / 21 各跑一遍 DLL 探测逻辑

**不能覆盖**：真实 GUI 自动化（runner 无交互式桌面会话）。**不要指望这一层能验证 UI 操作。**

### L3 — 端到端（云 Windows 实例，按小时计费）

### ⭐ 关键资产：自建 Swing 测试应用 `pyjab-testapp`

**这是解决"无法复现"问题的根本手段。**

现在所有 issue 都依赖用户自己的私有 Java 应用，所以**没人能复现，包括作者**。自建一个覆盖全部已知问题场景的 Swing 应用，就把"无法复现"变成了"可回归测试"。

**建议内容**（每个组件对应一组历史 issue）：

| 组件 | 覆盖的 issue |
|---|---|
| 登录表单（文本框 + 密码 + 按钮 + 复选框） | #33 #75 基线流程 |
| 动态标题的多窗口 + 弹出对话框 | #19 #56 #74 |
| 大型 `JTable`（1000 行 × 8 列，带滚动条） | #20 #33 #57 #59 #61 |
| `JTree` | #54 #58 |
| `JTabbedPane`（含同名标签） | #63 |
| 带快捷键的按钮（`alt+y`）、右键菜单 | #23 #42 #53 |
| 字体/DPI 缩放声明开关 | #62 |
| 一个故意在 canvas 上绘制面板的窗口 | #73（验证"确实拿不到"这一预期行为） |

**这个应用本身是重要资产**：既用于 pyjab 的回归测试，也用于 pyjab-mcp 的 E2E，还可以作为 issue 复现环境。
**而且它很适合用 AI 生成**——一个纯 Swing demo，需求明确，是 AI 辅助开发的理想任务。预计 4–6 小时。

**E2E 脚本**：在云 Windows 实例上启动 `pyjab-testapp`，跑一个完整的 MCP 会话（列出窗口 → 快照 → 找到登录按钮 → 填表 → 点击 → 验证表格内容），断言全部成功。**每次改动后手工跑一遍，或做成半自动脚本。**

---

## 7. 分发策略

### 7.1 渠道

| 渠道 | 动作 | 优先级 |
|---|---|---|
| **PyPI** | 发布 `pyjab-mcp` 包 | P0 |
| **官方 MCP Registry** | `server.json` + GitHub 命名空间验证 + GitHub Actions 发布 | P0 |
| **LobeHub / PulseMCP / Smithery / mcp.so** | 提交收录（官方 Registry 会被这些 aggregator 定期拉取） | P0 |
| GitHub README | 含 Claude Desktop / Claude Code / Cursor 的配置片段 | P0 |
| `pyjab` 的 README | 加一节指向 pyjab-mcp | P1 |

### 7.2 官方 Registry 发布要点

- 元数据格式：`server.json`
- 命名规范：反向 DNS 形式，如 `io.github.gaozhao1989/pyjab-mcp`
- 命名空间验证：通过 GitHub 账号或 DNS 验证归属
- **Registry 目前是 preview 状态**，可能发生破坏性变更或数据重置
- Registry 只托管**元数据**，包本身仍在 PyPI
- 支持通过 GitHub Actions 发布

### 7.3 为什么 MCP 渠道特别适合你

MCP 生态的分发是**注册表式的、被动的**：用户和 agent host 主动搜索，aggregator 自动拉取。
**不需要发布 Product Hunt、不需要营销、不需要与人沟通。**
这正好匹配你想要的"装完即用、零推销"形态——也是我在上一轮建议优先做 pyjab-mcp 的核心原因。

---

## 8. 变现伏笔（不主动推销）

目标：**当有人想付钱时，你有地方收。**

| 伏笔 | 做法 | 什么时候做 |
|---|---|---|
| F1 | `java_diagnostics` 的输出里附一行"商业支持：<你的联系方式>" | M1 |
| F2 | README 增加 `Support` 章节：免费支持范围（GitHub issue）+ 商业支持（邮件） | M8 |
| F3 | PyPI 项目页标注许可证与商用条款说明 | M9 |
| F4 | **预留企业版能力缺口**：远程 streamable HTTP 传输、多会话管理、审计日志、批量执行、与 CI 集成 | 架构上预留，不实现 |
| F5 | 在 `pyjab-mcp` README 里明确"企业环境部署支持"可联系 | M8 |

**明确不做**：不在 MCP 工具里设付费墙、不做 license key、不做额度限制。
开源版必须是完整可用的——否则会直接杀死采用率，而采用率是唯一的资产。

**F4 的逻辑**：企业真正会付钱的是"多机部署 + 审计 + 与现有 CI/CD 集成"，个人用户完全不需要这些。把缺口留在架构上，需求出现时再实现。

---

## 9. 风险登记册

| ID | 风险 | 概率 | 影响 | 应对 |
|---|---|---|---|---|
| **M1** | **JAB 相对 UIA 无实质优势** | 中 | 极高 | **M0 专门验证，作为 go/no-go**。不成立则停止 MCP 方向 |
| **M2** | Python SDK 未跟进 2026-07-28 无状态规范 | 高 | 中 | 以 SDK 支持版本为编码目标，架构按无状态设计，切版本成本低 |
| **M3** | 异步 + 阻塞 JAB 调用导致 server 假死 | 高 | 高 | 单线程 executor 隔离（3.5 节）；M1 就要建立这套结构 |
| **M3b** | **pyjab 没有任何版本实现持续运行的消息泵**，长驻 MCP server 无法响应新窗口/对话框 | **已确定存在**（三版本均如此） | 极高 | **P1-0 是硬前置**（`docs/TRIAGE.md` 3.9 节）。M1 必须实现独立线程中持续运行的消息泵，不能依赖 pyjab 现有的 `ActorScheduler`（它只做生成器滴灌） |
| **M3c** | 误用 `pyjab/common/actor_scheduler.py` 当线程池，导致阻塞事件循环 | 中 | 高 | 它不是线程池，是生成器调度器且是 `@singleton` 全局状态。pyjab-mcp 必须自建 `ThreadPoolExecutor(max_workers=1)` |
| **M4** | MCP server 作为子进程无 GUI 会话亲和性，部分操作失败 | 中 | 中 | M1 早测；失败的操作在 docstring 里明确标注限制 |
| **M5** | 句柄表引入新的泄漏/悬垂引用（元素已销毁但句柄还在） | 中 | 中 | 每次使用句柄前校验有效性；失效时返回明确的"句柄已失效，请重新 snapshot" |
| **M6** | 快照 token 超预算，实际不可用 | 中 | 高 | L1 层做硬性 token 断言，作为 CI 门禁 |
| **M7** | 没有真实企业 Java 应用可测，只靠自建 testapp | 高 | 中 | 自建 testapp 覆盖已知 issue 场景；主动邀请 issue 里的用户试用（#75/#76 的提问者就是现成测试者） |
| **M8** | 通用 UIA 方案把"Java 支持"变成 feature，窗口关闭 | 中 | 高 | 时间窗 6–12 个月；M9 必须在 W24 前完成 |
| **M9** | 无法验证 Windows 行为，发布即坏 | 高 | 高 | 阶段 1 必须先解决 Windows 环境（ROADMAP R1） |

---

## 10. 验收标准（0.1.0 发布条件）

- [ ] **M0 结论为"继续"**
- [ ] 能通过 MCP 完成端到端：列出窗口 → 快照 → 找到元素 → 填表 → 点击 → 读取表格结果
- [ ] 单次 `java_snapshot` token 消耗 **< 4k**（有自动化断言）
- [ ] `java_diagnostics` 在 3 种 JDK（8 / 17 / 21）下都能正确报告环境状态
- [ ] L1 单测覆盖句柄表与渲染器，CI 绿
- [ ] L2 Windows CI 在 `windows-latest` 通过（打包、安装、导入、`tools/list`）
- [ ] L3 在 `pyjab-testapp` 上跑通完整 E2E
- [ ] 发布到 PyPI + 官方 MCP Registry
- [ ] 被 ≥ 3 个 aggregator 收录
- [ ] README 含主流客户端的配置片段
- [ ] 文档明确写出能力边界（canvas / 内嵌浏览器 / Applet 不支持）

---

## 11. 下一步

**本周**：完成 **M0 验证**。这一步不需要写任何 MCP 代码，只需要：

1. 一个有 Windows 的环境（云实例，几小时）
2. `pyjab-testapp` 的最小版本（一个含表单和表格的 Swing 应用）
3. 同一批操作分别在 `FlaUI-MCP` 和 pyjab 上跑一遍，记录差异

**M0 的结论决定后面 12 周的资源投向。**

如果 M0 结论是"继续"，则 M1 从搭建骨架开始；
如果是"降级"，把阶段 2 的时间转投到 ROADMAP 的 P2 项与支持服务准备上。
