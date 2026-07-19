"""merge heads: agent-target/file-upload + audit-v2

Revision ID: 14c1e4b3d640
Revises: a7b8c9d0e1f2, c1d2e3f4a5b6
Create Date: 2026-07-19 07:48:35.145259

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '14c1e4b3d640'
down_revision: Union[str, Sequence[str], None] = ('a7b8c9d0e1f2', 'c1d2e3f4a5b6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
