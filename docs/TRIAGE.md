# pyjab 问题清单与分诊

> 快照时间：本文档生成时的仓库状态（HEAD = `9460721`，最后提交 2023-05-06）
> 数据来源：GitHub Issues/PRs 全量拉取（15 个 open issue + 2 个 open PR + 55 个 closed issue + 23 个 PR）、PyPI 元数据与下载统计、`pypistats` 月度数据、源码静态分析。

---

## 0. 一句话结论

pyjab 的问题不是"功能不够"，而是**一个能用的东西被丢下了四年**：

- 2 个已经写好的修复 PR 挂在仓库里没人合（其中一个只有 6 行）
- GitHub HEAD 比 PyPI 上的 v1.1.7 领先 **35 个 commit / +9062 −3139 行**，从未发版
- 2024-01 之后的 5 个 issue/PR（#74 / #75 / #76 / PR #70 / PR #77）**一条回复都没有**（#71 除外，作者在 2024-02 有过回复）
- 而同期 PyPI 每月仍有 **2,000–4,000 次下载**

**此外，本次审计发现仓库里实际上有三个版本，且没有一个处于"可直接发布"的状态（见 3.9 节）**：

- **v1.1.7**（PyPI 上用户实际在跑的版本）：功能完整
- **HEAD**（35 个未发版 commit）：能编译，但相对 v1.1.7 引入了 **2 处回归**——删掉了消息泵的重复驱动逻辑，并把内核事件创建移入函数体导致每次 `JABDriver()` 泄漏 2 个句柄
- **工作区未提交的 WIP**（2023-05，`jabdriver.py` 改了 637 行）：**连导入都失败**——`win32utils.py` 有语法错误，`jabdriver.py` 调用了不存在的方法

**这很可能就是 2023 年停手的真正原因**：重构做到一半，代码已经跑不起来了。因此**发版前必须先决定基线并回补回归**，不能直接把 HEAD 或工作区发出去。

---

## 1. 现状数据

| 指标 | 数值 | 说明 |
|---|---|---|
| PyPI 近 30 天下载 | 2,206 | 日约 90 |
| PyPI 月度峰值 | 3,977（2026-07） | 说明需求在增长，不是衰减 |
| GitHub star / fork | 52 / 25 | **fork/star ≈ 48%**，远高于同类项目 |
| Open issue | 15 | 另有 2 个 open PR |
| 其中零评论 | **6 项**：4 个 issue（#54 / #74 / #75 / #76）+ 2 个 PR（#70 / #77） | 其中 5 项创建于 2024-01 之后 |
| PyPI 最后发版 | 2022-05-23（v1.1.7） | |
| GitHub 最后提交 | 2023-05-06 | |
| 未发版的 commit | 35（+9062 / −3139） | 含整个 `pyjab/jab/` 包重构 |

**为什么 fork/star 48% 是最重要的数字**：普通工具库的 fork 率通常在 10–20%，因为 fork 意味着"我要改它"。48% 说明大量用户不是收藏，而是**把源码拉下来改造后投入生产**。这类用户流失了不会再回来，但也意味着只要发一个能用的版本，他们会第一时间拉到。

---

## 2. 问题分类总览

15 个 open issue + 2 个 open PR，归为 8 类：

| 类别 | open 数 | 历史 closed 数 | 用户痛苦度 | 修复价值 |
|---|---|---|---|---|
| A 性能与遍历 | 4 | 5 | 🔴 极高 | 极高 |
| B 元素发现与定位 | 3 | 6 | 🔴 极高 | 极高 |
| C 交互保真度 | 2 | 6 | 🟠 高 | 高 |
| D 表格与选择 | 3 | 1 | 🟠 高 | 中 |
| E 安装与环境 | 0 (+2 PR) | 1 | 🔴 极高 | 极高 |
| F 平台能力边界 | 0 | 3 | 🟡 中 | 低（应文档化） |
| G 文档与 API 开放 | 3 | 4 | 🟠 高 | 高 |
| H 许可证 | 0 | 1 | 🔴 极高 | 战略性 |

