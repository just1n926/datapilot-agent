import time
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from datapilot.api import create_app
from datapilot.config import Settings


CSV = b"Region,Revenue,Cost\nNorth,100,60\nSouth,200,120\nNorth,150,90\n"


class ApiTests(unittest.TestCase):
    def test_upload_and_async_analysis(self) -> None:
        app = create_app(Settings(mode="demo", demo_file=None))
        with TestClient(app) as client:
            upload = client.post(
                "/api/datasets",
                files={"file": ("sales.csv", CSV, "text/csv")},
            )
            self.assertEqual(upload.status_code, 201)
            dataset = upload.json()

            response = client.post(
                "/api/analyses",
                json={
                    "dataset_id": dataset["id"],
                    "table": "data",
                    "question": "按地区分析收入和利润",
                },
            )
            self.assertEqual(response.status_code, 202)
            run = response.json()
            for _ in range(100):
                if run["status"] != "running":
                    break
                time.sleep(0.02)
                run = client.get(f"/api/analyses/{run['id']}").json()
            self.assertEqual(run["status"], "completed")
            self.assertEqual(run["chart"]["type"], "bar")

    def test_homepage_loads(self) -> None:
        app = create_app(Settings(mode="demo", demo_file=None))
        with TestClient(app) as client:
            response = client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("DataPilot", response.text)

    def test_public_demo_can_disable_uploads(self) -> None:
        app = create_app(Settings(mode="demo", demo_file=None, allow_uploads=False))
        with TestClient(app) as client:
            health = client.get("/health")
            upload = client.post(
                "/api/datasets",
                files={"file": ("sales.csv", CSV, "text/csv")},
            )
        self.assertFalse(health.json()["uploads_enabled"])
        self.assertEqual(upload.status_code, 403)

    def test_configured_demo_file_is_loaded(self) -> None:
        demo_file = Path(__file__).parents[1] / "sample_data" / "sales_demo.xlsx"
        app = create_app(Settings(mode="demo", demo_file=demo_file, allow_uploads=False))
        with TestClient(app) as client:
            health = client.get("/health").json()
            datasets = client.get("/api/datasets").json()
        self.assertEqual(health["datasets"], 1)
        self.assertEqual(datasets[0]["filename"], "sales_demo.xlsx")
