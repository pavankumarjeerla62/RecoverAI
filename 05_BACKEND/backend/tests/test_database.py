import unittest

from app.core.config import get_settings


@unittest.skipUnless(get_settings().database_url, "DATABASE_URL is not configured.")
class DatabaseConnectivityTests(unittest.TestCase):
    def test_database_connection(self) -> None:
        from sqlalchemy import text

        from app.db.session import engine

        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1")).scalar_one()

        self.assertEqual(result, 1)
