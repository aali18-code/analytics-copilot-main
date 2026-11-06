"""One synthetic export through the Dashboard API, including the PPT download."""

from __future__ import annotations

import io
import os
import unittest
from unittest.mock import patch

import pandas as pd
from fastapi.testclient import TestClient

from backend_modules.dashboard import snapshot_store
from backend_modules.main import app


def _servicenow_workbook() -> bytes:
    frame = pd.DataFrame(
        {
            "Number": ["TASK000", "TASK001", "TASK002"],
            "SLA definition": ["Standard", "Standard", "Priority"],
            "Stage": ["Completed", "Completed", "Cancelled"],
            "Business duration": [1800, 3600, 7200],
            "Created": ["2026-07-30", "2026-08-02", "2026-08-03"],
        }
    )
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        frame.to_excel(writer, sheet_name="raw data", index=False)
    return output.getvalue()


class DashboardApiTest(unittest.TestCase):
    def setUp(self) -> None:
        password_env = patch.dict(os.environ, {"POC_ACCESS_PASSWORD": "synthetic-demo-password"})
        password_env.start()
        self.addCleanup(password_env.stop)
        snapshot_store._store = snapshot_store.MemoryStore()
        self.client = TestClient(app)
        token = self.client.post("/api/auth/login", json={"password": "synthetic-demo-password"}).json()["token"]
        self.client.headers.update({"Authorization": f"Bearer {token}"})

    def test_upload_save_read_and_report(self) -> None:
        upload = self.client.post(
            "/api/dashboard/uploads/inspect",
            files={"file": ("service.xlsx", _servicenow_workbook(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
        self.assertEqual(upload.status_code, 200, upload.text)
        inspected = upload.json()
        self.assertEqual(inspected["source"], "ServiceNow")
        self.assertTrue(inspected["period_filters_rows"])
        self.assertEqual(inspected["period_start"], "2026-07-01")
        self.assertEqual(inspected["period_end"], "2026-08-31")

        invalid_period = self.client.post(
            "/api/dashboard/snapshots",
            json={"upload_id": inspected["upload_id"], "period_start": "2026-08-31", "period_end": "2026-08-01", "generate_ai": False},
        )
        self.assertEqual(invalid_period.status_code, 422)

        saved = self.client.post(
            "/api/dashboard/snapshots",
            json={
                "upload_id": inspected["upload_id"],
                "period_start": inspected["period_start"],
                "period_end": inspected["period_end"],
                "generate_ai": False,
            },
        )
        self.assertEqual(saved.status_code, 201, saved.text)
        self.assertEqual(saved.json()["snapshot"]["kpis"]["sn_total_tasks"]["value"], 3)

        reused = self.client.post(
            "/api/dashboard/snapshots",
            json={"upload_id": inspected["upload_id"], "period_start": inspected["period_start"], "period_end": inspected["period_end"], "generate_ai": False},
        )
        self.assertEqual(reused.status_code, 404)

        periods = self.client.get("/api/dashboard/periods")
        self.assertEqual(periods.json()["periods"][0]["sources"], ["ServiceNow"])
        period = self.client.get("/api/dashboard/periods/2026-07-01/2026-08-31")
        self.assertEqual(period.status_code, 200)
        self.assertIsNone(period.json()["sources"]["Traackr"])

        report = self.client.get("/api/dashboard/periods/2026-07-01/2026-08-31/report")
        self.assertEqual(report.status_code, 200, report.text)
        self.assertTrue(report.content.startswith(b"PK"))


if __name__ == "__main__":
    unittest.main()
