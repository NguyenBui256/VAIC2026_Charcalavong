"""Runnable arq worker entrypoint for the Orchestrator (Epic 7 thin-slice).

Wires `app.workers.orchestrator_worker.worker_config` (registers
`run_workflow`) together with `resume_orphaned_runs` (AC8 crash-recovery
startup poller) into a real `arq.Worker` process loop.

Usage::

    cd backend
    uv run python -m scripts.run_worker
    # or
    uv run python scripts/run_worker.py

Requires Redis (`VAIC_REDIS_URL`) and Postgres (`VAIC_DATABASE_URL`) to be
reachable — see `backend/.env`. Runs until interrupted (Ctrl+C) or the
process is killed; each `POST /workflows/{id}/runs` enqueues a
`run_workflow` job this process will pick up.
"""

from __future__ import annotations

import sys
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from app.workers.orchestrator_worker import resume_orphaned_runs, worker_config  # noqa: E402

__all__ = ["main"]


def main() -> None:
    """Build and run the arq Worker (blocks until interrupted)."""
    worker = worker_config.build_worker(on_startup=resume_orphaned_runs)
    worker.run()


if __name__ == "__main__":
    main()
