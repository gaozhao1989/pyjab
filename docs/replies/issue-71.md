Confirmed -- there is no double-click API. What I suggested at the time (call
`click()` twice) works, but only if the two clicks land within the system
double-click interval, which is fragile:

```python
element.click()
element.click()      # may be treated as two single clicks
```

The reliable route today is a real mouse double-click via `win32api`, which
needs valid bounds:

```python
import win32api, win32con
b = element.bounds
if b["width"] > 0 and b["height"] > 0:
    x, y = b["x"] + b["width"] // 2, b["y"] + b["height"] // 2
    win32api.SetCursorPos((x, y))
    for _ in range(2):
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0)
```

Note this needs the window in the foreground, and it will not work when the
element reports `bounds = -1` (common for table cells).

Adding `click(double=True)` and a right-click alongside it is on the 1.3.0
list -- it is a small, well-understood change.
