# Support Packages

pyjab is small and leans on well-established libraries rather than
reimplementing them.

## [pywin32](https://github.com/mhammond/pywin32)

Windows API access from Python. pyjab uses it for the things Java Access Bridge
does not cover: enumerating windows, reading a window's process id, bringing a
window to the foreground, synthesising mouse and keyboard input, and window
geometry.

Only required on Windows — the dependency carries a `sys_platform == "win32"`
marker, so `pip install pyjab` does not request it on other platforms.

Note for anyone upgrading from 1.1.x: older releases declared **both**
`pypiwin32` and `pywin32`. `pypiwin32` is a deprecated shim that pins
`pywin32==223`, and having both made dependency resolution fail for every
released version. It was removed in 1.2.0.

## Standard library

pyjab uses `ctypes` to talk to `WindowsAccessBridge-64.dll`, and `pythoncom`
(from pywin32) to service the COM message queue that delivers Java Access Bridge
accessibility events.

## Development

Installing the test and release tooling:

```console
> pip install -e ".[dev]"
```

That adds more than a test runner, and the list is in one place —
`[project.optional-dependencies].dev` in `pyproject.toml`, which is what CI and the
release workflow install:

* `pytest` — the suite;
* `PyYAML` — the workflow checks need it, and **a guard that skips is not a guard**,
  so it is a dependency rather than an extra nobody installs;
* `tomli` — only below Python 3.11, where `tomllib` is not in the standard library;
* `build` and `twine` — the distribution and the upload;
* `pip-licenses` — the licence check;
* `uiautomation` — Windows only, for the UI Automation comparison the measurements
  are made against.

The GUI test suite drives a small Swing application that lives in `tests/java` and
is compiled on demand, so nothing is downloaded to run it.
