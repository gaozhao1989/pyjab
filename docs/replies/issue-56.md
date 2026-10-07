Still reproducing, and I now understand it better.

Two contributing causes:

1. After the first window is found, `_run_actor_sched()` is no longer called,
   so the Windows message pump stops. New top-level windows are announced
   through the message loop, so they can go unnoticed.
2. `wait_java_window_by_title` matches on title only, so a window with an
   empty or dynamic title is never matched.

For the Java Control Panel -> About repro specifically: the About dialog is a
modal child, not a new top-level window, so even a working pump may not make it
reachable by title. Searching through the existing driver with
`find_element_by_role("dialog")` is the more reliable route.

Fixing the pump is the top item in 1.3.0; I will re-test this exact repro then.
