import unittest

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

# Each entry: set of (frozenset(constrained_columns), referred_table).
# Using frozenset captures composite FKs correctly — a single-column FK is
# represented as frozenset(["col"]) and a composite FK as frozenset(["a", "b"]).
EXPECTED_FOREIGN_KEYS: dict[str, set[tuple[frozenset, str]]] = {
    "customers": {
        (frozenset(["merchant_id"]), "merchants"),
    },
    "orders": {
        (frozenset(["merchant_id"]), "merchants"),
        # Composite FK enforcing tenant isolation (Fix 1).
        (frozenset(["customer_id", "merchant_id"]), "customers"),
    },
    "payments": {
        (frozenset(["order_id"]), "orders"),
    },
    "payment_failures": {
        (frozenset(["payment_id"]), "payments"),
    },
    "recovery_attempts": {
        (frozenset(["payment_id"]), "payments"),
    },
    "ai_decisions": {
        (frozenset(["payment_id"]), "payments"),
        # Composite FK enforcing payment coherence (Fix 2).
        (frozenset(["recovery_attempt_id", "payment_id"]), "recovery_attempts"),
    },
}


@unittest.skipUnless(get_settings().database_url, "DATABASE_URL is not configured.")
class DatabaseSchemaTests(unittest.TestCase):
    def test_schema_creation_and_foreign_keys(self) -> None:
        from sqlalchemy import inspect

        from app.db.base import Base
        from app.db.schema import create_schema
        from app.db.session import engine

        existing_tables = set(inspect(engine).get_table_names())
        existing_application_tables = EXPECTED_TABLES & existing_tables
        if existing_application_tables:
            self.skipTest(
                "RecoverAI tables already exist; schema test will not alter existing data."
            )

        try:
            create_schema()
            inspector = inspect(engine)
            created_tables = EXPECTED_TABLES & set(inspector.get_table_names())

            self.assertSetEqual(created_tables, EXPECTED_TABLES)

            for table_name, expected_fks in EXPECTED_FOREIGN_KEYS.items():
                actual_fks = {
                    (frozenset(fk["constrained_columns"]), fk["referred_table"])
                    for fk in inspector.get_foreign_keys(table_name)
                }
                self.assertSetEqual(
                    actual_fks,
                    expected_fks,
                    f"Foreign key mismatch on table {table_name!r}.\n"
                    f"  Expected: {sorted((sorted(c), r) for c, r in expected_fks)}\n"
                    f"  Actual:   {sorted((sorted(c), r) for c, r in actual_fks)}",
                )
        finally:
            Base.metadata.drop_all(bind=engine)
