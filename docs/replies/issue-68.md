This is expected behaviour rather than a bug in pyjab, though the failure mode
is unhelpful.

`simulate=True` sets the target window to the foreground with
`SetForegroundWindow`. Windows refuses that call when the process is not
attached to an interactive desktop session -- which is exactly how a Jenkins
agent usually runs (as a service, in session 0). Hence
`pywintypes.error: (0, 'SetForegroundWindow', 'No error message is available')`.

Two ways forward:

1. **Drop `simulate=True`.** The default (`simulate=False`) drives the control
   through the JAB accessibility action API and does not need the window in the
   foreground -- so it works fine from a service session. This is the right fix
   for most cases; `simulate=True` should only be used when the accessibility
   action is ignored by the application.
2. **Run the Jenkins agent interactively** (as a logged-in user, not a
   service) if you genuinely need real mouse input.

I am also going to make this fail with a clear message instead of a raw
`pywintypes.error` -- tracked for 1.3.0.