---

## 3. 分类明细

### A. 性能与遍历（最高优先级）

根因已定位：**所有查找方法都从根节点开始全树递归**，且每个节点都要发起昂贵的跨进程 JAB 调用。

| # | 状态 | 标题 | 日期 | 评论 | 关键信息 |
|---|---|---|---|---|---|
| #33 | open | 复杂点的窗体定位控件很慢 | 2022-02-04 | **13** | 含 table 的窗体定位一个控件**要 40 秒**；改成完整 XPath 路径**毫无改善** |
| #29 | open | CPU usage when use find the element | 2022-01-12 | **12** | 查找失败时 CPU 24%；`find_element_by_xpath` 遍历所有节点 |
| #54 | open | find by xpath by another JABElement will through the root node | 2022-05-31 | 0 | 作者自建：**以某个 JABElement 为起点查找时，仍然从 root 开始遍历** |
| #58 | open | Xpath Parser enhancement | 2022-07-13 | 2 | 自研 XPath 解析器语法不全（清单见下） |
| #43 | closed | 测试用例跑久了，被控制的窗体会卡慢 | 2022-03-04 | 5 | **跑 30 分钟后越来越慢，1 小时后卡死**；CPU/内存正常 → 典型的 JAB 对象未释放泄漏 |
| #44 | closed | Locate root element failed with xpath | 2022-03-27 | 1 | 作者自建，根元素 XPath 定位失败 |
| #47 | closed | 能否把某些内部方法改成外部可调用 | 2022-04-08 | 2 | 用户需要直接调用 `_generate_childs_from_element` / `_get_accessible_selection_from_context` |

**#33 + #54 的组合是致命的设计缺陷**：用户以为写全路径能加速，实际不加速——说明解析器虽然识别了路径，但**执行时仍然做全树遍历**，路径信息没有被用于剪枝。这是最容易拿到数量级提升的优化点。

**#43 是另一个独立问题**：长时间运行后性能单调退化 → 资源泄漏。这与 PR #77 中"对不匹配的元素调用 `release_jabelement`"的处理方式互相印证，说明作者知道有泄漏问题但只在局部处理。

### B. 元素发现与定位（最高优先级）

| # | 状态 | 标题 | 日期 | 评论 | 关键信息 |
|---|---|---|---|---|---|
| #75 | open | How to get locators for the elements? | 2024-11-28 | 0 | **新用户根本不知道怎么写 locator** — 没有定位工具 |
| #56 | open | Can not found new opened java window | 2022-07-11 | 3 | 作者自建：新打开的窗口找不到（Java 控制面板 → 关于） |
| #15 | open | scroll to view | 2021-11-14 | 3 | 列表内元素滚动到可见；作者尝试用 `PropertyVisibleDataChange` 未果，**挂最久（4 年+）** |
| #19 | closed | 为什么我无法定位子窗体里的控件 | 2021-11-25 | 2 | 同一进程的第二个 root pane 拿不到 |
| #20 | closed | bounds {X=-1,Y=-1,W=-1,H=-1} 能否点击 | 2021-11-26 | **17** | 表格单元格 bounds 全是 -1，**SilkTest 能拿到，pyjab 不能** |
| #46 | closed | missing "desktop pane" role | 2022-03-30 | 2 | role 枚举缺失 |
| #48 | closed | 有什么好的方法可以定位元素吗 | 2022-04-18 | 2 | 与 #75 同一个需求，**2022 年就有人问了** |
| #50 | closed | 无法找到特定的元素 | 2022-05-09 | 3 | |

**#75 与 #48 相隔 2.5 年提出同一个问题**，说明"上手门槛"是长期未被解决的结构性问题。#75 的提问者甚至不是遇到 bug，是**卡在第一步**。

