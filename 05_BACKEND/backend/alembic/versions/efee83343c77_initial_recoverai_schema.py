"""initial recoverai schema

Revision ID: efee83343c77
Revises:
Create Date: 2026-09-05 00:38:41.698096

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'efee83343c77'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('merchants',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('email', sa.String(length=255), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('email')
    )
    op.create_table('customers',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('merchant_id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('email', sa.String(length=255), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['merchant_id'], ['merchants.id'], ),
    sa.PrimaryKeyConstraint('id'),
    # Required so orders can reference customers(id, merchant_id) via composite FK.
    sa.UniqueConstraint('id', 'merchant_id', name='uq_customers_id_merchant_id'),
    )
    op.create_index('ix_customers_merchant_email', 'customers', ['merchant_id', 'email'], unique=True)
    op.create_index(op.f('ix_customers_merchant_id'), 'customers', ['merchant_id'], unique=False)
    op.create_table('orders',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('merchant_id', sa.UUID(), nullable=False),
    sa.Column('customer_id', sa.UUID(), nullable=False),
    sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('currency', sa.String(length=3), server_default='INR', nullable=False),
    sa.Column('status', sa.String(length=50), server_default='pending', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('amount >= 0', name='ck_orders_amount_non_negative'),
    # Composite FK enforces tenant isolation: customer must belong to the same
    # merchant as the order.  Prevents cross-merchant customer references at the DB level.
    sa.ForeignKeyConstraint(
        ['customer_id', 'merchant_id'],
        ['customers.id', 'customers.merchant_id'],
        name='fk_orders_customer_merchant',
    ),
    sa.ForeignKeyConstraint(['merchant_id'], ['merchants.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_orders_customer_id'), 'orders', ['customer_id'], unique=False)
    op.create_index(op.f('ix_orders_merchant_id'), 'orders', ['merchant_id'], unique=False)
    op.create_table('payments',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('order_id', sa.UUID(), nullable=False),
    sa.Column('provider', sa.String(length=50), nullable=False),
    sa.Column('provider_payment_id', sa.String(length=255), nullable=False),
    sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('currency', sa.String(length=3), server_default='INR', nullable=False),
    sa.Column('status', sa.String(length=50), server_default='pending', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('amount >= 0', name='ck_payments_amount_non_negative'),
    sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_payments_order_id'), 'payments', ['order_id'], unique=False)
    op.create_index('ix_payments_provider_payment_id', 'payments', ['provider', 'provider_payment_id'], unique=True)
    op.create_table('payment_failures',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('payment_id', sa.UUID(), nullable=False),
    sa.Column('failure_code', sa.String(length=100), nullable=False),
    sa.Column('failure_reason', sa.Text(), nullable=False),
    sa.Column('failed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['payment_id'], ['payments.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_payment_failures_payment_id'), 'payment_failures', ['payment_id'], unique=False)
    op.create_table('recovery_attempts',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('payment_id', sa.UUID(), nullable=False),
    sa.Column('action_type', sa.String(length=50), nullable=False),
    sa.Column('status', sa.String(length=50), server_default='scheduled', nullable=False),
    sa.Column('scheduled_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('executed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['payment_id'], ['payments.id'], ),
    sa.PrimaryKeyConstraint('id'),
    # Required so ai_decisions can reference recovery_attempts(id, payment_id) via composite FK.
    sa.UniqueConstraint('id', 'payment_id', name='uq_recovery_attempts_id_payment_id'),
    )
    op.create_index('ix_recovery_attempts_payment_scheduled_at', 'recovery_attempts', ['payment_id', 'scheduled_at'], unique=False)
    op.create_table('ai_decisions',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('payment_id', sa.UUID(), nullable=False),
    sa.Column('recovery_attempt_id', sa.UUID(), nullable=True),
    sa.Column('decision', sa.String(length=100), nullable=False),
    sa.Column('reason', sa.Text(), nullable=False),
    sa.Column('confidence', sa.Numeric(precision=5, scale=4), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('confidence >= 0 AND confidence <= 1', name='ck_ai_decisions_confidence_range'),
    sa.ForeignKeyConstraint(['payment_id'], ['payments.id'], ),
    # Composite FK enforces payment coherence: when recovery_attempt_id is not NULL,
    # the referenced recovery_attempt must belong to the same payment as this decision.
    # PostgreSQL MATCH SIMPLE skips the check when recovery_attempt_id IS NULL.
    sa.ForeignKeyConstraint(
        ['recovery_attempt_id', 'payment_id'],
        ['recovery_attempts.id', 'recovery_attempts.payment_id'],
        name='fk_ai_decisions_recovery_attempt_payment',
    ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_ai_decisions_payment_id'), 'ai_decisions', ['payment_id'], unique=False)
    op.create_index(op.f('ix_ai_decisions_recovery_attempt_id'), 'ai_decisions', ['recovery_attempt_id'], unique=False)


def downgrade() -> None:
    # Drop tables in reverse dependency order.  DROP TABLE removes all
    # constraints and indexes on that table automatically in PostgreSQL.
    op.drop_index(op.f('ix_ai_decisions_recovery_attempt_id'), table_name='ai_decisions')
    op.drop_index(op.f('ix_ai_decisions_payment_id'), table_name='ai_decisions')
    op.drop_table('ai_decisions')
    op.drop_index('ix_recovery_attempts_payment_scheduled_at', table_name='recovery_attempts')
    op.drop_table('recovery_attempts')
    op.drop_index(op.f('ix_payment_failures_payment_id'), table_name='payment_failures')
    op.drop_table('payment_failures')
    op.drop_index('ix_payments_provider_payment_id', table_name='payments')
    op.drop_index(op.f('ix_payments_order_id'), table_name='payments')
    op.drop_table('payments')
    op.drop_index(op.f('ix_orders_merchant_id'), table_name='orders')
    op.drop_index(op.f('ix_orders_customer_id'), table_name='orders')
    op.drop_table('orders')
    op.drop_index(op.f('ix_customers_merchant_id'), table_name='customers')
    op.drop_index('ix_customers_merchant_email', table_name='customers')
    op.drop_table('customers')
    op.drop_table('merchants')
