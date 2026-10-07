Sorry for the very long delay on this one -- it is the oldest open issue here.

Your suggestion from back then was the right instinct, and I now have a better
answer to why it is hard: JAB exposes no scroll-position information, so there
is nothing to poll. `PropertyVisibleDataChange` fires, but it does not tell you
*where* the scrollbar ended up.

Practical approach I am planning for 1.3.0: compare the target element's
bounds against its scrollable parent's bounds, scroll by a bounded number of
steps, and re-check after each step -- exactly the algorithm you proposed. It
will be best-effort rather than exact, and it needs the parent to report valid
bounds.

In the meantime, `element.scroll(to_bottom=True, hold=N)` drives the scrollbar
via mouse actions and is the only tool available. If your list length is
unbounded, scroll in steps and re-query rather than trying to scroll to a
computed offset.
