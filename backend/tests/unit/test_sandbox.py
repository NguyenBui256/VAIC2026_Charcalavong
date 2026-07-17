"""Unit tests for `SubprocessSandbox` (Story 2.6 T7.4, AC4/AC5, AR-14).

Exercises the REAL subprocess sandbox (no fakes) -- these are the mandatory
timeout / memory-breach / no-network / stdin-stdout tests from the Dev
Notes "Mandatory sandbox tests" section. The dev host here is Windows, so
the POSIX-only `resource.setrlimit` path is inactive and the cross-platform
`psutil` watchdog (see `app/core/adapters/sandbox.py`) is the active
enforcement mechanism (T3.5).
"""

from __future__ import annotations

import sys

from app.core.adapters.sandbox import SubprocessSandbox


def test_stdin_stdout_roundtrip() -> None:
    """Input via stdin, output read from stdout as JSON (AC4)."""
    code = (
        "import sys, json\n"
        "data = json.loads(sys.stdin.read())\n"
        "print(json.dumps({'doubled': data['n'] * 2}))\n"
    )
    result = SubprocessSandbox().run(code, stdin='{"n": 21}', timeout_s=5, memory_mb=64)
    assert not result.timed_out
    assert result.exit_code == 0
    assert result.output == {"doubled": 42}


def test_timeout_terminates_and_sets_timed_out() -> None:
    """A script that spins past the CPU/wall-clock cap is terminated (AC5)."""
    code = (
        "import time\n"
        "end = time.time() + 30\n"
        "while time.time() < end:\n"
        "    pass\n"
    )
    result = SubprocessSandbox().run(code, timeout_s=1, memory_mb=64)
    assert result.timed_out is True
    assert result.exit_code < 0


def test_memory_breach_is_killed_and_surfaces_as_violation() -> None:
    """A script allocating well past the memory cap is killed (AC5)."""
    code = (
        "chunks = []\n"
        "while True:\n"
        "    chunks.append(bytearray(10 * 1024 * 1024))\n"
    )
    result = SubprocessSandbox().run(code, timeout_s=10, memory_mb=32)
    assert result.exit_code < 0
    # Either the watchdog/rlimit flags it as a timeout-style kill or a
    # distinct negative exit -- both are "forcibly killed" per AR-14.
    assert result.output == {}


def test_no_network_egress_blocked() -> None:
    """An outbound socket attempt fails inside the sandbox (AR-14)."""
    code = (
        "import json\n"
        "try:\n"
        "    import socket\n"
        "    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)\n"
        "    s.connect(('example.com', 80))\n"
        "    print(json.dumps({'blocked': False}))\n"
        "except Exception as exc:\n"
        "    print(json.dumps({'blocked': True, 'error': str(exc)}))\n"
    )
    result = SubprocessSandbox().run(code, timeout_s=5, memory_mb=64)
    assert not result.timed_out
    assert result.output.get("blocked") is True


def test_fs_escape_via_open_blocked() -> None:
    """`open()` is disabled -- restricted builtins (AR-14)."""
    code = (
        "import json\n"
        "try:\n"
        "    open('C:/Windows/win.ini' if 'win' in __import__('sys').platform else '/etc/passwd')\n"
        "    print(json.dumps({'blocked': False}))\n"
        "except Exception as exc:\n"
        "    print(json.dumps({'blocked': True, 'error': str(exc)}))\n"
    )
    result = SubprocessSandbox().run(code, timeout_s=5, memory_mb=64)
    assert not result.timed_out
    assert result.output.get("blocked") is True


def test_uses_same_python_interpreter() -> None:
    """Sanity: the sandbox launches the same interpreter running the tests."""
    code = "import sys, json\nprint(json.dumps({'v': sys.version_info[0]}))\n"
    result = SubprocessSandbox().run(code, timeout_s=5, memory_mb=64)
    assert result.output.get("v") == sys.version_info[0]


def test_raw_socket_c_extension_blocked() -> None:
    """`import _socket` (raw C-extension) bypass is blocked (bypass #1)."""
    code = (
        "import json\n"
        "try:\n"
        "    import _socket\n"
        "    s = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)\n"
        "    s.connect(('example.com', 80))\n"
        "    print(json.dumps({'blocked': False}))\n"
        "except Exception as exc:\n"
        "    print(json.dumps({'blocked': True, 'error': str(exc)}))\n"
    )
    result = SubprocessSandbox().run(code, timeout_s=5, memory_mb=64)
    assert not result.timed_out
    assert result.output.get("blocked") is True


def test_ssl_c_extension_blocked() -> None:
    """`import _ssl` (raw C-extension) bypass is blocked (bypass #1)."""
    code = (
        "import json\n"
        "try:\n"
        "    import _ssl\n"
        "    print(json.dumps({'blocked': False}))\n"
        "except Exception as exc:\n"
        "    print(json.dumps({'blocked': True, 'error': str(exc)}))\n"
    )
    result = SubprocessSandbox().run(code, timeout_s=5, memory_mb=64)
    assert not result.timed_out
    assert result.output.get("blocked") is True


