Thanks for this, and apologies for the delay.

Your diagnosis in the thread was correct: every `find_element_by_*` walks the
entire accessibility tree from the root, and each node costs a cross-process
JAB call. When the element is *not* found in a large window, that is a lot of
wasted work -- which is why you saw high CPU only on failed lookups.

Two things you can do today:

1. **Narrow the search root.** Find a stable ancestor once, then search under
   it, rather than searching from the driver each time:

   ```python
   panel = driver.find_element_by_name("OrderPanel")
   button = panel.find_element_by_name("Submit")   # searches a subtree
   ```

2. **Do not wrap finds in `try/except` inside a polling loop.** Each failed
   attempt is a full traversal. Use
   `driver.wait_until_element_exist(By.NAME, "...", timeout=30)` instead -- it
   re-queries on a single path.

The real fix (pruning the traversal using the locator instead of walking
everything) is the top item in the 1.3.0 roadmap. I will post here when there
is something to test.
