"""Mini-App lifecycle — the impure side of AD-8.

Applies a ProvisioningPlan: inserts the mini_apps row (build_status=pending)
and enqueues the isolated UI build. No schema/codegen logic here.
"""

from __future__ import annotations

from arq.connections import ArqRedis
from sqlalchemy.orm import Session

from app.core.jobs import enqueue_job_with_context
from app.modules.mini_app.models import MiniApp
from app.modules.mini_app.provisioner import ProvisioningPlan


def plan_to_model(plan: ProvisioningPlan) -> MiniApp:
    return MiniApp(
        id=plan.app_id,
        tenant_id=plan.tenant_id,
        department_id=plan.department_id,
        owner_id=plan.owner_id,
        name=plan.name,
        slug=plan.slug,
        description=plan.description,
        entity_schema=plan.entity_schema,
        ui_spec=plan.ui_spec,
        visibility_tier=plan.visibility_tier,
        whitelist_user_ids=plan.whitelist_user_ids,
        build_status="pending",
        created_by_agent_id=plan.created_by_agent_id,
    )


async def enqueue_build(pool: ArqRedis, app_id: str) -> None:
    await enqueue_job_with_context(pool, "build_mini_app", app_id=app_id)
