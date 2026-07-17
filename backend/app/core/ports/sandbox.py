"""SandboxPort -- hexagonal port for embedded Python tool execution.

Per consistency-conventions.md: "Embedded Python Tools -- Only when a Tool
can't be expressed as an MCP tool. Executes in a subprocess: no network,
restricted builtins, 10s CPU cap, 128 MB memory. Caller passes input via
stdin, reads stdout."

Implementation: ``core/adapters/sandbox.py`` (future story).
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field

__all__ = ["SandboxPort", "SandboxResult"]


class SandboxResult(BaseModel):
    """Result of a sandboxed Python execution."""

    stdout: str
    stderr: str = ""
    exit_code: int
    timed_out: bool = False
    truncated: bool = Field(
        default=False,
        description="True if stdout was truncated to the size ceiling",
    )
    output: dict[str, Any] = Field(
        default_factory=dict,
        description="Parsed JSON output if the script printed valid JSON",
    )


@runtime_checkable
class SandboxPort(Protocol):
    """Hexagonal port for embedded Python execution in a subprocess sandbox.

    Constraints (consistency-conventions.md):
    - No network egress.
    - Restricted builtins.
    - 10-second CPU cap.
    - 128 MB memory cap.
    - Input via stdin, output via stdout.
    """

    def run(
        self,
        code: str,
        stdin: str = "",
        *,
        timeout_s: int = 10,
        memory_mb: int = 128,
    ) -> SandboxResult:
        """Execute Python code in a sandboxed subprocess.

        Args:
            code: the Python source to execute.
            stdin: input passed to the script via stdin.
            timeout_s: CPU time cap (default 10s per convention).
            memory_mb: memory cap (default 128MB per convention).

        Returns:
            SandboxResult with stdout, stderr, exit code, and timeout flag.
        """
        ...
