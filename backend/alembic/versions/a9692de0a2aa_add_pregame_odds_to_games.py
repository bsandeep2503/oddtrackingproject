"""add pregame odds to games

Revision ID: a9692de0a2aa
Revises: 017a504eea85
Create Date: 2026-01-29 18:38:33.051539

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a9692de0a2aa'
down_revision: Union[str, Sequence[str], None] = '017a504eea85'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add pregame odds columns to games table
    op.add_column('games', sa.Column('pregame_ml_home', sa.Float(), nullable=True))
    op.add_column('games', sa.Column('pregame_ml_away', sa.Float(), nullable=True))
    op.add_column('games', sa.Column('pregame_spread', sa.Float(), nullable=True))
    op.add_column('games', sa.Column('pregame_total', sa.Float(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    # Remove pregame odds columns from games table
    op.drop_column('games', 'pregame_total')
    op.drop_column('games', 'pregame_spread')
    op.drop_column('games', 'pregame_ml_away')
    op.drop_column('games', 'pregame_ml_home')
