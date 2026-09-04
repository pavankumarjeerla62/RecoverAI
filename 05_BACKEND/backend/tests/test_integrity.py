"""
Explicit database-level integrity tests for RecoverAI security constraints.

These tests verify that PostgreSQL itself — not just application code — enforces:
  1. Merchant/customer tenant isolation via the composite FK on orders:
       orders(customer_id, merchant_id) → customers(id, merchant_id)
  2. AI decision / recovery attempt payment coherence via the composite FK on ai_decisions:
       ai_decisions(recovery_attempt_id, payment_id) → recovery_attempts(id, payment_id)

Each test creates the schema fresh, inserts raw SQL to bypass ORM validation, and
confirms that PostgreSQL raises an IntegrityError on violations and accepts valid rows.

The tests skip automatically if the target database already contains RecoverAI tables
to avoid accidentally modifying a live or migrated database.
"""
import unittest
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.core.config import get_settings


EXPECTED_TABLES = {
    "merchants",
    "customers",
    "orders",
    "payments",
    "payment_failures",
    "recovery_attempts",
    "ai_decisions",
}


@unittest.skipUnless(get_settings().database_url, "DATABASE_URL is not configured.")
class DatabaseIntegrityTests(unittest.TestCase):
    """Verify composite FK constraints are enforced at the PostgreSQL level."""

    # ------------------------------------------------------------------
    # Setup / teardown
    # ------------------------------------------------------------------

    def setUp(self) -> None:
        from sqlalchemy import inspect

        import app.db.models  # noqa: F401  – registers all mapped tables with Base.metadata
        from app.db.base import Base
        from app.db.session import engine

        self.engine = engine
        self.Base = Base
        self._schema_created = False

        existing = set(inspect(engine).get_table_names())
        if EXPECTED_TABLES & existing:
            self.skipTest(
                "RecoverAI tables already exist; integrity test will not modify "
                "existing data.  Drop the tables or use a dedicated test database."
            )

        Base.metadata.create_all(bind=engine)
        self._schema_created = True

    def tearDown(self) -> None:
        if self._schema_created:
            self.Base.metadata.drop_all(bind=self.engine)

    # ------------------------------------------------------------------
    # Raw-SQL helpers (bypass ORM so PostgreSQL constraints are the only guard)
    # ------------------------------------------------------------------

    def _insert_merchants_and_customers(self, conn) -> dict:
        """Insert two merchants, one customer per merchant.  Return id dict."""
        merchant_a = str(uuid4())
        merchant_b = str(uuid4())
        customer_a = str(uuid4())  # belongs to merchant_a
        customer_b = str(uuid4())  # belongs to merchant_b

        conn.execute(
            text("INSERT INTO merchants (id, name, email) VALUES (:id, :name, :email)"),
            {"id": merchant_a, "name": "Merchant A", "email": f"{uuid4()}@a.test"},
        )
        conn.execute(
            text("INSERT INTO merchants (id, name, email) VALUES (:id, :name, :email)"),
            {"id": merchant_b, "name": "Merchant B", "email": f"{uuid4()}@b.test"},
        )
        conn.execute(
            text(
                "INSERT INTO customers (id, merchant_id, name, email) "
                "VALUES (:id, :mid, :name, :email)"
            ),
            {"id": customer_a, "mid": merchant_a, "name": "Cust A", "email": f"{uuid4()}@a.test"},
        )
        conn.execute(
            text(
                "INSERT INTO customers (id, merchant_id, name, email) "
                "VALUES (:id, :mid, :name, :email)"
            ),
            {"id": customer_b, "mid": merchant_b, "name": "Cust B", "email": f"{uuid4()}@b.test"},
        )
        return {
            "merchant_a": merchant_a,
            "merchant_b": merchant_b,
            "customer_a": customer_a,  # belongs to merchant_a
            "customer_b": customer_b,  # belongs to merchant_b
        }

    def _insert_order_and_payments(self, conn, merchant_id: str, customer_id: str) -> dict:
        """Insert one order and two payments under that order.  Return id dict."""
        order_id = str(uuid4())
        payment_a = str(uuid4())
        payment_b = str(uuid4())

        conn.execute(
            text(
                "INSERT INTO orders (id, merchant_id, customer_id, amount) "
                "VALUES (:id, :mid, :cid, 100.00)"
            ),
            {"id": order_id, "mid": merchant_id, "cid": customer_id},
        )
        conn.execute(
            text(
                "INSERT INTO payments (id, order_id, provider, provider_payment_id, amount) "
                "VALUES (:id, :oid, 'razorpay', :ppid, 100.00)"
            ),
            {"id": payment_a, "oid": order_id, "ppid": str(uuid4())},
        )
        conn.execute(
            text(
                "INSERT INTO payments (id, order_id, provider, provider_payment_id, amount) "
                "VALUES (:id, :oid, 'razorpay', :ppid, 100.00)"
            ),
            {"id": payment_b, "oid": order_id, "ppid": str(uuid4())},
        )
        return {
            "order_id": order_id,
            "payment_a": payment_a,
            "payment_b": payment_b,
        }

    # ------------------------------------------------------------------
    # Test Group 1: Merchant / Customer Tenant Isolation
    # ------------------------------------------------------------------

    def test_cross_merchant_order_is_rejected(self) -> None:
        """PostgreSQL must reject an order where merchant_id and customer_id belong to
        different merchants.

        Composite FK: orders(customer_id, merchant_id) → customers(id, merchant_id)
        The pair (customer_b.id, merchant_a.id) does not exist in customers, so
        PostgreSQL raises an IntegrityError.
        """
        with self.engine.begin() as conn:
            ids = self._insert_merchants_and_customers(conn)

        with self.assertRaises(
            IntegrityError,
            msg=(
                "Expected PostgreSQL to reject an order with "
                "merchant_id=merchant_A but customer belonging to merchant_B."
            ),
        ):
            with self.engine.begin() as conn:
                conn.execute(
                    text(
                        "INSERT INTO orders (id, merchant_id, customer_id, amount) "
                        "VALUES (:id, :mid, :cid, 100.00)"
                    ),
                    {
                        "id": str(uuid4()),
                        "mid": ids["merchant_a"],  # merchant A
                        "cid": ids["customer_b"],  # customer belongs to merchant B — VIOLATION
                    },
                )

    def test_same_merchant_order_is_accepted(self) -> None:
        """PostgreSQL must accept an order where merchant and customer belong to the
        same merchant.
        """
        with self.engine.begin() as conn:
            ids = self._insert_merchants_and_customers(conn)
            # merchant_a + customer_a (who belongs to merchant_a) — VALID
            conn.execute(
                text(
                    "INSERT INTO orders (id, merchant_id, customer_id, amount) "
                    "VALUES (:id, :mid, :cid, 100.00)"
                ),
                {
                    "id": str(uuid4()),
                    "mid": ids["merchant_a"],  # merchant A
                    "cid": ids["customer_a"],  # customer belongs to merchant A — VALID
                },
            )

    # ------------------------------------------------------------------
    # Test Group 2: AI Decision / Recovery Attempt Payment Coherence
    # ------------------------------------------------------------------

    def test_mismatched_payment_recovery_attempt_is_rejected(self) -> None:
        """PostgreSQL must reject an AI decision whose recovery_attempt_id belongs to
        a different payment than payment_id.

        Composite FK: ai_decisions(recovery_attempt_id, payment_id)
                       → recovery_attempts(id, payment_id)
        The pair (recovery_attempt_for_payment_b, payment_a) does not exist in
        recovery_attempts, so PostgreSQL raises an IntegrityError.
        """
        with self.engine.begin() as conn:
            ids = self._insert_merchants_and_customers(conn)
            pay_ids = self._insert_order_and_payments(
                conn, ids["merchant_a"], ids["customer_a"]
            )
            recovery_for_b = str(uuid4())
            conn.execute(
                text(
                    "INSERT INTO recovery_attempts "
                    "(id, payment_id, action_type, scheduled_at) "
                    "VALUES (:id, :pid, 'email', now())"
                ),
                {"id": recovery_for_b, "pid": pay_ids["payment_b"]},
            )

        # AI decision: payment_a + recovery attempt that belongs to payment_b — VIOLATION
        with self.assertRaises(
            IntegrityError,
            msg=(
                "Expected PostgreSQL to reject an AI decision referencing a "
                "recovery attempt that belongs to a different payment."
            ),
        ):
            with self.engine.begin() as conn:
                conn.execute(
                    text(
                        "INSERT INTO ai_decisions "
                        "(id, payment_id, recovery_attempt_id, decision, reason, confidence) "
                        "VALUES (:id, :pid, :raid, 'retry', 'test', 0.9)"
                    ),
                    {
                        "id": str(uuid4()),
                        "pid": pay_ids["payment_a"],  # payment A
                        "raid": recovery_for_b,        # recovery attempt belongs to payment B — VIOLATION
                    },
                )

    def test_matched_payment_recovery_attempt_is_accepted(self) -> None:
        """PostgreSQL must accept an AI decision where payment_id and
        recovery_attempt_id refer to the same payment.
        """
        with self.engine.begin() as conn:
            ids = self._insert_merchants_and_customers(conn)
            pay_ids = self._insert_order_and_payments(
                conn, ids["merchant_a"], ids["customer_a"]
            )
            recovery_for_a = str(uuid4())
            conn.execute(
                text(
                    "INSERT INTO recovery_attempts "
                    "(id, payment_id, action_type, scheduled_at) "
                    "VALUES (:id, :pid, 'email', now())"
                ),
                {"id": recovery_for_a, "pid": pay_ids["payment_a"]},
            )

            # AI decision: payment_a + recovery attempt belonging to payment_a — VALID
            conn.execute(
                text(
                    "INSERT INTO ai_decisions "
                    "(id, payment_id, recovery_attempt_id, decision, reason, confidence) "
                    "VALUES (:id, :pid, :raid, 'retry', 'test', 0.9)"
                ),
                {
                    "id": str(uuid4()),
                    "pid": pay_ids["payment_a"],   # payment A
                    "raid": recovery_for_a,          # recovery attempt belongs to payment A — VALID
                },
            )

    def test_null_recovery_attempt_id_is_accepted(self) -> None:
        """PostgreSQL must accept an AI decision with recovery_attempt_id = NULL.

        recovery_attempt_id is optional — a decision can be recorded before any
        recovery attempt is scheduled.  PostgreSQL MATCH SIMPLE semantics mean the
        composite FK check is skipped entirely when recovery_attempt_id IS NULL, so
        setting it to NULL must always be accepted regardless of payment_id.
        """
        with self.engine.begin() as conn:
            ids = self._insert_merchants_and_customers(conn)
            pay_ids = self._insert_order_and_payments(
                conn, ids["merchant_a"], ids["customer_a"]
            )

            # No recovery attempt yet — recovery_attempt_id = NULL — VALID
            conn.execute(
                text(
                    "INSERT INTO ai_decisions "
                    "(id, payment_id, recovery_attempt_id, decision, reason, confidence) "
                    "VALUES (:id, :pid, NULL, 'retry', 'test', 0.9)"
                ),
                {
                    "id": str(uuid4()),
                    "pid": pay_ids["payment_a"],
                },
            )
