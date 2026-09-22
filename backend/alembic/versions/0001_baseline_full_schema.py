"""baseline: full-schema squash (replaces the pre-2026-09-22 migration chain)

Why this exists
---------------
Historically the schema was materialised by ``Base.metadata.create_all`` while the
Alembic chain only ever created ~21 of the 191 model tables. As a result
``alembic upgrade head`` could **not** build a database from empty (e.g. it tried
``ALTER TABLE plans ...`` before any migration created ``plans``), which broke
greenfield/self-host deploys even though the project's policy is "schema managed
exclusively by Alembic".

This revision collapses that tangled 108-migration chain (archived under
``backend/alembic/_archived_versions_pre_baseline/``) into a single baseline that
materialises the entire current model schema via ``create_all``. ``create_all``
uses ``checkfirst=True``, so it is idempotent: on an empty database it creates all
tables; on a database that already has them it is a no-op.

Transition notes
----------------
* Greenfield deploy: ``alembic upgrade head`` runs this baseline and builds the
  full schema in one step.
* Existing database (schema already present via the old chain): run
  ``alembic stamp baseline_0001`` once so Alembic records this baseline without
  re-creating anything.
* Future schema changes: add normal migrations chained after this revision
  (``down_revision = "baseline_0001"``), created via ``ops/new-migration.sh``.

Revision ID: baseline_0001
Revises:
Create Date: 2026-09-22
"""
from typing import Sequence, Union

from alembic import op

# Mirror alembic/env.py: importing app.models registers every model on the
# shared Base.metadata, so create_all/drop_all see the complete schema.
from app.models.base import Base
import app.models  # noqa: F401  (side-effect import: registers all models)

# revision identifiers, used by Alembic.
revision: str = "baseline_0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the full current schema. Idempotent via create_all(checkfirst=True)."""
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    """Drop the entire schema (baseline has no predecessor)."""
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
