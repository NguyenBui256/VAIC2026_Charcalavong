"""merge audit v2 trace/evaluation into rebuild

Revision ID: c76b8fc3ef08
Revises: ac20actions01, d91f4a8c2e70
Create Date: 2026-07-19 04:08:05.082077

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c76b8fc3ef08'
down_revision: Union[str, Sequence[str], None] = ('ac20actions01', 'd91f4a8c2e70')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
