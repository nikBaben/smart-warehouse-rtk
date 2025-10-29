"""Оптимизация
Revision ID: 144a26a8c705
Revises: b0380714d6e5
Create Date: 2025-10-28 22:14:07.564692
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '144a26a8c705'
down_revision: Union[str, Sequence[str], None] = 'b0380714d6e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass