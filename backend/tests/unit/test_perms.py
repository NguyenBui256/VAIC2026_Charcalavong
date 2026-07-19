import uuid

import pytest

from app.core.errors import AuthorizationError
from app.core.perms import require_builder
from app.modules.agent_builder.service import Principal


def _p(role):
    return Principal(
        user_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        department_id=uuid.uuid4(),
        role=role,
    )


def test_require_builder_allows_builder():
    require_builder(_p("builder"))  # no raise


def test_require_builder_blocks_member():
    with pytest.raises(AuthorizationError):
        require_builder(_p("member"))
