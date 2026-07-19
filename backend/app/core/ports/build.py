"""BuildPort — bundles a generated mini-app component into a static asset set.

Protocol for the sandbox build plane (story 4-5): takes the codegen'd TSX
source for a mini-app and produces a browser-loadable `bundle.js` +
`index.html` pair in `out_dir`.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel


class BuildResult(BaseModel):
    ok: bool
    bundle_path: str | None = None
    error: str = ""


@runtime_checkable
class BuildPort(Protocol):
    def build(
        self,
        app_id: str,
        tsx_source: str,
        out_dir: str,
        *,
        timeout_s: int = 60,
        memory_mb: int = 512,
    ) -> BuildResult: ...
