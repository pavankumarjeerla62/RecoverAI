"""
Alembic migration tests for RecoverAI.

DESTRUCTIVE OPERATIONS
======================
These tests perform real upgrade and downgrade operations against the configured
DATABASE_URL.  They are disabled by default and require an explicit opt-in.

To enable (PowerShell):
    $env:RECOVERAI_ALLOW_DESTRUCTIVE_DB_TESTS="1"
    python -m pytest tests/test_migrations.py -v
    Remove-Item Env:RECOVERAI_ALLOW_DESTRUCTIVE_DB_TESTS

Safety guarantees:
  - Skips automatically if RECOVERAI_ALLOW_DESTRUCTIVE_DB_TESTS is not exactly "1".
  - Refuses to run if the database already contains any RecoverAI application tables
    or Alembic migration state (alembic_version table).
  - Performs best-effort cleanup in the finally block if upgrade succeeded but a
    later step failed.
"""
import os
import unittest
from pathlib import Path

from app.core.config import get_settings


BACKEND_DIRECTORY = Path(__file__).resolve().parents[1]
ALEMBIC_CONFIG_PATH = BACKEND_DIRECTORY / "alembic.ini"

EXPECTED_TABLES = {
    "merchants",
    "customers",
    "orders",
    "payments",
    "payment_failures",
    "recovery_attempts",
    "ai_decisions",
}

_DATABASE_CONFIGURED = bool(get_settings().database_url)
_DESTRUCTIVE_ENABLED = os.environ.get("RECOVERAI_ALLOW_DESTRUCTIVE_DB_TESTS") == "1"


