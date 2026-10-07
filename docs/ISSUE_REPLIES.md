# pyjab Issue / PR 回复草稿

> 用途：阶段 0 第 1 项「回复全部 15 个 open issue + 2 个 open PR」。
> 当前环境**没有安装 `gh` CLI**，所以下面每条都写成可直接粘贴的文本。
>
> 如果之后安装了 `gh`（`brew install gh && gh auth login`），可以这样批量发：
>
> ```bash
> # 示例：把本条回复发到 issue 75
> gh issue comment 75 --repo gaozhao1989/pyjab --body-file /tmp/reply-75.md
> ```
>
> 建议节奏：**先发 #75 / #74 / #76 / PR #70 / PR #77 这 5 条**（最新且零回复的），
> 其余按优先级慢慢回。不要一次性全发，留出处理后续追问的余力。

---

## 通用前缀（新回复里统一带上一次即可）

中文版：

> 抱歉这么久没有回复——这个项目在 2023 年因为工作原因中断了维护，我最近重新接手，
> 会持续处理积压的 issue。感谢你还在用 pyjab。
> 刚发布的 **1.2.0** 修了一个影响所有 JDK 11+ 用户的问题：DLL 只在
> `%JAVA_HOME%\jre\bin` 里查找，而 JDK 11 起这个目录已经不存在了，DLL 实际在
> `%JAVA_HOME%\bin`。如果你之前必须手动传 `bridge_dll=`，现在应该不需要了。
> 详情见 CHANGELOG。

English version:

> Apologies for the long silence -- this project went unmaintained in 2023 for
> work reasons and I have only just picked it back up. I am working through the
> backlog now. Thanks for still using pyjab.
> **1.2.0** fixes a problem that affected every JDK 11+ user: the DLL was only
> looked for in `%JAVA_HOME%\jre\bin`, but that directory stopped existing in
> JDK 11 and the DLL now lives in `%JAVA_HOME%\bin`. If you previously had to
> pass `bridge_dll=` by hand, you should not need to any more. See CHANGELOG.

---

# 一、零回复的 5 条（最高优先）

## #75 — How to get locators for the elements?

**English.** 这条是文档缺口，回复应直接给出可操作答案。