### C. 交互保真度

| # | 状态 | 标题 | 日期 | 评论 | 关键信息 |
|---|---|---|---|---|---|
| #71 | open | double click not working on JAB element | 2024-02-03 | 3 | 只有单击，没有双击 API。作者给的临时方案是"连点两次" |
| #68 | open | click(True) fails when run from Jenkins | 2023-06-29 | 1 | `win32gui.SetForegroundWindow` 抛出 `pywintypes.error` |
| #41 | closed | 我好像发现一个很大的BUG | 2022-03-01 | **14** | `click(simulate=True)` 无效；bounds 全 -1；**用户情绪激烈，作者未有效解决** |
| #42 | closed | 我发现一个很奇怪的问题 | 2022-03-01 | 2 | `simulate=True` 后热键失效、弹窗阻塞 |
| #21 | closed | 测试中碰到的问题 | 2021-11-28 | 2 | **希望保持后台操作**、截图串窗（截子窗体得到主窗体内容）、要双击、要 classname 定位 |
| #23 | closed | 如何对元素进行鼠标右键点击 | 2021-12-08 | 5 | 无右键 API |
| #14 | closed | send "enter" key | 2021-11-13 | 2 | |
| #53 | closed | 为什么 `_set_window_foreground` 里要 SendKeys(' ') | 2022-05-25 | 4 | 一个 hack 的成因，说明前台窗口管理是脆弱的 |

**核心矛盾**：`simulate=True` 会把目标窗口强行提到前台（用户明确表示"这对我非常不友好"），而 `simulate=False` 又不可靠。这是设计层面的问题，不是 bug。

### D. 表格与选择

| # | 状态 | 标题 | 日期 | 评论 | 关键信息 |
|---|---|---|---|---|---|
| #57 | open | Missing select action for AccessibleTable | 2022-07-13 | 2 | 作者自建 |
| #59 | open | Not able to auto scroll in table | 2022-07-20 | 4 | 表格不可见行取值时**应用直接崩溃** |
| #61 | open | Get Cell element in Select Cells property | 2022-08-05 | 4 | |
| #20 | closed | （见 B 类） | | 17 | |

### E. 安装与环境（最高优先级，成本最低）

| # | 状态 | 标题 | 日期 | 关键信息 |
|---|---|---|---|---|
| PR #70 | **open，未合** | Supports JDK16 and later versions | 2024-01-15 | **修复只有 6 行**，见下 |
| #64 | closed | pip install 冲突（1.0.0–1.1.7 全部） | 2022-10-31 | 根因：`requirements.txt` 同时有 `pypiwin32>=223` 和 `pywin32>=302`；`pypiwin32` 是废弃的 shim，会钉死 `pywin32==223`。**用户在 Mac 上也装了**，装上后运行必然失败 |

**PR #70 的技术实质**（`pyjab/config.py`）：

```python
# 现状（错误）
JDK_BRIDGE_DLL = os.environ.get("JAVA_HOME", ".") + f"\\jre\\bin\\{WAB_DLL}"
# PR #70
JDK_BRIDGE_DLL      = os.environ.get("JAVA_HOME", ".") + f"\\bin\\{WAB_DLL}"      # JDK 11+
JDKBEF16_BRIDGE_DLL = os.environ.get("JAVA_HOME", ".") + f"\\jre\\bin\\{WAB_DLL}" # JDK ≤10
```

