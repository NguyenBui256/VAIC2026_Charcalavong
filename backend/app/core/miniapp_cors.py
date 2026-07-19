"""Scoped CORS handling for the Mini-App sandboxed-iframe data plane.

WHY `Origin: null` needs a special path: the generated Mini-App renders in
an iframe with `sandbox="allow-scripts allow-forms"` and deliberately NO
`allow-same-origin`. That gives the iframe document an OPAQUE origin, so
every `fetch()` the mini-app `sdk.ts` issues to `/apps/{app_id}/rows*`
sends `Origin: null`. The platform's global `CORSMiddleware` (see
`app/main.py`) is a fixed allow-list of explicit origins and will never
match `"null"`, so browsers block all row reads/writes from the mini-app.

WHY it is SAFE to allow: auth on the mini-app data-plane routes is a
BEARER TOKEN (`Authorization: Bearer <scoped JWT>`), not a cookie or any
other ambient credential. CORS exists to protect cookie-based/ambient
auth flows from cross-site reads; it is not the security boundary for
bearer-token APIs — a page can only succeed if it already possesses the
scoped token. So granting `Origin: null` CORS access here does not
introduce CSRF or a new attack surface. We still scope this as tightly
as possible: only `/apps/{app_id}/rows` (+ subpaths) get the null-origin
exemption; the global allow-list and every other route are untouched.

This is a plain ASGI middleware (not `BaseHTTPMiddleware`) so it can
short-circuit CORS preflight `OPTIONS` requests *before* `AuthMiddleware`
runs — preflight requests are unauthenticated by spec, so AuthMiddleware
would otherwise 401 them. It must be mounted OUTERMOST, i.e. added via
`app.add_middleware()` AFTER both `AuthMiddleware` and the global
`CORSMiddleware`, so it is the first thing to see the request.
"""

from __future__ import annotations

import re
from typing import Any, Awaitable, Callable, MutableMapping

from starlette.responses import Response
from starlette.types import Receive, Scope, Send

__all__ = ["MiniAppNullOriginCORSMiddleware"]

# Matches /apps/{app_id}/rows and /apps/{app_id}/files (or any deeper subpath)
# — the mini-app row CRUD data plane AND the `file` field upload/download plane,
# both registered on `mini_app_rows_router` in `app/modules/mini_app/routes.py`.
# The sandboxed iframe (Origin: null) calls both, so both need the null-origin
# CORS grant.
_MINI_APP_ROWS_PATH = re.compile(r"^/apps/[^/]+/(?:rows|files)(?:/.*)?$")

_ALLOW_METHODS = "GET, POST, PATCH, DELETE, OPTIONS"
_ALLOW_HEADERS = "authorization, content-type"
_MAX_AGE = "600"


def _is_miniapp_rows_path(path: str) -> bool:
    return bool(_MINI_APP_ROWS_PATH.match(path))


class MiniAppNullOriginCORSMiddleware:
    """Grants `Origin: null` CORS access, scoped to mini-app row routes.

    No-ops for every other request (different origin, or a path outside
    `/apps/{app_id}/rows*`) — those fall through unchanged to the existing
    `AuthMiddleware` + global `CORSMiddleware` stack.
    """

    def __init__(self, app: Callable[[Scope, Receive, Send], Awaitable[None]]) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers: MutableMapping[bytes, bytes] = dict(scope.get("headers") or [])
        origin = headers.get(b"origin")
        path = scope.get("path", "")

        if origin != b"null" or not _is_miniapp_rows_path(path):
            await self.app(scope, receive, send)
            return

        if scope["method"] == "OPTIONS":
            # Preflight — answer directly. This bypasses AuthMiddleware and
            # the global CORSMiddleware entirely, since neither should ever
            # see (or need to authenticate) a preflight request.
            response = Response(status_code=200)
            response.headers["Access-Control-Allow-Origin"] = "null"
            response.headers["Access-Control-Allow-Methods"] = _ALLOW_METHODS
            response.headers["Access-Control-Allow-Headers"] = _ALLOW_HEADERS
            response.headers["Access-Control-Max-Age"] = _MAX_AGE
            # No Access-Control-Allow-Credentials: these routes use bearer
            # tokens, not cookies, so credentialed CORS is unnecessary.
            await response(scope, receive, send)
            return

        # Actual GET/POST/PATCH/DELETE — let the real request flow through
        # normal auth + routing, then stamp the CORS header onto the
        # response on the way back out.
        async def send_wrapper(message: dict[str, Any]) -> None:
            if message["type"] == "http.response.start":
                raw_headers = list(message.get("headers", []))
                raw_headers.append((b"access-control-allow-origin", b"null"))
                message = {**message, "headers": raw_headers}
            await send(message)

        await self.app(scope, receive, send_wrapper)