> Thanks for reporting this -- and sorry for the silence.
>
> You are not doing anything wrong: pyjab has never documented how to find
> locators, and that is a real gap. I have just rewritten the README with a
> dedicated "Finding locators" section. Short version:
>
> **1. Install [Access Bridge Explorer](https://github.com/google/access-bridge-explorer).**
> Expand the tree of your target application. Every node shows exactly the
> fields pyjab exposes: `name`, `description`, `role`, `states`,
> `indexInParent`, `bounds`. Whatever you see there is what you pass to
> `find_element_by_*`.
>
> **2. Pick the locator that matches what you can see:**
>
> ```python
> driver.find_element_by_name("Submit")                    # accessible name
> driver.find_element_by_role("push button")               # no useful name
> driver.find_element_by_index_in_parent(3)                # neither name nor role
> driver.find_element_by_xpath("//push button[@name=contains('OK')]")
> ```
>
> **3. If a control has no accessible name**, call
> `driver.find_elements_by_role("...")` first and print what comes back -- a
> sibling or parent usually carries the label you want.
>
> The most common mistake is using the *visible* label as the name. They are
> often different (a button labelled "Login" frequently has the accessible name
> `"Login"` but sometimes `"Login..."`, `"&Login"` or nothing at all).
> Access Bridge Explorer removes the guesswork.
>
> If you are still stuck, paste the output of
> `driver.find_elements_by_role("<role>")` for the window you are working with
> and I will help you write the locator.

## #74 — Script Freezes when a new window

**English.** 需要复现信息。

> Sorry for the silence, and thanks for the detailed report.
>
> What you are describing -- the script freezing when a second window opens --
> matches a known weak spot: after the first window is found, pyjab stops
> driving the Windows message pump, so newly opened top-level windows and modal
> dialogs may never be seen. I am fixing this in 1.3.0.
>
> A few questions so I can confirm that is what you are hitting:
>
> 1. Does it freeze forever, or eventually raise a timeout?
> 2. Is the second window a **modal** dialog (does the first window stop
>    responding until you close it)?
> 3. Does `simulate=True` anywhere in the script make it worse? That parameter
>    forces the window to the foreground and can deadlock with a modal dialog.
> 4. Which JDK version is the target application running on?
>
> **Workaround to try in the meantime:** instead of constructing a second
> `JABDriver("Configuración de Archivos Temporales")`, reuse the first driver and
> search for the dialog's contents through it, or poll
> `driver.wait_until_element_exist(By.NAME, "Aceptar")`.
>
> If you can attach a minimal script plus the JDK version, that would help a lot.

## #76 — 再使用当中碰到一些问题，跪求指导

**中文。** 三个问题都要正面回答。

> 抱歉这么久才回复——项目 2023 年因工作原因中断，我刚重新接手，正在清理积压。
> 先把你这三个问题逐个答一下。
>
> **1. `with JABDriver(file_path=..., timeout=60)` 会阻塞**
>
> 这是设计如此，不是 bug。`file_path` 分支会执行
> `Popen(cmd, shell=True)` 然后 `p.wait()`——**它会一直等到目标进程退出**。
> 对 `.jnlp` 来说还会先走 `javaws`，而 `javaws` 本身也要等应用关闭才返回。
>
> 两种解法：
>
> ```python
> # 解法 A：自己启动应用，让 pyjab 只负责绑定（推荐）
> import subprocess
> subprocess.Popen([r"C:\path\to\javaws.exe", r"D:\copy\swing-test.jar"])
> driver = JABDriver(title="你的窗口标题", timeout=60)
>
> # 解法 B：干脆不用 file_path，手动把应用跑起来再绑定
> ```
>
> 另外提醒一句：这里其实还有个 bug——`open_application()` 里判断
> `self.file_path.suffix == "jnlp"`，但 `Path.suffix` 是带点的（`.jnlp`），
> 所以 javaws 分支从来没生效过。这个我已经在 1.2.0 里修了。
>
> **2. 如何获取没有 name / title 的 dialog（比如登录页）**
>
> 不要按 name 找，按 **role + index** 找：
>
> ```python
> from pyjab.common.by import By
>
> # 列出所有 dialog
> dialogs = driver.find_elements_by_role("dialog")
> print([(d.name, d.index_in_parent, d.bounds) for d in dialogs])
>
> # 多个 dialog 时用 index 区分
> login = driver.find_element_by_index_in_parent(1)
> ```
>
> 建议先用 [Access Bridge Explorer](https://github.com/google/access-bridge-explorer)
> 展开看看这个 dialog 到底有什么可用的属性——通常 `role` 和
> `index_in_parent` 一定存在。
>
> **3. 如何操作 JTable、读取全部数据和选中行的数据**
>
> ```python
> table = driver.find_element_by_role("table")
>
> # 行列数
> info = table.table          # {'row_count': .., 'column_count': .., ...}
>
> # 取单元格
> cell = table.get_cell(row=2, column=1)
> print(cell.text)
>
> # 选中某行：表格必须走 accessible selection，鼠标点击 bounds 是 -1 用不了
> table.select("行标识")       # 或参考 README 的 selection 说明
> ```
>
> **重要限制**：终端里滚动到不可见区域的单元格**读不到，而且可能让目标程序崩溃**
> （这正是 issue #59 报的问题）。请先把表格滚到目标行可见，再取值。
> 详细说明见 README 的 Limitations 一节。
>
> 如果方便，把 `table.table` 的输出和 Access Bridge Explorer 里表格节点的截图发我，
> 我可以给你更具体的代码。

## PR #70 — Supports JDK16 and later versions

**English.** 感谢 + 说明被更大范围实现取代 + 请求 review。

> Thank you for this -- and apologies for leaving it unmerged for so long. This
> was the right diagnosis and it turned out to matter much more than it looked:
> JDK 11 removed the bundled `jre` directory, so this affected every modern JDK,
> not just 16+.
>
> I have just implemented the fix in 1.2.0, expanded well beyond the two lines
> here. Rather than only swapping the path, discovery now walks:
>
> 1. the explicit `bridge_dll` argument
> 2. `%JAVA_HOME%\bin` (JDK 11+), then `%JAVA_HOME%\jre\bin` (JDK 8-10), then `%JAVA_HOME%`
> 3. `%JDK_HOME%`, `%JRE_HOME%`, `%JAB_HOME%`
> 4. common vendor install locations (Adoptium, Corretto, Zulu, Microsoft, scoop, IntelliJ-downloaded JDKs)
> 5. a bounded recursive fallback
>
> and a failed lookup now reports every directory probed, flags a bitness
> mismatch, and prints three concrete ways to fix it. The logic is in
> `pyjab/config.py` and is unit tested on every OS.
>
> I am closing this PR in favour of the implementation above, but your report is
> credited in the CHANGELOG. **If you have a Windows box with a JDK 16+ install,
> I would really value your review of `pyjab.config.find_bridge_dll()`** -- you
> found the original problem, so you will know fastest whether this covers it.
> CI now runs the discovery against Temurin JDK 8/11/17/21 on every push.

## PR #77 — Add get_children() method to JABElement

**English.** 感谢 + 审查意见 + 计划合并。

> Thanks for this, and sorry for the delay. `get_children()` and the regex name
> matching are both genuinely useful additions.
>
> I have reviewed the diff against current `dev` (not merged yet -- it is queued
> for 1.3.0, not 1.2.0, so that 1.2.0 stays a focused compatibility release):
>
> * `self._is_element_matched` exists and is a `@staticmethod`
>   (`jabelement.py:1577`), so your call form is correct.
> * `re` is already imported in `jabelement.py`, so `re.search` is fine.
> * Two small things I will fix on merge: `by: By = None` should be
>   `Optional[By]`, and `find_elements_by_name_pattern` raises before releasing
>   the elements it already collected.
>
> One design question before I merge: should `get_children()` raise when it
> finds nothing, or return an empty list? `find_elements_by_*` currently raises,
> but for a traversal primitive an empty list is more useful. I lean towards
> empty list -- any objection?

---

# 二、其余 open issue

## #15 — scroll to view

**English.**

> Sorry for the very long delay on this one -- it is the oldest open issue here.
>
> Your suggestion from back then was the right instinct, and I now have a better
> answer to why it is hard: JAB exposes no scroll-position information, so there
> is nothing to poll. `PropertyVisibleDataChange` fires, but it does not tell you
> *where* the scrollbar ended up.
>
> Practical approach I am planning for 1.3.0: compare the target element's
> bounds against its scrollable parent's bounds, scroll by a bounded number of
> steps, and re-check after each step -- exactly the algorithm you proposed. It
> will be best-effort rather than exact, and it needs the parent to report valid
> bounds.
>
> In the meantime, `element.scroll(to_bottom=True, hold=N)` drives the scrollbar
> via mouse actions and is the only tool available. If your list length is
> unbounded, scroll in steps and re-query rather than trying to scroll to a
> computed offset.

## #29 — CPU usage when use find the element

**English.**

> Thanks for this, and apologies for the delay.
>
> Your diagnosis in the thread was correct: every `find_element_by_*` walks the
> entire accessibility tree from the root, and each node costs a cross-process
> JAB call. When the element is *not* found in a large window, that is a lot of
> wasted work -- which is why you saw high CPU only on failed lookups.
>
> Two things you can do today:
>
> 1. **Narrow the search root.** Find a stable ancestor once, then search under
>    it, rather than searching from the driver each time:
>
>    ```python
>    panel = driver.find_element_by_name("OrderPanel")
>    button = panel.find_element_by_name("Submit")   # searches a subtree
>    ```
>
> 2. **Do not wrap finds in `try/except` inside a polling loop.** Each failed
>    attempt is a full traversal. Use
>    `driver.wait_until_element_exist(By.NAME, "...", timeout=30)` instead -- it
>    re-queries on a single path.
>
> The real fix (pruning the traversal using the locator instead of walking
> everything) is the top item in the 1.3.0 roadmap. I will post here when there
> is something to test.

## #33 — 复杂点的窗体定位控件很慢

**中文。**

> 抱歉拖了这么久才回。你这条 issue 里的信息量很大，而且你的观察是对的——
> **写全 XPath 路径并不会变快**，这一点当年我没解释清楚。
>
> 原因：`_generate_all_childs` 是从根节点开始的全树递归遍历，XPath 的路径信息
> 目前**没有参与剪枝**。所以无论写 `//push button` 还是完整路径，都要先把整棵树
> 走一遍，再拿路径去过滤。含大表格的窗口节点多，配上每次节点访问的跨进程 JAB
> 调用，40 秒就说得通了。
>
> 关于你试的多进程方案：不可行。JAB 的 DLL 句柄和 Java 对象引用不是线程安全的，
> 跨进程共享同一个 `JABDriver` 一定会崩。当年我回复"不考虑多线程"就是这个原因。
>
> **现在能用的缓解办法：**
>
> ```python
> # 1. 先定位一个稳定的祖先，再在它的子树里找（能显著减少节点数）
> panel = driver.find_element_by_name("订单面板")
> btn = panel.find_element_by_name("提交")
> ```
>
> 2. 避免在 `try/except` 里反复调用 `find_element_by_xpath`——每次失败都是一次
>    全树遍历。用 `wait_until_element_exist` 替代。
>
> **真正的修复**（让 XPath 路径参与剪枝 + 命中即停）已经排在 1.3.0 的第一项。
> 我会在这个 issue 里同步进展。如果方便，能告诉我目标窗口大概有多少个节点吗
> （Access Bridge Explorer 里能看出层级规模）？这能帮我验证优化效果。

## #54 — find by xpath by another JABElement will through the root node

**English.** 作者自建 issue，是明确的 bug。

> Re-confirming this is a real bug and noting the fix for 1.3.0.
>
> `JABElement.find_element_by_xpath()` calls
> `_get_children_by_level(level)` which defaults to `"root"`, so searching from a
> child element silently re-traverses from the top of the tree. The `level`
> argument exists but is never threaded through from the xpath path.
>
> This is both a correctness bug (a relative path can match something outside
> the subtree you started from) and a performance bug (it is why searching from
> a child is no faster than searching from the driver -- see #33). Fixing it
> together with the traversal pruning work.

## #56 — Can not found new opened java window

**English.** 作者自建。

> Still reproducing, and I now understand it better.
>
> Two contributing causes:
>
> 1. After the first window is found, `_run_actor_sched()` is no longer called,
>    so the Windows message pump stops. New top-level windows are announced
>    through the message loop, so they can go unnoticed.
> 2. `wait_java_window_by_title` matches on title only, so a window with an
>    empty or dynamic title is never matched.
>
> For the Java Control Panel -> About repro specifically: the About dialog is a
> modal child, not a new top-level window, so even a working pump may not make it
> reachable by title. Searching through the existing driver with
> `find_element_by_role("dialog")` is the more reliable route.
>
> Fixing the pump is the top item in 1.3.0; I will re-test this exact repro then.

## #57 — Missing select action for AccessibleTable

**English.**

> Confirming this is still missing. `AccessibleSelection` is used for
> list/combo/tab selection, but tables need the row/column selection entry points
> and those are not exposed at all yet.
>
> Plan for 1.3.0: expose selection on `AccessibleTable` (select row, select
> column, select cell, read back the selection) and document the ordering
> requirement -- JAB only lets you interact with a table through its accessible
> selection, which is why clicking table cells with `simulate=True` does nothing
> when the cells report `bounds = -1` (see #20 and #61).

## #58 — Xpath Parser enhancement

**English.** 作者自建 checklist。

> Updating the checklist against the 1.2.0 code. Currently supported:
>
> * `nodename`
> * `@attr = 'value'`
> * `@attr = contains('value')`
> * `//*`
> * `[n]` positional predicates
>
> Still missing (unchanged):
>
> * `/` and `//` as distinct axes -- the parser currently treats the tree as flat
> * `.` and `..`
> * comparison predicates such as `[@indexinparent > 10]`
> * union `|`
> * axes
>
> Given the traversal-pruning work in 1.3.0 touches the same code path, I would
> rather land the parser changes together with it than twice. Keeping this open
> as the tracking issue.

## #59 — Not able to auto scroll in table

**English.** 用户报了崩溃，最重要是给出安全做法。

> Thanks for the report -- the crash you are seeing is the important part here,
> and it is a real limitation rather than something you are doing wrong.
>
> `_get_visible_children()` only returns the children the application reports as
> visible. Your loop then indexes past that array while using `row * col` as the
> upper bound, so it reads beyond the populated entries and touches stale or
> invalid JAB object references. That is what destabilises the target process.
>
> **Please bound the loop by the size of the array you actually got back**, and
> only read what is on screen:
>
> ```python
> children = table._get_visible_children()
> count = len(children.children)          # do NOT assume row_count * col_count
> for i in range(count):
>     ...
> ```
>
> For records scrolled out of view: JAB does not expose them, and trying to reach
> them is exactly what crashes. Scroll the table so the target row is visible,
> then query again. README now documents this under Limitations.
>
> Automatic scrolling that respects visibility is on the 1.3.0 list (it is the
> same problem as #15).

## #61 — Get Cell element in Select Cells property

**English.** 需要更多信息。

> Thanks for the report. To move this forward I need a bit more detail:
>
> 1. What does `table.table` return for `row_count` / `column_count`?
> 2. What does `table.get_cell(row, column)` give you -- an exception, or an
>    element with unusable properties?
> 3. Does the table report `AccessibleSelection` and `AccessibleTable` in
>    `element.accessible_interfaces`?
>
> Background on why this is awkward: JAB only allows interaction with table
> contents through the accessible selection, and many tables report
> `bounds = {x: -1, y: -1, width: -1, height: -1}` for their cells (see #20).
> When bounds are invalid, `simulate=True` cannot work at all -- there is no
> coordinate to click -- so the accessibility action path is the only option.
> I want to know which of those two situations you are in.
>
> Table selection support (select row/column/cell, read back the selection) is
> planned for 1.3.0, tracked in #57.

## #62 — Logical coordinates differ from physical coordinates when DPI changes

**English.** 这条诊断质量很高，值得认真对待。

> This is an excellent diagnosis and you are right on both counts.
>
> Confirmed: pyjab never declares DPI awareness and never converts JAB's logical
> coordinates to physical ones. On a display at 125% or 150% scaling,
> `simulate=True` therefore moves the cursor to the wrong place. The
> `PROCESS_PER_MONITOR_DPI_AWARE` detail you identified is the missing piece.
>
> Plan for 1.3.0:
>
> 1. declare per-monitor DPI awareness for the pyjab process, and
> 2. convert logical -> physical coordinates before calling
>    `SetCursorPos` / `SendInput`, using the target window's DPI.
>
> Both need a Windows machine with scaling set to 125%/150% to verify -- I am
> setting that up. In the meantime, the escape hatch is to mark the *target*
> application as DPI aware (which is what makes its bounds physical), or to run
> at 100% scaling.
>
> If you still have the environment where you found this, I would very much like
> your help verifying the fix when it is ready.

## #68 — Issue in click(True) Function when run from Jenkins

**English.** 明确的根因。

> This is expected behaviour rather than a bug in pyjab, though the failure mode
> is unhelpful.
>
> `simulate=True` sets the target window to the foreground with
> `SetForegroundWindow`. Windows refuses that call when the process is not
> attached to an interactive desktop session -- which is exactly how a Jenkins
> agent usually runs (as a service, in session 0). Hence
> `pywintypes.error: (0, 'SetForegroundWindow', 'No error message is available')`.
>
> Two ways forward:
>
> 1. **Drop `simulate=True`.** The default (`simulate=False`) drives the control
>    through the JAB accessibility action API and does not need the window in the
>    foreground -- so it works fine from a service session. This is the right fix
>    for most cases; `simulate=True` should only be used when the accessibility
>    action is ignored by the application.
> 2. **Run the Jenkins agent interactively** (as a logged-in user, not a
>    service) if you genuinely need real mouse input.
>
> I am also going to make this fail with a clear message instead of a raw
> `pywintypes.error` -- tracked for 1.3.0.

## #71 — double click not working on JAB element

**English.**

> Confirmed -- there is no double-click API. What I suggested at the time (call
> `click()` twice) works, but only if the two clicks land within the system
> double-click interval, which is fragile:
>
> ```python
> element.click()
> element.click()      # may be treated as two single clicks
> ```
>
> The reliable route today is a real mouse double-click via `win32api`, which
> needs valid bounds:
>
> ```python
> import win32api, win32con
> b = element.bounds
> if b["width"] > 0 and b["height"] > 0:
>     x, y = b["x"] + b["width"] // 2, b["y"] + b["height"] // 2
>     win32api.SetCursorPos((x, y))
>     for _ in range(2):
>         win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0)
>         win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0)
> ```
>
> Note this needs the window in the foreground, and it will not work when the
> element reports `bounds = -1` (common for table cells).
>
> Adding `click(double=True)` and a right-click alongside it is on the 1.3.0
> list -- it is a small, well-understood change.

---

# 三、发布后可以补发的（暂时不必回复，等 1.2.0 上线后一并提）

以下 issue 属于 1.2.0 **已经间接解决或明确不做**的，可以在 1.2.0 发布后补一条说明：

| issue | 处置 |
|---|---|
| #70（PR） | 已由 1.2.0 的 DLL 发现逻辑覆盖，关闭时引用上面的回复 |
| #56 / #74 | 等 1.3.0 消息泵修复后再回复，避免给两次承诺 |
| #15 / #57 / #58 / #59 / #61 | 归入 1.3.0 表格与遍历工作，统一在一个 tracking issue 里同步 |
| #19（closed） | 已关闭，不必重开；但可在 1.3.0 说明里提及 |
| #42 / #43（closed） | 同上。若再次收到同类报告再开新 issue |

---

# 四、建议的回复顺序与时间盒

按「每周 1 小时回 issue」的固定开销，分三批：

| 批次 | 内容 | 预估 |
|---|---|---|
| 第 1 批（本周） | #75、#74、#76、PR #70、PR #77 | 40 分钟 |
| 第 2 批（下周） | #33、#29、#54、#68、#71 | 40 分钟 |
| 第 3 批（第三周） | #15、#56、#57、#58、#59、#61、#62 | 50 分钟 |

**注意**：#62 的提问者（`discovery-131794`）和 #15 的提问者（`szczepanR`）
诊断质量都很高，是潜在的协作者。回复时可以主动邀请他们验证 1.3.0 的修复——
这比你自己搭环境更快。