JDK 11 起 JDK 安装目录下不再有 `jre` 子目录，DLL 位于 `%JAVA_HOME%\bin\`。
`pyjab/common/service.py:92-99` 的探测顺序只包含由环境变量拼出的固定路径，**没有任何兜底搜索**。
结论：**JDK 11+ 用户开箱即坏**，必须手动传 `dll=` 参数或设 `JAB_HOME`。这解释了为什么"下载量稳定但 issue 里全是入门问题"。

### F. 平台能力边界（应文档化，不应修）

| # | 状态 | 标题 | 日期 | 结论 |
|---|---|---|---|---|
| #73 | closed | canvas 中绘制的元素能否获取 | 2024-05-17 | JAB 无法访问 canvas 手绘 UI，属 JAB/NVDA 层面的限制 |
| #55 | closed | 嵌入在浏览器的 Java 如何获取 | 2022-06-15 | 用友 U8 等 Electron 内嵌 Java，Access Bridge Explorer 也抓不到 |
| #49 | closed | 如何连接 Applet | 2022-04-21 | |
| #19 | closed | 子窗体控件（部分属此类） | | |

**这一类不是 bug，是能力边界。** 不写清楚会导致用户反复提同类问题——#73 与 #55 就是同一类问题的两次提问。

### G. 文档与 API 开放

`docs/` 目录下**只有 `AccessBridge.h` 等 5 个 C 头文件，没有任何用户文档**。

| # | 状态 | 标题 | 日期 | 关键信息 |
|---|---|---|---|---|
| #75 | open | How to get locators | 2024-11-28 | 文档缺失的最直接证据 |
| #47 | closed | 能否把内部方法改成外部可调用 | 2022-04-08 | `_generate_childs_from_element` 等仍为私有 |
| #17 | closed | I don't understand the Win32 API part | 2021-11-23 | "文档太简单，很多函数没写" |
| #16 | closed | How to take a screenshot? | 2021-11-23 | |
| #48 | closed | 有什么好的方法可以定位元素吗 | 2022-04-18 | |
| #64 | closed | README_CN.rst 示例代码跑不通 | 2022-11-06 | #64 评论区：中文 README 示例与实际 API 不符 |

### H. 许可证（战略性，非技术）

**#30 —「是否考虑以 LGPL 协议分发」（2022-01-15，已关闭）**

这是全部 issue 里**商业意义最大的一个**，但被草率处理了。

- 请求者 `tshemeng` 的观点**在技术上是正确的**：GPLv2 库被链接进用户程序，用户的程序也必须以 GPL 发布。对一个"自动化公司内部 Java 客户端"的脚本来说，这是**不可接受**的——公司的自动化脚本不可能开源。
- 作者的回复（2022-01-16）："pyjab 只能以 GPLv2 协议进行分发，感谢关注，关于 GPLv2 的协议内容，您可能有些误解"——**这个回复是错的**，并附了 GPLv2 原文链接而非澄清。
- 请求者引用 GNU 官方 FAQ 反驳后，作者 2022-02-06 回复 **"Close without comment"**。

**这一条直接决定了变现路径，且是一个自我设置的障碍**：GPLv2 正在主动驱赶价值最高的用户群（企业 RPA 团队）。详见 `docs/ROADMAP.md` 第 5 节。

### 3.9 ⚠️ 仓库里存在三个不同版本，且都不是"可直接发布"的状态

> **本节是 3.9 节的修正版。** 初版把消息泵缺陷归因给了已发布版本并据此解释了 5 个历史 issue，**该结论是错的**——我把"工作区未提交的代码"当成了"用户实际在跑的代码"。经逐版本比对后修正如下。这也是本次审计最重要的发现。

#### 三个版本

| 版本 | 时间 | 状态 | 说明 |
|---|---|---|---|
| **v1.1.7**（tag） | 2022-05-23 | **已发布到 PyPI，用户实际在跑的就是它** | 功能完整，消息泵在窗口等待循环中被反复驱动 |
| **HEAD**（commit `9460721`） | 2023-05-06 | 已提交，**从未发版** | 35 个 commit 的重构；能编译通过；但引入 **2 处回归** |
| **工作区**（uncommitted） | 2023-05 | **未提交，且无法运行** | 在 HEAD 之上又改了 5 个文件（`by.py` / `win32utils.py` / `jab/api.py` / `jab/structure.py` / `jabdriver.py`，`jabdriver.py` 改了 637 行） |

#### 工作区 WIP 是坏的（两处硬错误）

1. **`pyjab/common/win32utils.py` 有语法错误**，模块无法导入：

   ```
   IndentationError: expected an indented block after 'elif' statement on line 206
   ```

   `win32utils.py:206-210` 的 `elif` 分支函数体只有注释、没有语句，紧接着又是 `elif`。
2. **`pyjab/jabdriver.py:180` 调用了不存在的方法**：`Service().create_session()`，而 `Service` 没有 `create_session`（全仓库唯一一处引用，旁边还留着 `# TODO: complete start session`）。

**推论**：导入 `pyjab.jabdriver` 就会失败，`JABDriver()` 根本无法实例化。**这很可能就是 2023 年真正停手的原因**——当时的重构做到一半，代码已经跑不起来了。`git status` 显示这些改动从未提交。

#### HEAD 相对 v1.1.7 有 2 处回归

| 回归 | v1.1.7 | HEAD | 影响 |
|---|---|---|---|
| **消息泵不再被反复驱动** | `wait_java_window_by_title` 的轮询循环里会重复调用 `_run_actor_sched()`（`jabdriver.py:288`） | **该调用被删除**，`_run_actor_sched()` 只在 `init_jab()` 中被调用一次（`jabdriver.py:179`） | 找到窗口后消息泵就再不被推进 |
| **每次创建 driver 泄漏 2 个内核事件** | `stop_event`/`other_event` 在**类体**中创建（`win32utils.py:19-20`），配合 `@singleton` → **每进程只创建一次，不泄漏** | 移到 `setup_msg_pump()` **函数体内**（`win32utils.py:177-178`），每次调用都创建；**全包搜索 `CloseHandle` 零命中** | 每次 `JABDriver()` 泄漏 2 个内核句柄 |

两处共同的机制是：`ActorScheduler.run_actor()` 的循环是 `while self.deque:`，而 `_run_actor_sched()` 只注册 1 个 actor，所以**每次调用只把生成器推进一个 `yield`**（约 200ms 一个切片）。v1.1.7 靠"在窗口等待循环里反复调用"来补偿这一点；HEAD 删掉了补偿。

> 注：`ActorScheduler` 是**生成器协作式调度器，不是线程池**，`run_actor()` 不创建任何真实线程。v1.1.7 与 HEAD 的实现在这一点上一致。

#### 工作区 WIP 还额外引入了一个更严重的缺陷

v1.1.7 和 HEAD 都用 `pythoncom.PumpWaitingMessages()`，返回 `True`（收到 WM_QUIT）才 `break`——这是正确的。
而工作区把这段改成了单次 `PeekMessageW` + `TranslateMessage` + `DispatchMessageW`，并且 **`break` 是无条件的**，跳出的是外层 `while True` → **派发第一条 Windows 消息后消息泵永久结束**。

#### 修正：这些缺陷能解释哪些 issue

| issue | 日期 | 修正后的判断 |
|---|---|---|
| #19（子窗口控件） | 2021-11 | ❌ **不相关**。早于 v1.1.7 之前的版本，与上述回归无关 |
| #43（越跑越慢直至卡死） | 2022-03 | ❌ **不能用句柄泄漏解释**。该 issue 早于 v1.1.7 发布，而句柄泄漏是 HEAD 才引入的。仍需在其他方向找原因（JAB Java 对象泄漏仍是候选） |
| #42（弹窗阻塞） | 2022-03 | ❌ **不相关**。同上，早于回归引入 |
| #56（找不到新窗口） | 2022-07 | ⚠️ **可能相关，但仅在 HEAD 上**。用户当时用的是 v1.1.x，而 v1.1.7 有补偿机制，所以未必 |
| #74（新窗口导致冻结） | 2024-11 | ⚠️ **可能相关**。报告时间晚，用户可能已从 GitHub 安装了 HEAD |

