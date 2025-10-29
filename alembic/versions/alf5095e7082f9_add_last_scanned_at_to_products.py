"""add last_scanned_at to products
Revision ID: f5095e7082f9
Revises: d0cd90214af1
Create Date: 2025-10-28 22:07:29.784435
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f5095e7082f9'
down_revision: Union[str, Sequence[str], None] = 'd0cd90214af1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass