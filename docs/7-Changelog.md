# Changelog

The full changelog lives in the repository, in
[`CHANGELOG.rst`](https://github.com/gaozhao1989/pyjab/blob/master/CHANGELOG.rst),
and is also shown on the GitHub release page for each version.

## Upgrading

```console
> pip install --upgrade pyjab
```

## Release history at a glance

| Version | What it was about |
|---|---|
| **1.3.0** | Rewrote the Windows message pump. A window or dialog opened after the first one is now noticed; `wait_until_element_exist()` no longer spins the CPU; the two leaked kernel event handles are gone. |
| **1.2.1** | Shipped `JABDriver.get_focused_element()`, contributed in 2022 but never released. |
| **1.2.0** | First release since 2022. Fixed Java Access Bridge DLL discovery on JDK 11+ — the DLL had moved from `%JAVA_HOME%\jre\bin` to `%JAVA_HOME%\bin`, so every modern JDK failed until you set `JAB_HOME` by hand. Removed the `pypiwin32`/`pywin32` dependency conflict. Migrated packaging to `pyproject.toml` and added CI. |
| 1.1.7 | Last release of the original series (May 2022). |

## Notable upgrade notes

### Upgrading to 1.3.0

* `Win32Utils.setup_msg_pump()` has been removed. It was an internal generator
  used to drive the message pump; use `Win32Utils.pump_messages()` if you were
  calling it directly.
* `pyjab.common.actorscheduler.ActorScheduler` is deprecated and unused. It is
  still importable, but nothing in pyjab uses it.
* `wait_until_element_exist()` takes a new `poll_interval` argument and now
  sleeps between attempts instead of spinning.

### Upgrading to 1.2.0

* If you were passing `bridge_dll=` or setting `JAB_HOME` purely as a workaround
  for the "DLL not found" error, you should no longer need to. Existing
  workarounds keep working.
* `setup.py` and `setup.cfg` were removed in favour of `pyproject.toml`. If any
  of your tooling called `python setup.py ...`, use `python -m build` instead.
* Python 3.12 users on 1.1.7 could not build from source at all, because
  `setup.py` imported `distutils`.