def test_importlib_import_module_bypass_blocked() -> None:
    """`importlib.import_module` bypasses `builtins.__import__` (bypass #2)."""
    code = (
        "import json\n"
        "try:\n"
        "    import importlib\n"
        "    socket = importlib.import_module('socket')\n"
        "    print(json.dumps({'blocked': False}))\n"
        "except Exception as exc:\n"
        "    print(json.dumps({'blocked': True, 'error': str(exc)}))\n"
    )
    result = SubprocessSandbox().run(code, timeout_s=5, memory_mb=64)
    assert not result.timed_out
    assert result.output.get("blocked") is True


def test_io_open_bypass_blocked() -> None:
    """`io.open` is a distinct binding from `builtins.open` (bypass #3)."""
    code = (
        "import json\n"
        "try:\n"
        "    import io\n"
        "    is_win = 'win' in __import__('sys').platform\n"
        "    win_p = 'C:/Windows/Temp/vaic_sandbox_test.txt'\n"
        "    path = win_p if is_win else '/tmp/vaic_sandbox_test.txt'\n"
        "    f = io.open(path, 'w')\n"
        "    print(json.dumps({'blocked': False}))\n"
        "except Exception as exc:\n"
        "    print(json.dumps({'blocked': True, 'error': str(exc)}))\n"
    )
    result = SubprocessSandbox().run(code, timeout_s=5, memory_mb=64)
    assert not result.timed_out
    assert result.output.get("blocked") is True


def test_ctypes_import_blocked() -> None:
    """`import ctypes` (could call libc/network directly) is blocked (probe)."""
    code = (
        "import json\n"
        "try:\n"
        "    import ctypes\n"
        "    print(json.dumps({'blocked': False}))\n"
        "except Exception as exc:\n"
        "    print(json.dumps({'blocked': True, 'error': str(exc)}))\n"
    )
    result = SubprocessSandbox().run(code, timeout_s=5, memory_mb=64)
    assert not result.timed_out
    assert result.output.get("blocked") is True


def test_harness_globals_not_leaked_to_user_code() -> None:
    """User code's globals() contains NO `__vaic_*` harness internals.

    The prelude runs in a separate namespace; user code is exec'd in a fresh
    globals dict, so harness internals (esp. the trusted `__vaic_socket`
    module) are unreachable by plain global-name reference (bypass #6).
    """
    code = (
        "import json\n"
        "leaked = sorted(n for n in globals() if n.startswith('__vaic'))\n"
        "print(json.dumps({'leaked': leaked}))\n"
    )
    result = SubprocessSandbox().run(code, timeout_s=5, memory_mb=64)
    assert not result.timed_out
    assert result.output.get("leaked") == []


def test_trusted_socket_global_leak_is_dead() -> None:
    """The exact live-egress repro via `__vaic_socket._socket` must NameError.

    Previously the harness's trusted pre-patch `socket` module leaked as the
    global `__vaic_socket`, and `__vaic_socket._socket` was the real unpatched
    C-extension -- a confirmed live network escape. With namespace isolation
    there is no such name to reach (bypass #6).
    """
    code = (
        "import json\n"
        "try:\n"
        "    raw = __vaic_socket._socket\n"
        "    s = raw.socket(raw.AF_INET, raw.SOCK_STREAM)\n"
        "    s.connect(('127.0.0.1', 9))\n"
        "    print(json.dumps({'blocked': False}))\n"
        "except NameError as exc:\n"
        "    print(json.dumps({'blocked': True, 'kind': 'NameError', 'error': str(exc)}))\n"
        "except Exception as exc:\n"
        "    print(json.dumps({'blocked': True, 'kind': type(exc).__name__, 'error': str(exc)}))\n"
    )
    result = SubprocessSandbox().run(code, timeout_s=5, memory_mb=64)
    assert not result.timed_out
    assert result.output.get("blocked") is True
    assert result.output.get("kind") == "NameError"


def test_socket_dunder_underscore_via_import_blocked() -> None:
    """Reaching `socket._socket` via any import path is blocked (bypass #6)."""
    code = (
        "import json\n"
        "try:\n"
        "    socket = __import__('socket')\n"
        "    raw = socket._socket\n"
        "    s = raw.socket(raw.AF_INET, raw.SOCK_STREAM)\n"
        "    s.connect(('127.0.0.1', 9))\n"
        "    print(json.dumps({'blocked': False}))\n"
        "except Exception as exc:\n"
        "    print(json.dumps({'blocked': True, 'error': str(exc)}))\n"
    )
    result = SubprocessSandbox().run(code, timeout_s=5, memory_mb=64)
    assert not result.timed_out
    assert result.output.get("blocked") is True


def test_gc_import_blocked() -> None:
    """`import gc` is blocked (belt-and-suspenders vs object-graph resurrection)."""
    code = (
        "import json\n"
        "try:\n"
        "    import gc\n"
        "    print(json.dumps({'blocked': False}))\n"
        "except Exception as exc:\n"
        "    print(json.dumps({'blocked': True, 'error': str(exc)}))\n"
    )
    result = SubprocessSandbox().run(code, timeout_s=5, memory_mb=64)
    assert not result.timed_out
    assert result.output.get("blocked") is True
