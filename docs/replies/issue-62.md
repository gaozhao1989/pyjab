This is an excellent diagnosis and you are right on both counts.

Confirmed: pyjab never declares DPI awareness and never converts JAB's logical
coordinates to physical ones. On a display at 125% or 150% scaling,
`simulate=True` therefore moves the cursor to the wrong place. The
`PROCESS_PER_MONITOR_DPI_AWARE` detail you identified is the missing piece.

Plan for 1.3.0:

1. declare per-monitor DPI awareness for the pyjab process, and
2. convert logical -> physical coordinates before calling
   `SetCursorPos` / `SendInput`, using the target window's DPI.

Both need a Windows machine with scaling set to 125%/150% to verify -- I am
setting that up. In the meantime, the escape hatch is to mark the *target*
application as DPI aware (which is what makes its bounds physical), or to run
at 100% scaling.

If you still have the environment where you found this, I would very much like
your help verifying the fix when it is ready.
