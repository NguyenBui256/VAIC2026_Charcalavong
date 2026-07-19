"""SubprocessSandbox — SandboxPort implementation (AR-14, Story 2.6 T3).

Embedded Python executes in a **child subprocess only** (never in-process,
never `eval`/`exec` on the caller's process).

**SECURITY DISCLAIMER — READ BEFORE RELYING ON THIS FOR UNTRUSTED CODE**

This is **best-effort, language-level isolation** achieved by monkeypatching
dangerous builtins/modules and blocking known-dangerous imports *inside the
same OS process* as the interpreter running the Tool's code. It is **NOT a
hard security boundary**. A determined attacker with arbitrary Python
execution inside the child interpreter has many potential avenues to defeat
purely language-level restrictions (e.g. reaching blocked functionality via
attribute introspection, `__builtins__` manipulation, `os.fork`/`ctypes`-free
syscalls, C-extension modules we haven't enumerated, or bugs in this harness
itself). Treat embedded-Python Tools as **semi-trusted, builder-authored
code**, not as isolation from a malicious/adversarial author. Real,
defense-in-depth isolation for genuinely untrusted code REQUIRES OS-level
sandboxing — a container with a dropped/firewalled network namespace,
seccomp-bpf syscall filtering, or a network-namespace-scoped child process —
which is explicitly **out of scope for this MVP** and deferred to a future
story.

What this harness DOES do, best-effort:
- **Import blocking** — blocks importing a broad set of network/fs/process
  escape modules by name (`socket`, `_socket`, `ssl`, `_ssl`, `urllib*`,
  `http*`, `ftplib`, `smtplib`, `subprocess`, `os`, `ctypes`, `_ctypes`,
  `importlib`, ...), intercepting both `builtins.__import__` AND
  `importlib.import_module` so the latter can't bypass the former.
- **Socket monkeypatching** — `socket.socket`/`create_connection`/
  `getaddrinfo` raise before user code runs (belt-and-suspenders on top of
  the import block, in case a module is already resolvable via `sys.modules`
  aliasing).
- **Filesystem write/read denial** — both `builtins.open` and `io.open` are
  disabled (they are distinct bindings; patching only one leaves a bypass).
- **Isolated interpreter flags** — the child runs with `-S` (skip `site`)
  and `-I` (isolated mode: ignores `PYTHONPATH`/env, blocks `sys.path`
  user-site injection) to reduce ambient attack surface.
- **10s CPU cap / 128MB memory cap** — enforced two ways:
    1. POSIX: `resource.setrlimit(RLIMIT_CPU, ...)` / `RLIMIT_AS` via
       `preexec_fn` (hard OS-level kill on breach).
    2. Cross-platform (incl. Windows, where `resource` doesn't exist, per
       T3.5): a `psutil`-based watchdog thread polls the child's CPU time
       and RSS and terminates it on breach. This is the primary mechanism
       on Windows and a secondary belt-and-suspenders check on POSIX.
- **stdin in / stdout out only** — the Tool's input is written to the
  child's stdin; `SandboxResult.output` is parsed from stdout as JSON.
- **Harness/user namespace isolation** — the harness prelude runs in its own
  scope; the Tool's source is exec'd in a FRESH globals dict holding only a
  locked-down `__builtins__` and `__name__`. No `__vaic_*` harness internal
  (and no trusted pre-patch module object — e.g. the `socket` module and its
  real `_socket` C-extension) is reachable from user code by global name.
  This closes a confirmed live-egress escape where those internals leaked as
  plain globals when prelude + user code shared one `__main__` namespace.

RESIDUAL RISK (still real — this is best-effort, NOT a hard boundary):
Namespace isolation and import blocking remove the *easy* named-reference
escapes, but a determined author can still attempt to reach blocked
functionality through pure-Python object-graph introspection — e.g. walking
`object.__subclasses__()` / frame or traceback objects to rediscover an
already-loaded dangerous class. `gc` is now blocked to raise the bar against
object resurrection, but such introspection is not fully preventable at the
language level. Genuinely untrusted code REQUIRES OS-level isolation (see
below); treat embedded-Python Tools as semi-trusted, builder-authored code.
"""

from __future__ import annotations

import base64
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
# builtins" + "no network egress"). Includes underscore C-extension modules
# (`_socket`, `_ssl`, `_ctypes`) which are never touched by the
# `socket.socket = ...` monkeypatch below, plus the `importlib` family which
# can load a blocked module without going through `builtins.__import__`.
_BLOCKED_MODULES = frozenset(
    {
        "socket", "_socket", "ssl", "_ssl", "select", "selectors", "asyncio",
        "urllib", "urllib2", "urllib3", "http", "httplib", "httpx",
        "requests", "ftplib", "smtplib", "telnetlib", "poplib", "imaplib",
        "subprocess", "multiprocessing", "os", "shutil", "ctypes", "_ctypes",
        "socketserver", "xmlrpc", "webbrowser",
        "importlib", "pkgutil", "runpy", "zipimport",
        "gc",
    }
)

# The harness prelude — injected before the Tool's own source. Disables
# network sockets + dangerous imports (via both `__import__` and
# `importlib.import_module`) + filesystem read/write (both `open` bindings),
# then runs the Tool's code with real stdin/stdout still wired through.
#
# NOTE: this is best-effort language-level hardening, not a hard security
# boundary -- see the module docstring's SECURITY DISCLAIMER.
_HARNESS_PRELUDE = f"""
import builtins as __vaic_builtins
import sys as __vaic_sys

class _VaicSandboxViolation(OSError):
    pass

def __vaic_blocked(*_a, **_k):
    raise _VaicSandboxViolation(
        "network egress / filesystem / dangerous-import is disabled in the "
        "embedded-Python sandbox (AR-14)"
    )

# Patch socket internals before installing the import guard below (this
# `import socket` call is trusted harness code, run before user code).
import socket as __vaic_socket
__vaic_socket.socket = __vaic_blocked
__vaic_socket.create_connection = __vaic_blocked
__vaic_socket.getaddrinfo = __vaic_blocked

_VAIC_BLOCKED_MODULES = {_BLOCKED_MODULES!r}

def __vaic_check_blocked(name):
    top = name.split(".")[0]
    if top in _VAIC_BLOCKED_MODULES:
        raise ImportError(
            f"module '{{name}}' is blocked in the embedded-Python sandbox (AR-14)"
        )

__vaic_orig_import = __vaic_builtins.__import__

def __vaic_restricted_import(name, *args, **kwargs):
    __vaic_check_blocked(name)
    return __vaic_orig_import(name, *args, **kwargs)

__vaic_builtins.__import__ = __vaic_restricted_import

# `importlib.import_module` (and `importlib.__import__`) do NOT route
# through `builtins.__import__` -- guard them directly so they can't be
# used to bypass the block above. `importlib` itself is also in the
# blocklist, so a fresh `import importlib` is already denied; this extra
# guard covers the case where `importlib` is already resolvable via
# `sys.modules` before this prelude runs.
if "importlib" in __vaic_sys.modules:
    __vaic_importlib = __vaic_sys.modules["importlib"]
    __vaic_importlib.import_module = __vaic_blocked
    if hasattr(__vaic_importlib, "__import__"):
        __vaic_importlib.__import__ = __vaic_blocked

# Purge already-imported dangerous modules from the cache so user code can't
# fetch a live reference via `sys.modules[...]` directly (bypassing both
# guards above).
for __vaic_mod_name in list(__vaic_sys.modules):
    if __vaic_mod_name.split(".")[0] in _VAIC_BLOCKED_MODULES:
        del __vaic_sys.modules[__vaic_mod_name]

__vaic_builtins.open = __vaic_blocked

# `io.open` is a distinct binding from `builtins.open` -- patch it too, or
# filesystem read/write remains reachable via `io.open(...)`.
import io as __vaic_io
__vaic_io.open = __vaic_blocked
"""


# Isolated-execution footer. Runs the Tool's source in a FRESH globals dict
# that contains ONLY a locked-down `__builtins__` (the same in-place-patched
# `builtins` module the prelude hardened) and `__name__`. None of the
# `__vaic_*` harness internals -- crucially the trusted pre-patch `socket`
# module bound to `__vaic_socket`, whose `._socket` was the real unpatched
# C-extension -- are reachable from user code by any global name. This closes
# the global-leak network escape that existed when prelude + user code shared
# one `__main__` namespace.
#
# The user source is carried as a base64 blob (assigned by `_build_script`
# between prelude and footer) so no user content is interpolated into any
# f-string. Not an f-string here -> `{}` are literal dict syntax.
_HARNESS_EXEC_FOOTER = """
__vaic_user_source = __vaic_base64.b64decode(__vaic_user_code_b64).decode("utf-8")
__vaic_user_globals = {"__name__": "__main__", "__builtins__": __vaic_builtins}
exec(compile(__vaic_user_source, "<tool>", "exec"), __vaic_user_globals)
"""


def _build_script(code: str) -> str:
    """Wrap the Tool's embedded Python with the restricted-builtins harness.

    The Tool's source is base64-encoded and exec'd in a separate globals dict
    (see `_HARNESS_EXEC_FOOTER`) so harness internals never leak to user code.
    """
    encoded = base64.b64encode(code.encode("utf-8")).decode("ascii")
    user_code_line = (
        "\nimport base64 as __vaic_base64\n"
        f"__vaic_user_code_b64 = {encoded!r}\n"
    )
    return _HARNESS_PRELUDE + user_code_line + _HARNESS_EXEC_FOOTER


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
        # -S: skip importing `site` (fewer ambient imports/sys.path entries).
        # -I: isolated mode (implies -E -P -s: ignores PYTHONPATH/PYTHONHOME
        # and other env vars, disables user site-packages). Both reduce the
        # child's ambient attack surface; neither is a substitute for OS-level
        # isolation (see module docstring).
        proc = subprocess.Popen(  # noqa: S603 -- fixed interpreter, sandboxed script
            [sys.executable, "-S", "-I", str(script_path)],
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
