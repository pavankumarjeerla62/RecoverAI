"""MVP SQLAlchemy models for RecoverAI's payment recovery domain."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Merchant(Base):
    """A business using RecoverAI to monitor and recover payments."""

    __tablename__ = "merchants"

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    customers: Mapped[list[Customer]] = relationship(back_populates="merchant")
    orders: Mapped[list[Order]] = relationship(back_populates="merchant")


class Customer(Base):
    """A merchant's customer who places orders."""

    __tablename__ = "customers"
    __table_args__ = (
        Index("ix_customers_merchant_email", "merchant_id", "email", unique=True),
        # Backing unique constraint required so orders can enforce the composite
        # FK (customer_id, merchant_id) → customers(id, merchant_id).
        UniqueConstraint("id", "merchant_id", name="uq_customers_id_merchant_id"),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    merchant_id: Mapped[UUID] = mapped_column(
        ForeignKey("merchants.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    merchant: Mapped[Merchant] = relationship(back_populates="customers")
    # foreign_keys disambiguates from the Order side, which carries the composite FK.
    orders: Mapped[list[Order]] = relationship(
        back_populates="customer",
        foreign_keys="[Order.customer_id]",
    )


class Order(Base):
    """An order placed by a customer for a merchant.

    Database-level tenant isolation:
        The composite FK (customer_id, merchant_id) → customers(id, merchant_id)
        guarantees that PostgreSQL itself rejects any order whose customer belongs
        to a different merchant.  Application code alone cannot be relied upon for
        this guarantee.
    """

    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint("amount >= 0", name="ck_orders_amount_non_negative"),
        # Composite FK enforces tenant isolation at the database level.
        # customer_id alone is not sufficient; both columns must match a row in
        # customers(id, merchant_id), which is covered by uq_customers_id_merchant_id.
        ForeignKeyConstraint(
            ["customer_id", "merchant_id"],
            ["customers.id", "customers.merchant_id"],
            name="fk_orders_customer_merchant",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    merchant_id: Mapped[UUID] = mapped_column(
        ForeignKey("merchants.id"), nullable=False, index=True
    )
    # No inline ForeignKey here — the composite ForeignKeyConstraint above
    # creates the FK object on this column via the __table_args__ mechanism.
    customer_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), nullable=False, index=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default="INR")
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default="pending"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    merchant: Mapped[Merchant] = relationship(back_populates="orders")
    # foreign_keys tells SQLAlchemy to use only customer_id for the ORM join
    # condition (customer_id == Customer.id).  The composite FK enforces the
    # merchant match at INSERT/UPDATE time; the ORM join is unambiguous.
    customer: Mapped[Customer] = relationship(
        back_populates="orders",
        foreign_keys="[Order.customer_id]",
    )
    payments: Mapped[list[Payment]] = relationship(back_populates="order")


class Payment(Base):
    """A payment attempt recorded for an order."""

    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint("amount >= 0", name="ck_payments_amount_non_negative"),
        Index(
            "ix_payments_provider_payment_id",
            "provider",
            "provider_payment_id",
            unique=True,
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    order_id: Mapped[UUID] = mapped_column(
        ForeignKey("orders.id"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    provider_payment_id: Mapped[str] = mapped_column(String(255), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default="INR")
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default="pending"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    order: Mapped[Order] = relationship(back_populates="payments")
    failures: Mapped[list[PaymentFailure]] = relationship(back_populates="payment")
    recovery_attempts: Mapped[list[RecoveryAttempt]] = relationship(back_populates="payment")
    ai_decisions: Mapped[list[AIDecision]] = relationship(back_populates="payment")


class PaymentFailure(Base):
    """A provider-reported failure for a payment."""

    __tablename__ = "payment_failures"

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    payment_id: Mapped[UUID] = mapped_column(
        ForeignKey("payments.id"), nullable=False, index=True
    )
    failure_code: Mapped[str] = mapped_column(String(100), nullable=False)
    failure_reason: Mapped[str] = mapped_column(Text, nullable=False)
    failed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    payment: Mapped[Payment] = relationship(back_populates="failures")


class RecoveryAttempt(Base):
    """A scheduled or completed action to recover a failed payment."""

    __tablename__ = "recovery_attempts"
    __table_args__ = (
        Index("ix_recovery_attempts_payment_scheduled_at", "payment_id", "scheduled_at"),
        # Backing unique constraint required so ai_decisions can enforce the composite
        # FK (recovery_attempt_id, payment_id) → recovery_attempts(id, payment_id).
        UniqueConstraint("id", "payment_id", name="uq_recovery_attempts_id_payment_id"),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    payment_id: Mapped[UUID] = mapped_column(ForeignKey("payments.id"), nullable=False)
    action_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default="scheduled"
    )
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    payment: Mapped[Payment] = relationship(back_populates="recovery_attempts")
    # foreign_keys disambiguates from the AIDecision side, which carries the composite FK.
    ai_decisions: Mapped[list[AIDecision]] = relationship(
        back_populates="recovery_attempt",
        foreign_keys="[AIDecision.recovery_attempt_id]",
    )


class AIDecision(Base):
    """A recorded AI recommendation related to a payment recovery action.

    Database-level payment coherence:
        The composite FK (recovery_attempt_id, payment_id) → recovery_attempts(id, payment_id)
        guarantees that PostgreSQL itself rejects any AI decision whose recovery_attempt
        belongs to a different payment.

        recovery_attempt_id is nullable (a decision may exist before any recovery attempt
        is scheduled).  PostgreSQL MATCH SIMPLE semantics mean the composite FK check is
        skipped entirely when recovery_attempt_id IS NULL, so NULL is always accepted.
    """

    __tablename__ = "ai_decisions"
    __table_args__ = (
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1", name="ck_ai_decisions_confidence_range"
        ),
        # Composite FK enforces payment coherence at the database level.
        # recovery_attempt_id is nullable; with PostgreSQL MATCH SIMPLE (the default),
        # the FK check is skipped whenever any referencing column is NULL.
        ForeignKeyConstraint(
            ["recovery_attempt_id", "payment_id"],
            ["recovery_attempts.id", "recovery_attempts.payment_id"],
            name="fk_ai_decisions_recovery_attempt_payment",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    payment_id: Mapped[UUID] = mapped_column(
        ForeignKey("payments.id"), nullable=False, index=True
    )
    # No inline ForeignKey here — the composite ForeignKeyConstraint above
    # creates the FK object on this column via the __table_args__ mechanism.
    recovery_attempt_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True), index=True
    )
    decision: Mapped[str] = mapped_column(String(100), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    payment: Mapped[Payment] = relationship(back_populates="ai_decisions")
    # foreign_keys tells SQLAlchemy to use only recovery_attempt_id for the ORM
    # join condition.  The composite FK enforces payment coherence at INSERT/UPDATE
    # time; the ORM join is unambiguous.
    recovery_attempt: Mapped[RecoveryAttempt | None] = relationship(
        back_populates="ai_decisions",
        foreign_keys="[AIDecision.recovery_attempt_id]",
    )
