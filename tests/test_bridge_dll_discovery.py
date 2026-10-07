"""Unit tests for Java Access Bridge DLL discovery.

These tests are intentionally platform independent: they exercise pure path
resolution and never load a DLL, so they run on Linux, macOS and Windows alike.

Regression context
------------------
Before 1.2.0 the only paths ever probed were derived from ``%JAVA_HOME%\\jre``
and friends.  JDK 11 removed the bundled ``jre`` directory, so the DLL moved to
``%JAVA_HOME%\\bin`` and every JDK 11+ user hit "WindowsAccessBridge dll not
found".  ``test_java_home_bin_is_probed_before_jre_bin`` and
``test_find_bridge_dll_in_java_home_bin`` pin the new behaviour.
"""

import os
from pathlib import Path

import pytest

import pyjab.config as config


@pytest.fixture(autouse=True)
def hermetic_discovery(monkeypatch):
    """Never let a test scan the real machine's install locations."""
    monkeypatch.setattr(config, "_PROGRAM_ROOTS", ())
    for var in config._HOME_ENV_VARS:
        monkeypatch.delenv(var, raising=False)


def _make_dll(directory: Path, dll_bit: int) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    dll = directory / config.WAB_DLL.format(dll_bit)
    dll.write_bytes(b"")
    return dll


# ---------------------------------------------------------------------------
# Bitness
# ---------------------------------------------------------------------------

def test_get_dll_bit_is_32_or_64():
    assert config.get_dll_bit() in (32, 64)


def test_get_dll_bit_matches_interpreter_pointer_size():
    import struct

    assert config.get_dll_bit() == struct.calcsize("P") * 8


# ---------------------------------------------------------------------------
# Search order
# ---------------------------------------------------------------------------

def test_java_home_bin_is_probed_before_jre_bin(tmp_path, monkeypatch):
    """JDK 11+ layout must be tried first; JDK 8-10 layout second."""
    monkeypatch.setenv("JAVA_HOME", str(tmp_path))

    dirs = config.get_bridge_dll_search_dirs()

    assert dirs[0] == tmp_path / "bin"
    assert dirs[1] == tmp_path / "jre" / "bin"


def test_jab_home_contributes_a_flat_directory(tmp_path, monkeypatch):
    monkeypatch.setenv("JAB_HOME", str(tmp_path))

    assert tmp_path in config.get_bridge_dll_search_dirs()


def test_quoted_java_home_is_tolerated(tmp_path, monkeypatch):
    """Environment values are often stored with surrounding quotes."""
    monkeypatch.setenv("JAVA_HOME", f'"{tmp_path}"')

    assert tmp_path / "bin" in config.get_bridge_dll_search_dirs()


def test_java_home_that_does_not_exist_is_ignored(tmp_path, monkeypatch):
    monkeypatch.setenv("JAVA_HOME", str(tmp_path / "does-not-exist"))

    assert config.get_bridge_dll_search_dirs() == []


def test_search_dirs_are_not_duplicated(tmp_path, monkeypatch):
    """JAVA_HOME and JDK_HOME pointing at the same place must not double up."""
    monkeypatch.setenv("JAVA_HOME", str(tmp_path))
    monkeypatch.setenv("JDK_HOME", str(tmp_path))

    dirs = config.get_bridge_dll_search_dirs()
    lowered = [str(d).lower() for d in dirs]

    assert len(lowered) == len(set(lowered))


@pytest.mark.parametrize("dll_bit", [32, 64])
def test_candidates_use_the_requested_bitness(tmp_path, monkeypatch, dll_bit):
    monkeypatch.setenv("JAVA_HOME", str(tmp_path))

    candidates = config.get_bridge_dll_candidates(dll_bit)

    assert candidates, "expected at least one candidate"
    assert all(c.name == config.WAB_DLL.format(dll_bit) for c in candidates)


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------

def test_find_bridge_dll_in_java_home_bin(tmp_path, monkeypatch):
    """The JDK 11+ location -- this is the fix for the JDK 16+ issue."""
    monkeypatch.setenv("JAVA_HOME", str(tmp_path))
    dll = _make_dll(tmp_path / "bin", 64)

    assert config.find_bridge_dll(64) == dll


def test_find_bridge_dll_in_legacy_jre_bin(tmp_path, monkeypatch):
    """The JDK 8-10 location must keep working."""
    monkeypatch.setenv("JAVA_HOME", str(tmp_path))
    dll = _make_dll(tmp_path / "jre" / "bin", 64)

    assert config.find_bridge_dll(64) == dll


def test_find_bridge_dll_in_jab_home(tmp_path, monkeypatch):
    monkeypatch.setenv("JAB_HOME", str(tmp_path))
    dll = _make_dll(tmp_path, 64)

    assert config.find_bridge_dll(64) == dll


def test_find_bridge_dll_respects_bitness(tmp_path, monkeypatch):
    """A 32-bit DLL must never satisfy a 64-bit request."""
    monkeypatch.setenv("JAVA_HOME", str(tmp_path))
    dll32 = _make_dll(tmp_path / "bin", 32)

    assert config.find_bridge_dll(64) is None
    assert config.find_bridge_dll(32) == dll32


def test_find_bridge_dll_falls_back_to_recursive_search(tmp_path, monkeypatch):
    """Non-standard layouts are still found by the bounded recursive search."""
    monkeypatch.setenv("JAVA_HOME", str(tmp_path))
    dll = _make_dll(tmp_path / "lib" / "nested", 64)

    assert config.find_bridge_dll(64) == dll


