"""AI Document Intelligence — processed documents with OCR/parse results,
classification, structured extraction, tables, AI summary and search embedding.

Revision ID: doc_intel_0001
Revises: knowledge_base_0001
Create Date: 2026-07-20
"""
import sqlalchemy as sa
from alembic import op

revision = 'doc_intel_0001'
down_revision = 'knowledge_base_0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'di_documents',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('organization_id', sa.UUID(), sa.ForeignKey('organizations.id'), nullable=False, index=True),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('content_type', sa.String(length=100), nullable=True),
        sa.Column('size_bytes', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('source', sa.String(length=20), nullable=False, server_default='upload'),
        sa.Column('context_type', sa.String(length=30), nullable=True),
        sa.Column('context_id', sa.UUID(), nullable=True, index=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='processed', index=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('text_content', sa.Text(), nullable=True),
        sa.Column('page_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('ocr_used', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('doc_type', sa.String(length=30), nullable=False, server_default='other', index=True),
        sa.Column('classification_confidence', sa.Float(), nullable=False, server_default='0'),
        sa.Column('classification_signals', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('extraction', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('tables', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('image_info', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('embedding', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('embedding_model', sa.String(length=40), nullable=False, server_default='hash_embed_v1'),
        sa.Column('uploaded_by', sa.UUID(), sa.ForeignKey('users.id'), nullable=True, index=True),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_table('di_documents')