**因此：#56 / #74 与消息泵的关系是"待验证的假设"，而不是已确认的根因；#19 / #42 / #43 与消息泵无关。** 初版的归因是错的。

#### 对发版决策的影响（这才是本节真正的价值）

1. **绝不能发布工作区 WIP**：它连导入都失败。
2. **不能直接发布 HEAD**：它会引入句柄泄漏、并丢掉 v1.1.7 已有的消息泵补偿逻辑——即"修好的东西变坏了"。
3. **推荐做法**：以 **HEAD 为基线**（保留 35 个 commit 的重构成果），但**先回补这 2 处回归**，再加上 P0 修复，然后才发 1.2.0。
4. 无论选哪个基线，**都必须先在 Windows 上验证**（见第 7 节）。这两个回归恰好也说明：没有 Windows 验证环境的这几年，HEAD 上的改动是"越改越坏"的。

#### 对 pyjab-mcp 的影响

仍然成立，甚至更强：MCP server 是长期存活的进程，而**三个版本里没有任何一个实现了持续运行的消息泵**（v1.1.7 靠轮询补偿，HEAD 连补偿都没有）。所以"把消息泵改为独立线程持续运行"依然是 pyjab-mcp 的前置硬依赖。见 `docs/PYJAB_MCP_PLAN.md` 第 3.5 节。

---

## 4. 两个悬空 PR 的处理建议

### PR #70 — JDK16+ 支持

- **状态**：2024-01-15 提交，至今未合，无 review 记录
- **内容**：`config.py` + `service.py`，共 6 行
- **评价**：方向正确，命名可以改进（`JDKBEF16_BRIDGE_DLL` 命名不清），且**没有解决根本问题**——仍然只探测环境变量拼出的路径
- **建议**：**吸收而非直接合并**。见下方 P0 项

### PR #77 — get_children + name pattern 查找

- **状态**：2026-07-17 提交，至今未合
- **内容**：`get_children()`、`find_elements_by_name_pattern()`、`find_element_by_name_pattern()`
- **评价**：功能有用，依赖项**已核对通过**
  - `self._is_element_matched` 存在，且是 `@staticmethod`（`jabelement.py:1577-1578`），PR 的调用形式正确
  - `re` 已在 `jabelement.py:9` 导入，`re.search` 可用
  - 仍需修正：`list[JABElement]` 注解需要 Python 3.9+，而 `setup.py` 声明 `python_requires=">=3.8"`（该文件第 1 行已有 `from __future__ import annotations`，实际影响有限）
  - 仍需修正：`by: By = None` 应标为 `Optional[By]`
  - 仍需改进：`find_elements_by_name_pattern` 在 `raise` 前对已找到的元素没有统一释放策略
- **建议**：review 后合并，修正上述问题

---

## 5. 优先级排序

### P0 — 发版前必须（预计 2–3 周，每周 4–6 小时）

