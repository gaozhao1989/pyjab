Thanks for the report -- the crash you are seeing is the important part here,
and it is a real limitation rather than something you are doing wrong.

`_get_visible_children()` only returns the children the application reports as
visible. Your loop then indexes past that array while using `row * col` as the
upper bound, so it reads beyond the populated entries and touches stale or
invalid JAB object references. That is what destabilises the target process.

**Please bound the loop by the size of the array you actually got back**, and
only read what is on screen:

```python
children = table._get_visible_children()
count = len(children.children)          # do NOT assume row_count * col_count
for i in range(count):
    ...
```

For records scrolled out of view: JAB does not expose them, and trying to reach
them is exactly what crashes. Scroll the table so the target row is visible,
then query again. README now documents this under Limitations.

Automatic scrolling that respects visibility is on the 1.3.0 list (it is the
same problem as #15).
