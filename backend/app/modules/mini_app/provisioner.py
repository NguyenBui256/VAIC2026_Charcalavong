"""Pure Mini-App provisioner (AD-8).

`build_provisioning_plan` is deterministic and side-effect free: given the
validated schema + ui spec + owner context, it returns a ProvisioningPlan
value. The lifecycle module (Task 6) performs the DB insert and enqueues
the build. Codegen of the .tsx bundle source (Phase 2) is a separate pure
step keyed off the plan.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from typing import Any

from app.core.ids import uuid7
from app.modules.mini_app.schemas import EntitySchema, UiSpec

_SLUG_STRIP = re.compile(r"[^a-z0-9]+")


def slugify(name: str) -> str:
    slug = _SLUG_STRIP.sub("-", name.lower()).strip("-")
    return (slug or "app")[:64]


@dataclass(frozen=True)
class ProvisioningPlan:
    app_id: uuid.UUID
    tenant_id: uuid.UUID
    department_id: uuid.UUID
    owner_id: uuid.UUID
    name: str
    slug: str
    description: str
    entity_schema: dict[str, Any]
    ui_spec: dict[str, Any]
    visibility_tier: str
    whitelist_user_ids: list[uuid.UUID] = field(default_factory=list)
    created_by_agent_id: uuid.UUID | None = None


def build_provisioning_plan(
    *,
    tenant_id: uuid.UUID,
    department_id: uuid.UUID,
    owner_id: uuid.UUID,
    name: str,
    description: str,
    schema: EntitySchema,
    ui_spec: UiSpec,
    visibility_tier: str,
    whitelist_user_ids: list[uuid.UUID] | None = None,
    created_by_agent_id: uuid.UUID | None = None,
) -> ProvisioningPlan:
    return ProvisioningPlan(
        app_id=uuid7(),
        tenant_id=tenant_id,
        department_id=department_id,
        owner_id=owner_id,
        name=name,
        slug=slugify(name),
        description=description,
        entity_schema=schema.model_dump(),
        ui_spec=ui_spec.model_dump(),
        visibility_tier=visibility_tier,
        whitelist_user_ids=list(whitelist_user_ids or []),
        created_by_agent_id=created_by_agent_id,
    )
