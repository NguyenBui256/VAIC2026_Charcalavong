"""Runnable arq worker entrypoint for the Orchestrator + Mini-App builder.

Wires `app.workers.orchestrator_worker.worker_config` (registers
`run_workflow`) together with `resume_orphaned_runs` (AC8 crash-recovery
startup poller) into a real `arq.Worker` process loop.

Epic 4 story 4-5: also registers `build_mini_app`
(`app.modules.mini_app.mini_app_worker`) on the SAME worker process, so one
`arq worker` picks up both Workflow Run and Mini-App build jobs. Imported
and merged HERE (not inside `orchestrator_worker.py`) per AD-1 — the two
feature modules stay decoupled; this script is the only place that knows
about both.
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from app.modules.action.worker import (  # noqa: E402
    action_cron_jobs,
    process_tenant_action_events,
)
from app.modules.mini_app.mini_app_worker import build_mini_app  # noqa: E402

# Register the mini_app_databases table on the worker's SQLAlchemy metadata so
# the MiniApp.database_id FK resolves during mapper config. The worker process
# imports MiniApp (via mini_app_worker) but nothing else pulls in database_models,
# so without this a build of a database-bound app raises NoReferencedTableError.
from app.modules.mini_app import database_models  # noqa: E402,F401
from app.workers.orchestrator_worker import resume_orphaned_runs, worker_config  # noqa: E402

__all__ = ["main"]

# Merge Mini-App builder + Action dispatch onto the orchestrator worker (AD-1).
_combined_worker_config = replace(
    worker_config,
    functions=[*worker_config.functions, build_mini_app, process_tenant_action_events],
    cron_jobs_list=[*worker_config.cron_jobs_list, *action_cron_jobs],
)


def main() -> None:
    """Build and run the arq Worker (blocks until interrupted)."""
    worker = _combined_worker_config.build_worker(on_startup=resume_orphaned_runs)
    worker.run()


if __name__ == "__main__":
    main()
