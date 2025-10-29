"""dddddd
Revision ID: b0380714d6e5
Revises: f5095e7082f9
Create Date: 2025-10-28 22:10:33.614943
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b0380714d6e5'
down_revision: Union[str, Sequence[str], None] = 'f5095e7082f9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass