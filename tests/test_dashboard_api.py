"""One synthetic export through the Dashboard API, including the PPT download."""

from __future__ import annotations

import base64
import io
import os
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd
from fastapi.testclient import TestClient
from PIL import Image
from pptx import Presentation

from backend_modules.dashboard import dashboard_ai, generated as generated_dashboard, snapshot_store
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
        pd.DataFrame({"Market": ["UK"], "Channel": ["Social"], "Budget": [250]}).to_excel(writer, sheet_name="Other table", index=False)
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

        picture = io.BytesIO()
        Image.new("RGB", (12, 8), "white").save(picture, format="PNG")
        chart_image = "data:image/png;base64," + base64.b64encode(picture.getvalue()).decode("ascii")
        visual_report = self.client.post(
            "/api/dashboard/periods/2026-07-01/2026-08-31/report",
            json={"chart_images": {"sn_tasks_by_sla": chart_image}},
        )
        self.assertEqual(visual_report.status_code, 200, visual_report.text)
        slides = Presentation(io.BytesIO(visual_report.content)).slides
        self.assertTrue(any(shape.shape_type == 13 for slide in slides for shape in slide.shapes))

        unknown_chart = self.client.post(
            "/api/dashboard/periods/2026-07-01/2026-08-31/report",
            json={"chart_images": {"unknown": chart_image}},
        )
        self.assertEqual(unknown_chart.status_code, 422)
        invalid_chart = self.client.post(
            "/api/dashboard/periods/2026-07-01/2026-08-31/report",
            json={"chart_images": {"sn_tasks_by_sla": "data:image/png;base64,bm90LXBuZw=="}},
        )
        self.assertEqual(invalid_chart.status_code, 422)

    def test_prefilled_snapshot_then_generated_metrics_from_same_upload(self) -> None:
        upload = self.client.post(
            "/api/dashboard/uploads/inspect",
            files={"file": ("service.xlsx", _servicenow_workbook(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
        self.assertEqual(upload.status_code, 200, upload.text)
        inspected = upload.json()

        saved = self.client.post("/api/dashboard/snapshots", json={
            "upload_id": inspected["upload_id"], "period_start": "2026-07-01",
            "period_end": "2026-08-31", "generate_ai": False,
        })
        self.assertEqual(saved.status_code, 201, saved.text)
        self.assertEqual(saved.json()["snapshot"]["kpis"]["sn_total_tasks"]["value"], 3)

        class FakeRouter:
            settings = SimpleNamespace(problems=lambda: [])
            calls = []

            def chat(self, messages, **kwargs):
                self.calls.append((messages, kwargs))
                if len(self.calls) == 1:
                    plan = {"sources": {"ServiceNow": [
                        {"title": "Tasks", "unit": "count", "kind": "card", "code": "result = len(servicenow_raw_data)"},
                        {"title": "Duration", "unit": "seconds", "kind": "card", "code": "result = servicenow_raw_data['Business duration'].sum()"},
                    ]}}
                    return SimpleNamespace(text=__import__("json").dumps(plan), model=SimpleNamespace(label="test-model"))
                return SimpleNamespace(text='{"GS1": {"insight": "Tasks were recorded.", "recommendation": "Review the task mix."}, "GS2": {"insight": "Duration was recorded.", "recommendation": "Review long tasks."}}', model=SimpleNamespace(label="test-model"))

        router = FakeRouter()
        with patch("backend_modules.dashboard.dashboard_ai.make_router", return_value=router):
            generated = self.client.post("/api/dashboard/generated", json={"upload_ids": [inspected["upload_id"]]})
        self.assertEqual(generated.status_code, 200, generated.text)
        self.assertEqual([m["value"] for m in generated.json()["sources"]["ServiceNow"]["metrics"]], [3, 12600])
        self.assertEqual(len(router.calls), 2)
        self.assertEqual(generated.json()["insights"]["entries"]["GS1"]["insight"], "Tasks were recorded.")
        first_prompt = router.calls[0][0][1]["content"]
        self.assertIn("sample_rows", first_prompt)
        self.assertIn("Business duration", first_prompt)
        self.assertIn("TASK000", first_prompt)  # original workbook columns and samples are profiled
        self.assertIn("Other table", first_prompt)
        self.assertIn("Budget", first_prompt)

    def test_large_profile_is_planned_per_source(self) -> None:
        profile = [
            {"source": source, "file_name": f"{source}.xlsx", "tables": [
                {"sheet": "Sheet1", "alias": f"{source.lower()}_sheet1", "columns": ["Value"],
                 "sample_rows": [[1] for _ in range(5)]}
            ]}
            for source in ("ServiceNow", "Traackr", "Sprinklr")
        ]

        class FakeRouter:
            calls = []

            def chat(self, messages, **kwargs):
                self.calls.append(messages)
                batch = __import__("json").loads(messages[1]["content"])
                source = batch[0]["source"]
                return SimpleNamespace(text=__import__("json").dumps({"sources": {source: []}}),
                                       model=SimpleNamespace(label="test-model"))

        router = FakeRouter()
        with patch.object(generated_dashboard, "MAX_PROFILE_CHARS", 10):
            plans, model = generated_dashboard._plan(profile, router)
        self.assertEqual(set(plans), {"ServiceNow", "Traackr", "Sprinklr"})
        self.assertEqual(len(router.calls), 3)
        self.assertEqual(model, "test-model")

    def test_dashboard_model_priority_is_strict_on_every_call(self) -> None:
        router = dashboard_ai.make_router()
        expected = ["gemini-3.8-flash", "gemini-3.6-flash", "gemini-3.5-flash-lite", "gemini-3.1-flash-lite"]
        self.assertEqual([model.model for model in router.settings.models], expected)
        self.assertTrue(router.strict_order)
        primary = router.settings.models[0]
        router._cooldown_until[primary] = time.time() + 600
        attempted = []

        def complete(spec, *_args):
            attempted.append(spec.model)
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="OK"), finish_reason="stop")], usage=None)

        with patch.object(router, "_complete", side_effect=complete), patch(
            "backend_modules.ask_ai.engine.observability.start_call",
            return_value=SimpleNamespace(finish=lambda **_kwargs: None),
        ):
            router.chat([{"role": "user", "content": "hello"}], max_tokens=20)
        self.assertEqual(attempted, [expected[0]])


if __name__ == "__main__":
    unittest.main()
