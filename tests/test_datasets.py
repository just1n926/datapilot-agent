from pathlib import Path
import unittest

from datapilot.config import Settings
from datapilot.datasets import DatasetStore, DatasetValidationError


CSV = b"Region,Revenue,Cost\nNorth,100,60\nSouth,200,120\nNorth,150,90\n"


class DatasetStoreTests(unittest.TestCase):
    def test_csv_load_preview_and_query(self) -> None:
        store = DatasetStore(Settings())
        meta = store.load_bytes("sales.csv", CSV)
        self.assertEqual(meta.primary_table, "data")
        self.assertEqual(meta.tables[0].row_count, 3)
        preview = store.preview(meta.id, "data", 2)
        self.assertEqual(len(preview["rows"]), 2)

        columns, rows = store.query(
            meta.id,
            "SELECT region, SUM(revenue) revenue FROM data GROUP BY 1 ORDER BY revenue DESC",
        )
        self.assertEqual(columns, ["region", "revenue"])
        self.assertEqual(rows[0], ["North", 250])

    def test_excel_demo_loads_sales_data_as_primary_table(self) -> None:
        demo = Path(__file__).parents[1] / "sample_data" / "sales_demo.xlsx"
        store = DatasetStore(Settings())
        meta = store.load_file(demo)
        self.assertEqual(meta.primary_table, "sales_data")
        sales_table = next(table for table in meta.tables if table.name == "sales_data")
        self.assertEqual(sales_table.row_count, 96)

    def test_unsupported_file_is_rejected(self) -> None:
        with self.assertRaises(DatasetValidationError):
            DatasetStore(Settings()).load_bytes("data.json", b"{}")