| 项 | 内容 | 是否需要 Windows 验证 |
|---|---|---|
| P0-1 | **DLL 定位健壮化**：探测顺序加上 `%JAVA_HOME%\bin\`，再加**文件系统兜底搜索**（在 JAVA_HOME/JRE_HOME/JAB_HOME 及常见安装路径下递归找 `WindowsAccessBridge-{64,32}.dll`），并在全部失败时给出可操作的错误信息（告诉用户去哪个路径找、怎么设 `JAB_HOME`） | 是 |
| P0-2 | **修复打包**：`requirements.txt` 移除 `pypiwin32`；`setup.cfg` 去掉 `universal=1`；加 `pyproject.toml`；加 platform 声明，让非 Windows 平台在**安装时**就明确报错而不是装上后运行崩 | 否 |
| P0-3 | **发版流程**：35 个未发版 commit 发布为 1.2.0；建立 tag → PyPI 的自动发布流水线 | 否 |
| P0-4 | **README 重写**：以"从零到跑通第一个脚本"为主线；补 JDK 版本与 DLL 路径对照表；补 `simulate` 参数的真实语义；**明确写出能力边界**（canvas / 内嵌浏览器 / Applet 不支持） | 否 |
| P0-5 | **定位辅助工具**：一个能把可访问性树 dump 成可读文本 / 生成 locator 的命令行工具（解决 #75 / #48） | 是 |

**P0-1 的定位**：这一个改动解开的是"所有现代 JDK 用户"。成本低、影响面最大，应该第一个做。

### P1 — 核心体验（预计 4–6 周）

| 项 | 内容 | 关联 issue |
|---|---|---|
| **P1-0** | **消息泵改造 + 回归回补（最高优先，先于所有其他 P1）**：① 回补 HEAD 删除的"窗口等待循环中重复驱动消息泵"；② 把内核事件创建移出函数体并补 `CloseHandle`；③ 改造为**独立线程中持续运行**。见 3.9 节 | #56 #74（待验证）；同时也是 pyjab-mcp 前置 |
| P1-1 | **遍历剪枝**：让 XPath 路径参与剪枝，避免全树遍历；`find_element` 命中即停 | #33 #54 #58 |
| P1-2 | **资源泄漏治理**：审计所有 JAB 对象（`release_jabelement`）释放路径，加长时间运行不退化的自动化检测 | #43 |
| P1-3 | **新窗口/多窗口发现**：`window_handles` 与 `swith_to` 的正确性（先做 P1-0 再验证是否仍需要） | #56 #74 #19 |
| P1-4 | **DPI 感知**：进程声明 DPI awareness，并做逻辑坐标→物理坐标转换 | #62 #41 |
| P1-5 | **双击与右键**：补齐基础鼠标操作 | #71 #21 #23 |
| P1-6 | **前台窗口策略**：解决 `simulate=True` 抢焦点 / `SetForegroundWindow` 非交互会话失败 | #68 #21 #42 |

> **关于泄漏源**：P1-0 修的是 **HEAD 新引入的内核句柄泄漏**（v1.1.7 没有这个问题）；P1-2 修的是 **JAB Java 对象泄漏**（`release_jabelement` 覆盖不全，v1.1.7 与 HEAD 都有）。两者独立。
> **关于 #43**：初版曾把 #43「越跑越慢」归因于内核句柄泄漏，**该归因已撤回**——#43 早于该回归引入。见 3.9 节的修正说明。

### P2 — 能力补全（预计 4–8 周）

| 项 | 内容 | 关联 issue |
|---|---|---|
| P2-1 | 表格：`AccessibleTable` 的 select 动作、不可见行安全读取 | #57 #59 #61 #20 |
| P2-2 | XPath 解析器补全（按 #58 清单） | #58 |
| P2-3 | 合并 PR #77（get_children / name pattern） | #77 |
| P2-4 | 开放部分内部方法为公开 API | #47 |
| P2-5 | 滚动到可见元素 | #15 |

### P3 — 明确不做，改为文档化

canvas 手绘 UI（#73）、浏览器/Electron 内嵌 Java（#55）、Applet（#49）。
**处理方式**：在 README 和维护者手册里写清"为什么不支持"和"替代方案"，然后给这些 issue 打 `wontfix` + 说明并关闭。**放着不回的代价高于明确拒绝**。

---

## 6. 隐性待办（不在 open 列表里，但必须处理）

1. **README_CN.rst 不存在**。PR #18 于 2021-11-24 合并了该文件，但当前工作区与 HEAD 中都没有它，#64 的评论还引用它作为示例来源。需确认是何时被谁删除，或重建。
2. **`temp.py`** 是调试遗留（logger 冒烟测试），应删除。已在 `.gitignore` 的 `temp*` 中，未被跟踪。
3. **`build/` 与 `dist/` 是本地残留产物**（`.gitignore` 已忽略，**未提交进仓库**，git 中零文件）。但 `build/lib/pyjab/` 里是旧版代码（含已删除的 `jabfixedfunc.py`、`accessibleinfo.py`），会**遮蔽真正的 `build` Python 包**——实测 `python3 -m build` 会报 `No module named build.__main__`。建议直接删除这两个目录。
4. **`docs/` 目录被 C 头文件占用**，用户文档无处安放。建议 C 头文件移到 `docs/reference/`，`docs/` 留给用户文档。
5. **`__version__ = "1.1.7"`**：HEAD 比已发布的 1.1.7 领先 35 个 commit，版本号必须先 bump 再发版。
6. **无 CI**。没有 `.github/workflows`、没有 `tox.ini`、没有 `pyproject.toml`。
7. **工作区有 5 个文件自 2023-05 起未提交**（`common/by.py`、`common/win32utils.py`、`jab/api.py`、`jab/structure.py`、`jabdriver.py`），另有 2 个未跟踪新文件（`common/timeout.py`、`support/__init__.py`）。**这批 WIP 无法导入**（见 3.9 节），需要决定是修复、重置还是丢弃。
8. **GPLv2 + 外部贡献者 `jsa34`**（19–20 个 commit，涉及 `jabelement.py` / `jabdriver.py` / `win32utils.py` / `xpathparser.py` 等核心文件）。任何重新授权都需要其同意。**这是路线图的前置决策项。**

---

## 7. 阻塞项：没有 Windows 测试环境

这是当前最硬的约束。pyjab 只能在 Windows 上运行，而开发机是 macOS。**所有 P0-1 / P1-4 / P1-5 / P1-6 都无法在本地验证**，盲改的修复等于没修。

按成本从低到高，可行方案：

| 方案 | 成本 | 能验证什么 | 评价 |
|---|---|---|---|
| **GitHub Actions `windows-latest`** | 免费（公开仓库） | 打包正确性、导入、纯逻辑单测、DLL 路径解析 | **必做**。先把不需要 GUI 会话的部分全覆盖 |
| **云 Windows 实例按小时计费** | 约 ¥1–3/小时 | 全部，含真实 GUI 自动化 | **推荐主力**。按需开机，每月 4–6 小时的预算下成本可忽略 |
| **本地虚拟机（UTM/Parallels + Windows 11 ARM）** | 时间成本 | 大部分；JAB DLL 为 x64，在 ARM Windows 上依赖 x64 仿真 | 一次性投入高，但长期最省 |
| **向社区求助** | 人情成本 | 真实环境回归 | 你有 25 个 fork，其中必然有人在稳定使用。可在 issue 里请求协助验证 |
| **买一台二手 Windows 小主机** | ¥300–800 | 全部 | 若打算长期做，长期看最划算 |

**建议**：先用 GitHub Actions 打通"不需要 GUI 的测试"（覆盖 P0-2/P0-3 的全部和 P0-1 的路径解析逻辑），同时申请一个按小时的云 Windows 实例作为人工验证环境。**不要在没有 Windows 验证手段之前动 P1-4/P1-5/P1-6。**

---

## 8. 与竞品对比后的问题优先级修正

调研结论（数据见 `docs/ROADMAP.md`）：通用 Windows 自动化 MCP 已拥挤（`FlaUI-MCP` 103 star），但 **Java/Swing 专属几乎无人**（swing-mcp 2 star）。

这带来一个优先级修正：**"能被 AI agent 稳定驱动"相关的问题要提前**。

- P0-5（定位辅助工具）不只是给人用的，它同时是 MCP 工具面的基础
- P1-1（遍历剪枝）在 MCP 场景下从"性能优化"升级为"**能否可用**"——因为一次全树遍历既花 40 秒、又会把海量节点塞进模型的上下文
- A 类性能问题的收益在 MCP 场景下被放大，应视为产品能力而非优化项

详见 `docs/PYJAB_MCP_PLAN.md`。
