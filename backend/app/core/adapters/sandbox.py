"""SubprocessSandbox — SandboxPort implementation (AR-14, Story 2.6 T3).

Embedded Python executes in a **child subprocess only** (never in-process,
never `eval`/`exec` on the caller's process):

- **No network egress** — the child harness monkeypatches `socket` to raise
  before user code runs, and blocks importing network/fs-escape modules
  (`socket`, `ssl`, `urllib*`, `http*`, `ftplib`, `smtplib`, `subprocess`,
  `os`, `ctypes`, ...). This is language-level restriction inside the child
  interpreter — it works identically on POSIX and Windows dev hosts, unlike
  OS-level network namespaces/seccomp (out of MVP scope per Dev Notes).
- **Restricted builtins** — `open` is disabled (no filesystem escape).
- **10s CPU cap / 128MB memory cap** — enforced two ways:
    1. POSIX: `resource.setrlimit(RLIMIT_CPU, ...)` / `RLIMIT_AS` via
       `preexec_fn` (hard OS-level kill on breach).
    2. Cross-platform (incl. Windows, where `resource` doesn't exist, per
       T3.5): a `psutil`-based watchdog thread polls the child's CPU time
       and RSS and terminates it on breach. This is the primary mechanism
       on Windows and a secondary belt-and-suspenders check on POSIX.
- **stdin in / stdout out only** — the Tool's input is written to the
  child's stdin; `SandboxResult.output` is parsed from stdout as JSON.
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

import psutil

from app.core.ports.sandbox import SandboxResult

__all__ = ["SubprocessSandbox"]

logger = logging.getLogger(__name__)

_IS_POSIX = sys.platform != "win32"

_STDOUT_MAX_BYTES = 64 * 1024  # truncation ceiling (SandboxResult.truncated)

_WATCHDOG_POLL_S = 0.1

# Modules that provide network egress or filesystem/process escape hatches —
# blocked at import time inside the child interpreter (AR-14 "restricted
# builtins" + "no network egress").
_BLOCKED_MODULES = frozenset(
    {
        "socket", "ssl", "select", "selectors", "asyncio",
        "urllib", "urllib2", "urllib3", "http", "httplib", "httpx",
        "requests", "ftplib", "smtplib", "telnetlib", "poplib", "imaplib",
        "subprocess", "multiprocessing", "os", "shutil", "ctypes",
        "socketserver", "xmlrpc", "webbrowser",
    }
)

# The harness prelude — injected before the Tool's own source. Disables
# network sockets + dangerous imports + filesystem writes, then runs the
# Tool's code with real stdin/stdout still wired through.
_HARNESS_PRELUDE = f"""
import builtins as __vaic_builtins

class _VaicSandboxViolation(OSError):
    pass

def __vaic_blocked(*_a, **_k):
    raise _VaicSandboxViolation(
        "network egress is disabled in the embedded-Python sandbox (AR-14)"
    )

import socket as __vaic_socket
__vaic_socket.socket = __vaic_blocked
__vaic_socket.create_connection = __vaic_blocked
__vaic_socket.getaddrinfo = __vaic_blocked

_VAIC_BLOCKED_MODULES = {_BLOCKED_MODULES!r}
__vaic_orig_import = __vaic_builtins.__import__

def __vaic_restricted_import(name, *args, **kwargs):
    top = name.split(".")[0]
    if top in _VAIC_BLOCKED_MODULES:
        raise ImportError(
            f"module '{{name}}' is blocked in the embedded-Python sandbox (AR-14)"
        )
    return __vaic_orig_import(name, *args, **kwargs)

__vaic_builtins.__import__ = __vaic_restricted_import
__vaic_builtins.open = __vaic_blocked

# --- Tool source begins ---
"""


def _build_script(code: str) -> str:
    """Wrap the Tool's embedded Python with the restricted-builtins harness."""
    return _HARNESS_PRELUDE + "\n" + code


def _posix_preexec(memory_mb: int, timeout_s: int):  # noqa: ANN202
    """Return a `preexec_fn` that applies POSIX rlimits, or None off-POSIX."""
    if not _IS_POSIX:
        return None

    import resource

    def _apply() -> None:
        mem_bytes = memory_mb * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))
        # +1s grace so our own watchdog (which also enforces this) wins the
        # race in the common case and can report a clean `timed_out=True`.
        resource.setrlimit(resource.RLIMIT_CPU, (timeout_s, timeout_s + 1))

    return _apply


class _Watchdog:
    """Cross-platform CPU-time / memory watchdog (T3.5 Windows fallback).

    Polls the child process via `psutil` and terminates it if it exceeds
    the CPU-time or memory cap. Runs on every platform as the primary
    enforcement mechanism on Windows and a secondary check on POSIX.
    """

    def __init__(self, pid: int, *, timeout_s: int, memory_mb: int) -> None:
        self._pid = pid
        self._timeout_s = timeout_s
        self._memory_bytes = memory_mb * 1024 * 1024
        self._stop = threading.Event()
        self.timed_out = False
        self.memory_violated = False
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=1)

    def _run(self) -> None:
        try:
            proc = psutil.Process(self._pid)
        except psutil.NoSuchProcess:
            return
        while not self._stop.is_set():
            try:
                if not proc.is_running():
                    return
                cpu_times = proc.cpu_times()
                cpu_used = cpu_times.user + cpu_times.system
                mem_used = proc.memory_info().rss
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                return
            if cpu_used > self._timeout_s:
                self.timed_out = True
                self._kill(proc)
                return
            if mem_used > self._memory_bytes:
                self.memory_violated = True
                self._kill(proc)
                return
            time.sleep(_WATCHDOG_POLL_S)

    @staticmethod
    def _kill(proc: psutil.Process) -> None:
        import contextlib

        with contextlib.suppress(psutil.NoSuchProcess, psutil.AccessDenied):
            proc.kill()


def _parse_output(stdout: str) -> dict:
    """Best-effort JSON parse of the last non-empty stdout line."""
    for line in reversed(stdout.strip().splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


class SubprocessSandbox:
    """`SandboxPort` implementation — subprocess-only embedded Python (AR-14)."""

    def run(
        self,
        code: str,
        stdin: str = "",
        *,
        timeout_s: int = 10,
        memory_mb: int = 128,
    ) -> SandboxResult:
        """Execute `code` in a sandboxed child subprocess.

        Wall-clock cutoff is `timeout_s + 2` (grace for interpreter startup);
        the CPU-time cap itself is enforced by rlimit (POSIX) and/or the
        watchdog (all platforms).
        """
        script = _build_script(code)
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as f:
            f.write(script)
            script_path = Path(f.name)

        try:
            return self._run_script(
                script_path, stdin, timeout_s=timeout_s, memory_mb=memory_mb
            )
        finally:
            script_path.unlink(missing_ok=True)

    def _run_script(
        self,
        script_path: Path,
        stdin: str,
        *,
        timeout_s: int,
        memory_mb: int,
    ) -> SandboxResult:
        preexec_fn = _posix_preexec(memory_mb, timeout_s)
        proc = subprocess.Popen(  # noqa: S603 -- fixed interpreter, sandboxed script
            [sys.executable, str(script_path)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            preexec_fn=preexec_fn,
        )

        watchdog = _Watchdog(proc.pid, timeout_s=timeout_s, memory_mb=memory_mb)
        watchdog.start()

        wall_clock_cap = timeout_s + 2
        try:
            stdout, stderr = proc.communicate(input=stdin, timeout=wall_clock_cap)
            wall_timed_out = False
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout, stderr = proc.communicate()
            wall_timed_out = True
        finally:
            watchdog.stop()

        timed_out = wall_timed_out or watchdog.timed_out
        truncated = len(stdout.encode("utf-8", errors="ignore")) > _STDOUT_MAX_BYTES
        if truncated:
            stdout = stdout[:_STDOUT_MAX_BYTES]

        # -9 is a sentinel "forcibly killed by the sandbox" exit code (mirrors
        # SIGKILL) distinct from a normal (positive) script failure exit code.
        # Callers (tool_service) treat `timed_out or exit_code < 0` as a
        # violation (AC5) -- both timeout and memory-breach map here.
        forced_kill = timed_out or watchdog.memory_violated
        exit_code = -9 if forced_kill else (proc.returncode if proc.returncode is not None else -1)

        output = {} if forced_kill else _parse_output(stdout)

        return SandboxResult(
            stdout=stdout,
            stderr=stderr,
            exit_code=exit_code,
            timed_out=timed_out,
            truncated=truncated,
            output=output,
        )
