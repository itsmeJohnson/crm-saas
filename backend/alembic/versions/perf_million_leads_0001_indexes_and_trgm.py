"""perf_million_leads_0001_indexes_and_trgm

Revision ID: perf_million_leads_0001
Revises: branch_assign_0001
Create Date: 2026-10-12
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'perf_million_leads_0001'
down_revision: Union[str, None] = 'branch_assign_0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # 1. Enable pg_trgm extension for substring & fuzzy search acceleration
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")

    # 2. Composite indexes for high-volume multi-tenant pipeline queries (100k - 1M+ leads)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_leads_org_active_created 
        ON leads (organization_id, is_deleted, is_archived, created_at DESC, id);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_leads_org_stage_created 
        ON leads (organization_id, stage_id, is_deleted, is_archived, created_at DESC, id);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_leads_org_status_created 
        ON leads (organization_id, status, is_deleted, is_archived, created_at DESC, id);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_leads_org_assigned_created 
        ON leads (organization_id, assigned_user_id, is_deleted, is_archived, created_at DESC, id);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_leads_org_priority_created 
        ON leads (organization_id, priority, is_deleted, is_archived, created_at DESC, id);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_leads_org_updated 
        ON leads (organization_id, is_deleted, is_archived, updated_at DESC);
    """)

    # 3. Trigram GIN index for sub-15ms multi-field text search
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_leads_trgm_search ON leads USING gin (
            (
                coalesce(title, '') || ' ' || 
                coalesce(company_name, '') || ' ' || 
                coalesce(first_name, '') || ' ' || 
                coalesce(last_name, '') || ' ' || 
                coalesce(email, '') || ' ' || 
                coalesce(phone, '')
            ) gin_trgm_ops
        ) WHERE is_deleted = false;
    """)

    # 4. Activity, task and note timeline optimization
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_activities_lead_created 
        ON activities (lead_id, created_at DESC) 
        WHERE is_deleted = false;
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_tasks_lead_due 
        ON tasks (lead_id, due_date) 
        WHERE is_deleted = false;
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_notes_lead_created 
        ON notes (lead_id, created_at DESC);
    """)

def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_notes_lead_created;")
    op.execute("DROP INDEX IF EXISTS ix_tasks_lead_due;")
    op.execute("DROP INDEX IF EXISTS ix_activities_lead_created;")
    op.execute("DROP INDEX IF EXISTS ix_leads_trgm_search;")
    op.execute("DROP INDEX IF EXISTS ix_leads_org_updated;")
    op.execute("DROP INDEX IF EXISTS ix_leads_org_priority_created;")
    op.execute("DROP INDEX IF EXISTS ix_leads_org_assigned_created;")
    op.execute("DROP INDEX IF EXISTS ix_leads_org_status_created;")
    op.execute("DROP INDEX IF EXISTS ix_leads_org_stage_created;")
    op.execute("DROP INDEX IF EXISTS ix_leads_org_active_created;")
