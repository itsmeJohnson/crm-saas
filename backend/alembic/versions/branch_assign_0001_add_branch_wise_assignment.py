"""add branch-wise lead assignment columns

Adds:
  * users.branch_id            -- posts a rep to a branch (nullable = unassigned)
  * assignment_configs.branch_cursors (JSON) -- per-branch round-robin cursors

Guarded (IF NOT EXISTS) because the schema has historically been created via
create_all, so these columns may already be present on some databases.

Revision ID: branch_assign_0001
Revises: d8e9f0a1b2c3
Create Date: 2026-09-22
"""
from typing import Sequence, Union

from alembic import op

revision: str = "branch_assign_0001"
down_revision: Union[str, Sequence[str], None] = "d8e9f0a1b2c3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS branch_id UUID")
    op.execute(
        "DO $$ BEGIN "
        "IF NOT EXISTS (SELECT 1 FROM information_schema.table_constraints "
        "WHERE constraint_name = 'fk_users_branch') THEN "
        "ALTER TABLE users ADD CONSTRAINT fk_users_branch "
        "FOREIGN KEY (branch_id) REFERENCES branches(id); "
        "END IF; END $$;"
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_users_branch_id ON users(branch_id)")
    op.execute(
        "ALTER TABLE assignment_configs "
        "ADD COLUMN IF NOT EXISTS branch_cursors JSON NOT NULL DEFAULT '{}'"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE assignment_configs DROP COLUMN IF EXISTS branch_cursors")
    op.execute("DROP INDEX IF EXISTS ix_users_branch_id")
    op.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS fk_users_branch")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS branch_id")
