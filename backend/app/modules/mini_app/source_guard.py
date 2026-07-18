"""Best-effort lexical guard on generated .tsx before it is built (sandbox).

This is NOT the security boundary — the sandboxed iframe + scoped token is
(see spec §7). This guard blocks the easy escapes in LLM/codegen output:
non-allowlisted imports and direct platform-reaching tokens. Layered
defense, mirroring core/adapters/sandbox.py's philosophy.
"""

from __future__ import annotations

import re

SAFE_IMPORTS = {"react", "./sdk"}
_IMPORT_RE = re.compile(r"""import\s+[^;]*?from\s+['"]([^'"]+)['"]""")
_BANNED = ("eval(", "new Function", "window.parent", "window.top",
           "window.opener", "document.cookie", "localStorage",
           "sessionStorage", "fetch(", "XMLHttpRequest", "import(")


class SourceGuardError(Exception):
    def __init__(self, token: str) -> None:
        super().__init__(f"generated source rejected: '{token}'")
        self.token = token


def assert_source_safe(tsx: str) -> None:
    for mod in _IMPORT_RE.findall(tsx):
        if mod not in SAFE_IMPORTS:
            raise SourceGuardError(f"import '{mod}'")
    for token in _BANNED:
        if token in tsx:
            raise SourceGuardError(token)
