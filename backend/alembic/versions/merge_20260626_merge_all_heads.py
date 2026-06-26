"""merge all heads

Revision ID: merge_20260626
Revises: 08f0bd8598d6, mfa_20260626
Create Date: 2026-06-26 00:00:00.000000

"""
from typing import Sequence, Union

revision: str = 'merge_20260626'
down_revision: Union[str, Sequence[str], None] = ('08f0bd8598d6', 'mfa_20260626')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
