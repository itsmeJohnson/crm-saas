"""AI Knowledge Base — categories, articles (FAQ/document types, approval
workflow, visibility), version snapshots, embedding chunks and analytics events.

Revision ID: knowledge_base_0001
Revises: ai_platform_0001
Create Date: 2026-07-20
"""
import sqlalchemy as sa
from alembic import op

revision = 'knowledge_base_0001'
down_revision = 'ai_platform_0001'
branch_labels = None
depends_on = None


def _base_cols():
    return [
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True, server_default=sa.false()),
    ]


def upgrade() -> None:
    op.create_table(
        'kb_categories',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('organization_id', sa.UUID(), sa.ForeignKey('organizations.id'), nullable=False, index=True),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('parent_id', sa.UUID(), sa.ForeignKey('kb_categories.id'), nullable=True, index=True),
        sa.Column('display_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_by', sa.UUID(), sa.ForeignKey('users.id'), nullable=True),
        *_base_cols(),
        sa.UniqueConstraint('organization_id', 'name', name='uq_kb_category_org_name'),
    )
    op.create_table(
        'kb_articles',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('organization_id', sa.UUID(), sa.ForeignKey('organizations.id'), nullable=False, index=True),
        sa.Column('title', sa.String(length=300), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('article_type', sa.String(length=20), nullable=False, server_default='article'),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='draft', index=True),
        sa.Column('category_id', sa.UUID(), sa.ForeignKey('kb_categories.id'), nullable=True, index=True),
        sa.Column('tags', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('visibility', sa.String(length=20), nullable=False, server_default='all'),
        sa.Column('language', sa.String(length=10), nullable=False, server_default='en'),
        sa.Column('source_filename', sa.String(length=255), nullable=True),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_by', sa.UUID(), sa.ForeignKey('users.id'), nullable=True, index=True),
        sa.Column('updated_by', sa.UUID(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('reviewed_by', sa.UUID(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('review_note', sa.Text(), nullable=True),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_indexed', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('indexed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('chunk_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('view_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('helpful_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('not_helpful_count', sa.Integer(), nullable=False, server_default='0'),
        *_base_cols(),
    )
    op.create_table(
        'kb_article_versions',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('article_id', sa.UUID(), sa.ForeignKey('kb_articles.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=300), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('edited_by', sa.UUID(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('change_note', sa.Text(), nullable=True),
        *_base_cols(),
        sa.UniqueConstraint('article_id', 'version', name='uq_kb_article_version'),
    )
    op.create_table(
        'kb_chunks',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('organization_id', sa.UUID(), sa.ForeignKey('organizations.id'), nullable=False, index=True),
        sa.Column('article_id', sa.UUID(), sa.ForeignKey('kb_articles.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('chunk_index', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('embedding', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('embedding_model', sa.String(length=40), nullable=False, server_default='hash_embed_v1'),
        sa.Column('token_count', sa.Integer(), nullable=False, server_default='0'),
        *_base_cols(),
    )
    op.create_table(
        'kb_events',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('organization_id', sa.UUID(), sa.ForeignKey('organizations.id'), nullable=False, index=True),
        sa.Column('user_id', sa.UUID(), sa.ForeignKey('users.id'), nullable=True, index=True),
        sa.Column('event_type', sa.String(length=20), nullable=False, index=True),
        sa.Column('article_id', sa.UUID(), sa.ForeignKey('kb_articles.id'), nullable=True, index=True),
        sa.Column('query', sa.Text(), nullable=True),
        sa.Column('results_count', sa.Integer(), nullable=True),
        sa.Column('helpful', sa.Boolean(), nullable=True),
        sa.Column('event_metadata', sa.JSON(), nullable=False, server_default='{}'),
        *_base_cols(),
    )


def downgrade() -> None:
    op.drop_table('kb_events')
    op.drop_table('kb_chunks')
    op.drop_table('kb_article_versions')
    op.drop_table('kb_articles')
    op.drop_table('kb_categories')
