import unittest

from datapilot.sql_safety import UnsafeQueryError, validate_readonly_sql


class SqlSafetyTests(unittest.TestCase):
    def test_select_and_with_are_allowed(self) -> None:
        tables = {"sales_data"}
        self.assertIn("SELECT", validate_readonly_sql("SELECT * FROM sales_data", tables))
        self.assertIn(
            "WITH",
            validate_readonly_sql(
                "WITH totals AS (SELECT COUNT(*) n FROM sales_data) SELECT * FROM totals",
                tables,
            ),
        )

    def test_mutations_external_reads_and_multiple_statements_are_blocked(self) -> None:
        queries = [
            "DELETE FROM sales_data",
            "SELECT * FROM read_csv_auto('secret.csv')",
            "SELECT * FROM sales_data; DROP TABLE sales_data",
            "SELECT * FROM sales_data -- bypass",
            "PRAGMA show_tables",
        ]
        for query in queries:
            with self.subTest(query=query), self.assertRaises(UnsafeQueryError):
                validate_readonly_sql(query, {"sales_data"})

    def test_query_must_reference_selected_dataset(self) -> None:
        with self.assertRaises(UnsafeQueryError):
            validate_readonly_sql("SELECT current_date", {"sales_data"})