@unittest.skipUnless(_DATABASE_CONFIGURED, "DATABASE_URL is not configured.")
@unittest.skipUnless(
    _DESTRUCTIVE_ENABLED,
    "Destructive migration tests are disabled.\n"
    "To enable (PowerShell):\n"
    '    $env:RECOVERAI_ALLOW_DESTRUCTIVE_DB_TESTS="1"\n'
    "    python -m pytest tests/test_migrations.py -v\n"
    "    Remove-Item Env:RECOVERAI_ALLOW_DESTRUCTIVE_DB_TESTS",
)
class AlembicMigrationTests(unittest.TestCase):
    """Upgrade/downgrade integration test for the RecoverAI Alembic migration."""

    # ------------------------------------------------------------------
    # Assertion helpers
    # ------------------------------------------------------------------

    def _assert_fk(
        self,
        inspector,
        table: str,
        constrained_cols: list[str],
        referred_table: str,
    ) -> None:
        """Assert that a FK constraint (single or composite) exists on *table*."""
        fks = inspector.get_foreign_keys(table)
        target = frozenset(constrained_cols)
        for fk in fks:
            if (
                frozenset(fk["constrained_columns"]) == target
                and fk["referred_table"] == referred_table
            ):
                return
        self.fail(
            f"Expected FK {table}({sorted(constrained_cols)!r}) → {referred_table!r} "
            f"not found.\n"
            f"Existing FKs: "
            f"{[(sorted(fk['constrained_columns']), fk['referred_table']) for fk in fks]}"
        )

    def _assert_unique_constraint(
        self, inspector, table: str, columns: list[str]
    ) -> None:
        """Assert that a unique *constraint* covering *columns* exists on *table*.

        Note: unique *indexes* created with op.create_index(..., unique=True) do NOT
        appear here; use _assert_index for those.
        """
        uqs = inspector.get_unique_constraints(table)
        target = frozenset(columns)
        for uq in uqs:
            if frozenset(uq["column_names"]) == target:
                return
        self.fail(
            f"Expected unique constraint on {table}({sorted(columns)!r}) not found.\n"
            f"Existing unique constraints: {[sorted(uq['column_names']) for uq in uqs]}"
        )

    def _assert_check_constraint(
        self, inspector, table: str, constraint_name: str
    ) -> None:
        """Assert that a named check constraint exists on *table*."""
        checks = inspector.get_check_constraints(table)
        names = {ck["name"] for ck in checks}
        self.assertIn(
            constraint_name,
            names,
            f"Expected check constraint {constraint_name!r} on {table!r}. "
            f"Found: {sorted(names)}",
        )

    def _assert_index(self, inspector, table: str, index_name: str) -> None:
        """Assert that a named index exists on *table*."""
        indexes = inspector.get_indexes(table)
        names = {idx["name"] for idx in indexes}
        self.assertIn(
            index_name,
            names,
            f"Expected index {index_name!r} on {table!r}. Found: {sorted(names)}",
        )

    def _get_columns_dict(self, inspector, table: str) -> dict:
        """Return {column_name: column_info} for *table*."""
        return {col["name"]: col for col in inspector.get_columns(table)}

    # ------------------------------------------------------------------
    # Schema verification (called after upgrade)
    # ------------------------------------------------------------------

    def _verify_schema(self, inspector) -> None:
        """Run all post-upgrade schema assertions."""

        # 1. All seven expected tables exist.
        created_tables = EXPECTED_TABLES & set(inspector.get_table_names())
        self.assertSetEqual(
            created_tables,
            EXPECTED_TABLES,
            "Not all expected tables were created by the migration.",
        )

        # 2. Every table has 'id' as its primary key.
        for table in EXPECTED_TABLES:
            pk = inspector.get_pk_constraint(table)
            self.assertIn(
                "id",
                pk["constrained_columns"],
                f"Table {table!r} does not have 'id' as its primary key. PK: {pk}",
            )

        # 3. Simple (single-column) foreign keys.
        self._assert_fk(inspector, "customers", ["merchant_id"], "merchants")
        self._assert_fk(inspector, "orders", ["merchant_id"], "merchants")
        self._assert_fk(inspector, "payments", ["order_id"], "orders")
        self._assert_fk(inspector, "payment_failures", ["payment_id"], "payments")
        self._assert_fk(inspector, "recovery_attempts", ["payment_id"], "payments")
        self._assert_fk(inspector, "ai_decisions", ["payment_id"], "payments")

        # 4. Composite FK: merchant/customer tenant isolation.
        #    orders(customer_id, merchant_id) → customers(id, merchant_id)
        self._assert_fk(
            inspector,
            "orders",
            ["customer_id", "merchant_id"],
            "customers",
        )

        # 5. Unique constraint backing the tenant-isolation composite FK.
        #    customers(id, merchant_id) must be unique-referenceable.
        self._assert_unique_constraint(inspector, "customers", ["id", "merchant_id"])

        # 6. Composite FK: AI decision / recovery attempt payment coherence.
        #    ai_decisions(recovery_attempt_id, payment_id) → recovery_attempts(id, payment_id)
        self._assert_fk(
            inspector,
            "ai_decisions",
            ["recovery_attempt_id", "payment_id"],
            "recovery_attempts",
        )

        # 7. Unique constraint backing the payment-coherence composite FK.
        #    recovery_attempts(id, payment_id) must be unique-referenceable.
        self._assert_unique_constraint(
            inspector, "recovery_attempts", ["id", "payment_id"]
        )

        # 8. Check constraints.
        self._assert_check_constraint(inspector, "orders", "ck_orders_amount_non_negative")
        self._assert_check_constraint(inspector, "payments", "ck_payments_amount_non_negative")
        self._assert_check_constraint(
            inspector, "ai_decisions", "ck_ai_decisions_confidence_range"
        )

        # 9. Merchants email unique constraint.
        self._assert_unique_constraint(inspector, "merchants", ["email"])

        # 10. Important indexes.
        self._assert_index(inspector, "customers", "ix_customers_merchant_email")
        self._assert_index(inspector, "customers", "ix_customers_merchant_id")
        self._assert_index(inspector, "payments", "ix_payments_provider_payment_id")
        self._assert_index(
            inspector, "recovery_attempts", "ix_recovery_attempts_payment_scheduled_at"
        )
        self._assert_index(inspector, "ai_decisions", "ix_ai_decisions_payment_id")
        self._assert_index(
            inspector, "ai_decisions", "ix_ai_decisions_recovery_attempt_id"
        )

        # 11. Nullable / non-nullable fields critical to the integrity fixes.
        ra_cols = self._get_columns_dict(inspector, "recovery_attempts")
        self.assertTrue(
            ra_cols["executed_at"]["nullable"],
            "recovery_attempts.executed_at must be nullable.",
        )
        self.assertFalse(
            ra_cols["payment_id"]["nullable"],
            "recovery_attempts.payment_id must NOT be nullable.",
        )

        ai_cols = self._get_columns_dict(inspector, "ai_decisions")
        self.assertTrue(
            ai_cols["recovery_attempt_id"]["nullable"],
            "ai_decisions.recovery_attempt_id must be nullable "
            "(recovery attempt is optional).",
        )
        self.assertFalse(
            ai_cols["payment_id"]["nullable"],
            "ai_decisions.payment_id must NOT be nullable.",
        )

    # ------------------------------------------------------------------
    # Main test
    # ------------------------------------------------------------------

    def test_upgrade_and_downgrade(self) -> None:
        from alembic import command
        from alembic.config import Config
        from alembic.runtime.migration import MigrationContext
        from alembic.script import ScriptDirectory
        from sqlalchemy import inspect, text

        from app.db.session import engine

        config = Config(str(ALEMBIC_CONFIG_PATH))

        # Safety check: refuse to touch a database that already has RecoverAI
        # tables or Alembic migration state.
        initial_tables = set(inspect(engine).get_table_names())
        existing_application_tables = EXPECTED_TABLES & initial_tables
        if existing_application_tables or "alembic_version" in initial_tables:
            self.skipTest(
                "Database already has RecoverAI tables or Alembic migration state. "
                "The destructive migration test will not alter an existing database.\n"
                f"Detected: {sorted(existing_application_tables or {'alembic_version'})}"
            )

        migration_applied = False
        try:
            # --- Upgrade to head ---
            command.upgrade(config, "head")
            migration_applied = True

            # --- Comprehensive schema verification ---
            self._verify_schema(inspect(engine))

            # --- Alembic revision must be at head ---
            expected_revision = ScriptDirectory.from_config(config).get_current_head()
            with engine.connect() as connection:
                current_revision = MigrationContext.configure(connection).get_current_revision()
            self.assertEqual(
                current_revision,
                expected_revision,
                f"Alembic revision mismatch after upgrade: "
                f"current={current_revision!r}, expected={expected_revision!r}",
            )

            # --- Downgrade to base ---
            command.downgrade(config, "base")
            migration_applied = False

            remaining_tables = EXPECTED_TABLES & set(inspect(engine).get_table_names())
            self.assertSetEqual(
                remaining_tables,
                set(),
                f"Application tables still present after downgrade to base: "
                f"{sorted(remaining_tables)}",
            )

        finally:
            # Robust cleanup: if upgrade succeeded but a later step (verification or
            # downgrade) raised, attempt to roll back so we leave the database clean.
            # Only reachable when the RECOVERAI_ALLOW_DESTRUCTIVE_DB_TESTS opt-in is
            # active (enforced at class level via @skipUnless).
            if migration_applied:
                try:
                    command.downgrade(config, "base")
                except Exception:
                    pass  # best-effort; log visible in pytest output above

            # Remove alembic_version if it was left behind by a failed downgrade.
            try:
                with engine.begin() as connection:
                    connection.execute(text("DROP TABLE IF EXISTS alembic_version"))
            except Exception:
                pass