def test_find_bridge_dll_returns_none_when_absent(tmp_path, monkeypatch):
    monkeypatch.setenv("JAVA_HOME", str(tmp_path))

    assert config.find_bridge_dll(64) is None


def test_find_bridge_dll_ignores_a_directory_with_the_dll_name(tmp_path, monkeypatch):
    """A directory named like the DLL is not a match."""
    monkeypatch.setenv("JAVA_HOME", str(tmp_path))
    (tmp_path / "bin" / config.WAB_DLL.format(64)).mkdir(parents=True)

    assert config.find_bridge_dll(64) is None


# ---------------------------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------------------------

def test_describe_reports_the_requested_filename_and_env_vars(monkeypatch):
    message = config.describe_bridge_dll_search(64)

    assert "WindowsAccessBridge-64.dll" in message
    assert "JAVA_HOME" in message
    assert "(not set)" in message
    assert "How to fix" in message
    assert "JABDriver" in message


def test_describe_flags_a_wrong_bitness_dll(tmp_path, monkeypatch):
    """Finding only the other architecture is a confusing failure -- call it out."""
    monkeypatch.setenv("JAVA_HOME", str(tmp_path))
    other_bit = 32 if config.get_dll_bit() == 64 else 64
    _make_dll(tmp_path / "bin", other_bit)

    message = config.describe_bridge_dll_search()

    assert f"found a {other_bit}-bit DLL instead" in message
    assert str(tmp_path / "bin") in message


def test_describe_lists_probed_directories(tmp_path, monkeypatch):
    monkeypatch.setenv("JAVA_HOME", str(tmp_path))

    message = config.describe_bridge_dll_search(64)

    assert str(tmp_path / "bin") in message


def test_describe_handles_no_environment_at_all():
    """Must not raise when nothing at all is configured."""
    message = config.describe_bridge_dll_search()

    assert "could not be located" in message


# ---------------------------------------------------------------------------
# Backwards compatibility
# ---------------------------------------------------------------------------

def test_legacy_module_constants_are_preserved():
    """Other code and downstream users import these; keep them working."""
    assert config.MAX_STRING_SIZE == 1024
    assert config.SHORT_STRING_SIZE == 256
    assert config.MAX_KEY_BINDINGS == 50
    assert config.MAX_RELATION_TARGETS == 25
    assert config.MAX_RELATIONS == 5
    assert config.MAX_ACTION_INFO == 256
    assert config.MAX_ACTIONS_TO_DO == 32
    assert config.MAX_VISIBLE_CHILDREN == 256
    assert config.TIMEOUT == 30
    assert config.WAB_DLL == "WindowsAccessBridge-{}.dll"
    assert config.JDK_BRIDGE_DLL.endswith("WindowsAccessBridge-{}.dll")
    assert config.JRE_BRIDGE_DLL.endswith("WindowsAccessBridge-{}.dll")
    assert config.JAB_BRIDGE_DLL.endswith("WindowsAccessBridge-{}.dll")


def test_accessibility_properties_constants_are_preserved():
    assert config.A11Y_PROPS_PATH.endswith(".accessibility.properties")
    assert "AccessBridge" in config.A11Y_PROPS_CONTENT


# ---------------------------------------------------------------------------
# Service integration
# ---------------------------------------------------------------------------

def test_service_prefers_an_explicit_dll_path(tmp_path, monkeypatch):
    """An explicit bridge_dll argument wins over automatic discovery."""
    from pyjab.common import service as service_module

    monkeypatch.setattr(service_module, "A11Y_PROPS_PATH", str(tmp_path / "a11y.props"))
    monkeypatch.setenv("JAVA_HOME", str(tmp_path / "java"))

    dll = _make_dll(tmp_path / "custom", 64)
    # Bypass the @singleton cache so monkeypatching takes effect.
    svc = service_module.Service.__wrapped__()

    assert svc.find_bridge_dll(str(dll)) == dll


def test_service_falls_back_when_explicit_path_is_missing(tmp_path, monkeypatch):
    from pyjab.common import service as service_module

    monkeypatch.setattr(service_module, "A11Y_PROPS_PATH", str(tmp_path / "a11y.props"))
    monkeypatch.setenv("JAVA_HOME", str(tmp_path / "java"))
    discovered = _make_dll(tmp_path / "java" / "bin", 64)

    svc = service_module.Service.__wrapped__()

    assert svc.find_bridge_dll(str(tmp_path / "nope.dll")) == discovered


def test_service_reports_none_when_nothing_is_found(tmp_path, monkeypatch):
    from pyjab.common import service as service_module

    monkeypatch.setattr(service_module, "A11Y_PROPS_PATH", str(tmp_path / "a11y.props"))
    monkeypatch.setenv("JAVA_HOME", str(tmp_path / "java"))

    svc = service_module.Service.__wrapped__()

    assert svc.find_bridge_dll() is None


def test_load_library_raises_an_actionable_error(tmp_path, monkeypatch):
    """The failure message must tell the user how to fix it, not just fail."""
    from pyjab.common import service as service_module

    monkeypatch.setattr(service_module, "A11Y_PROPS_PATH", str(tmp_path / "a11y.props"))
    monkeypatch.setenv("JAVA_HOME", str(tmp_path / "java"))

    svc = service_module.Service.__wrapped__()

    with pytest.raises(FileNotFoundError) as excinfo:
        svc.load_library()

    message = str(excinfo.value)
    assert "could not be located" in message
    assert "How to fix" in message
