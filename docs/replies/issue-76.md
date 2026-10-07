抱歉这么久才回复——项目 2023 年因工作原因中断，我刚重新接手，正在清理积压。
先把你这三个问题逐个答一下。

**1. `with JABDriver(file_path=..., timeout=60)` 会阻塞**

这是设计如此，不是 bug。`file_path` 分支会执行
`Popen(cmd, shell=True)` 然后 `p.wait()`——**它会一直等到目标进程退出**。
对 `.jnlp` 来说还会先走 `javaws`，而 `javaws` 本身也要等应用关闭才返回。

两种解法：

```python
# 解法 A：自己启动应用，让 pyjab 只负责绑定（推荐）
import subprocess
subprocess.Popen([r"C:\path\to\javaws.exe", r"D:\copy\swing-test.jar"])
driver = JABDriver(title="你的窗口标题", timeout=60)

# 解法 B：干脆不用 file_path，手动把应用跑起来再绑定
```

另外提醒一句：这里其实还有个 bug——`open_application()` 里判断
`self.file_path.suffix == "jnlp"`，但 `Path.suffix` 是带点的（`.jnlp`），
所以 javaws 分支从来没生效过。这个已经修好了，会随 1.2.0 一起发布。

**2. 如何获取没有 name / title 的 dialog（比如登录页）**

不要按 name 找，按 **role + index** 找：

```python
from pyjab.common.by import By

# 列出所有 dialog
dialogs = driver.find_elements_by_role("dialog")
print([(d.name, d.index_in_parent, d.bounds) for d in dialogs])

# 多个 dialog 时用 index 区分
login = driver.find_element_by_index_in_parent(1)
```

建议先用 [Access Bridge Explorer](https://github.com/google/access-bridge-explorer)
展开看看这个 dialog 到底有什么可用的属性——通常 `role` 和
`index_in_parent` 一定存在。

**3. 如何操作 JTable、读取全部数据和选中行的数据**

```python
table = driver.find_element_by_role("table")

# 行列数
info = table.table          # {'row_count': .., 'column_count': .., ...}

# 取单元格
cell = table.get_cell(row=2, column=1)
print(cell.text)

# 选中某行：表格必须走 accessible selection，鼠标点击 bounds 是 -1 用不了
table.select("行标识")       # 或参考 README 的 selection 说明
```

**重要限制**：终端里滚动到不可见区域的单元格**读不到，而且可能让目标程序崩溃**
（这正是 issue #59 报的问题）。请先把表格滚到目标行可见，再取值。
详细说明见 README 的 Limitations 一节。

如果方便，把 `table.table` 的输出和 Access Bridge Explorer 里表格节点的截图发我，
我可以给你更具体的代码。
