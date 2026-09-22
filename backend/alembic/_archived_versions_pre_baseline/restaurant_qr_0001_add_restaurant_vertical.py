"""Restaurant QR-Voucher vertical: venues, offers, tables, guests, vouchers.

This revision also MERGES the previously-diverged heads into one so that
`alembic upgrade head` (singular) works again.

Revision ID: restaurant_qr_0001
Revises: refresh_token_hash_0001, d4e5f6a7b8c9, reset_token_tz_0001, notifications_20260702, treatment_catalog_0001, d8e9f0a1b2c3
Create Date: 2026-09-15
"""
import sqlalchemy as sa
from alembic import op

revision = 'restaurant_qr_0001'
down_revision = (
    'refresh_token_hash_0001',
    'd4e5f6a7b8c9',
    'reset_token_tz_0001',
    'notifications_20260702',
    'treatment_catalog_0001',
    'd8e9f0a1b2c3',
)
branch_labels = None
depends_on = None


def _base_cols():
    return [
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default=sa.false()),
    ]


def upgrade() -> None:
    # ---- venues (default_offer_id FK added after offers exists) ----
    op.create_table(
        'restaurant_venues',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('organization_id', sa.UUID(), sa.ForeignKey('organizations.id'), nullable=False, index=True),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('slug', sa.String(length=80), nullable=False),
        sa.Column('whatsapp_settings_id', sa.UUID(),
                  sa.ForeignKey('whatsapp_settings.id', ondelete='SET NULL'), nullable=True),
        sa.Column('default_offer_id', sa.UUID(), nullable=True),
        sa.Column('timezone', sa.String(length=64), nullable=False, server_default='Asia/Kolkata'),
        sa.Column('default_country_code', sa.String(length=6), nullable=False, server_default='91'),
        sa.Column('logo_url', sa.String(length=500), nullable=True),
        sa.Column('brand_color', sa.String(length=9), nullable=False, server_default='#D97706'),
        sa.Column('consent_text', sa.Text(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        *_base_cols(),
        sa.UniqueConstraint('slug', name='uq_restaurant_venue_slug'),
    )
    op.create_index('ix_restaurant_venue_org', 'restaurant_venues', ['organization_id'])

    # ---- offers ----
    op.create_table(
        'restaurant_offers',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('organization_id', sa.UUID(), sa.ForeignKey('organizations.id'), nullable=False, index=True),
        sa.Column('venue_id', sa.UUID(),
                  sa.ForeignKey('restaurant_venues.id', ondelete='CASCADE'), nullable=False),
        sa.Column('title', sa.String(length=160), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('terms', sa.Text(), nullable=True),
        sa.Column('image_url', sa.String(length=500), nullable=True),
        sa.Column('valid_from', sa.DateTime(timezone=True), nullable=True),
        sa.Column('valid_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('voucher_validity_days', sa.Integer(), nullable=True, server_default='30'),
        sa.Column('per_guest_limit', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('total_issue_limit', sa.Integer(), nullable=True),
        sa.Column('issued_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('redeemed_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        *_base_cols(),
    )
    op.create_index('ix_restaurant_offer_org', 'restaurant_offers', ['organization_id'])
    op.create_index('ix_restaurant_offer_venue', 'restaurant_offers', ['venue_id'])

    # Now wire the circular venue->offer FK.
    op.create_foreign_key(
        'fk_venue_default_offer', 'restaurant_venues', 'restaurant_offers',
        ['default_offer_id'], ['id'], ondelete='SET NULL')

    # ---- tables ----
    op.create_table(
        'restaurant_tables',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('organization_id', sa.UUID(), sa.ForeignKey('organizations.id'), nullable=False, index=True),
        sa.Column('venue_id', sa.UUID(),
                  sa.ForeignKey('restaurant_venues.id', ondelete='CASCADE'), nullable=False),
        sa.Column('label', sa.String(length=40), nullable=False),
        sa.Column('token', sa.String(length=64), nullable=False),
        sa.Column('offer_id', sa.UUID(),
                  sa.ForeignKey('restaurant_offers.id', ondelete='SET NULL'), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('scan_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_scanned_at', sa.DateTime(timezone=True), nullable=True),
        *_base_cols(),
        sa.UniqueConstraint('token', name='uq_restaurant_table_token'),
        sa.UniqueConstraint('venue_id', 'label', name='uq_restaurant_table_venue_label'),
    )
    op.create_index('ix_restaurant_table_org', 'restaurant_tables', ['organization_id'])

    # ---- guests ----
    op.create_table(
        'restaurant_guests',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('organization_id', sa.UUID(), sa.ForeignKey('organizations.id'), nullable=False, index=True),
        sa.Column('venue_id', sa.UUID(),
                  sa.ForeignKey('restaurant_venues.id', ondelete='SET NULL'), nullable=True),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('phone', sa.String(length=20), nullable=False),
        sa.Column('email', sa.String(length=160), nullable=True),
        sa.Column('dob', sa.Date(), nullable=True),
        sa.Column('marketing_consent', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('consent_text', sa.Text(), nullable=True),
        sa.Column('consent_ip', sa.String(length=64), nullable=True),
        sa.Column('consent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.String(length=16), nullable=False, server_default='active'),
        sa.Column('opted_out_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('visit_count', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('last_visit_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_table_label', sa.String(length=40), nullable=True),
        sa.Column('rating', sa.Integer(), nullable=True),
        sa.Column('feedback', sa.Text(), nullable=True),
        sa.Column('lead_id', sa.UUID(), sa.ForeignKey('leads.id', ondelete='SET NULL'), nullable=True),
        *_base_cols(),
        sa.UniqueConstraint('organization_id', 'phone', name='uq_restaurant_guest_org_phone'),
    )
    op.create_index('ix_restaurant_guest_org_status', 'restaurant_guests', ['organization_id', 'status'])
    op.create_index('ix_restaurant_guest_phone', 'restaurant_guests', ['phone'])

    # ---- vouchers ----
    op.create_table(
        'restaurant_vouchers',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('organization_id', sa.UUID(), sa.ForeignKey('organizations.id'), nullable=False, index=True),
        sa.Column('venue_id', sa.UUID(),
                  sa.ForeignKey('restaurant_venues.id', ondelete='SET NULL'), nullable=True),
        sa.Column('offer_id', sa.UUID(),
                  sa.ForeignKey('restaurant_offers.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('guest_id', sa.UUID(),
                  sa.ForeignKey('restaurant_guests.id', ondelete='CASCADE'), nullable=False),
        sa.Column('code', sa.String(length=40), nullable=False),
        sa.Column('offer_title', sa.String(length=160), nullable=False),
        sa.Column('status', sa.String(length=16), nullable=False, server_default='active'),
        sa.Column('issued_table_label', sa.String(length=40), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('redeemed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('redeemed_by_user_id', sa.UUID(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('redeemed_table_label', sa.String(length=40), nullable=True),
        sa.Column('delivery_status', sa.String(length=16), nullable=False, server_default='pending'),
        sa.Column('wa_message_id', sa.UUID(),
                  sa.ForeignKey('whatsapp_messages.id', ondelete='SET NULL'), nullable=True),
        *_base_cols(),
        sa.UniqueConstraint('code', name='uq_restaurant_voucher_code'),
    )
    op.create_index('ix_restaurant_voucher_org_status', 'restaurant_vouchers', ['organization_id', 'status'])
    op.create_index('ix_restaurant_voucher_guest', 'restaurant_vouchers', ['guest_id'])


def downgrade() -> None:
    op.drop_table('restaurant_vouchers')
    op.drop_table('restaurant_guests')
    op.drop_table('restaurant_tables')
    op.drop_constraint('fk_venue_default_offer', 'restaurant_venues', type_='foreignkey')
    op.drop_table('restaurant_offers')
    op.drop_table('restaurant_venues')
