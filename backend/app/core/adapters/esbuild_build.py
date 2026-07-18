"""EsbuildBuild — BuildPort adapter (sandbox build plane, story 4-5).

Runs the frontend-vendored `esbuild` binary in an isolated per-app workdir
under a wall-clock timeout. The generated component is written as app.tsx
alongside the vendored runtime template (entry.tsx/sdk.ts/index.html).
Output: bundle.js + index.html in out_dir. A failed/timed-out build returns
ok=False (never raises into the worker) so one bad app can't take down the
platform.

React resolution: esbuild resolves bare imports (`react`, `react-dom/client`)
by walking UP from the importing file's directory looking for `node_modules`.
Building in an OS temp dir outside the repo would leave `react` unresolved
(the adapter can't rely on `--packages=external`/CDN — the iframe CSP blocks
external hosts, so react must be bundled IN). To make resolution work while
still keeping each build isolated, the per-app workdir is created UNDER the
frontend tree, at `frontend/.miniapp-build/<app_id>/`, so esbuild's upward
node_modules walk finds `frontend/node_modules/react` two levels up. The
resulting bundle.js + index.html are then copied into the real `out_dir` and
the workdir is removed, regardless of outcome.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from app.core.ports.build import BuildResult

_TEMPLATE = Path(__file__).resolve().parents[2] / "modules" / "mini_app" / "runtime_template"
_FRONTEND = Path(__file__).resolve().parents[4] / "frontend"
_BUILD_ROOT = _FRONTEND / ".miniapp-build"


def _esbuild_binary() -> Path:
    """Locate the esbuild binary vendored in frontend/node_modules/.bin.

    Windows ships esbuild.cmd (or esbuild.exe on some installs); POSIX ships
    the extensionless `esbuild` shell shim.
    """
    bin_dir = _FRONTEND / "node_modules" / ".bin"
    for name in ("esbuild.cmd", "esbuild.exe", "esbuild"):
        candidate = bin_dir / name
        if candidate.exists():
            return candidate
    # Fall back to the extensionless name; subprocess/shutil.which can still
    # resolve it via PATH-style lookup on some platforms.
    return bin_dir / "esbuild"


class EsbuildBuild:
    def build(
        self,
        app_id: str,
        tsx_source: str,
        out_dir: str,
        *,
        timeout_s: int = 60,
        memory_mb: int = 512,
    ) -> BuildResult:
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)

        work = _BUILD_ROOT / app_id
        try:
            if work.exists():
                shutil.rmtree(work)
            work.mkdir(parents=True, exist_ok=True)

            for name in ("entry.tsx", "sdk.ts"):
                shutil.copy(_TEMPLATE / name, work / name)
            (work / "app.tsx").write_text(tsx_source, encoding="utf-8")

            esbuild = _esbuild_binary()
            try:
                proc = subprocess.run(  # noqa: S603 -- fixed args, sandboxed inputs
                    [
                        str(esbuild),
                        "entry.tsx",
                        "--bundle",
                        "--loader:.tsx=tsx",
                        "--jsx=automatic",
                        "--outfile=bundle.js",
                    ],
                    cwd=work,
                    capture_output=True,
                    text=True,
                    timeout=timeout_s,
                )
            except subprocess.TimeoutExpired:
                return BuildResult(ok=False, error="build timed out")
            except OSError as exc:
                return BuildResult(ok=False, error=f"failed to launch esbuild: {exc}")

            if proc.returncode != 0:
                return BuildResult(ok=False, error=(proc.stderr or proc.stdout)[-2000:])

            bundle = work / "bundle.js"
            if not bundle.exists():
                return BuildResult(ok=False, error="esbuild reported success but bundle.js is missing")

            shutil.copy(bundle, out / "bundle.js")
            shutil.copy(_TEMPLATE / "index.html", out / "index.html")
        finally:
            shutil.rmtree(work, ignore_errors=True)

        return BuildResult(ok=True, bundle_path=str(out))
