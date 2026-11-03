"""Langfuse monitoring response and setup state, without external calls."""

from __future__ import annotations

import os
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend_modules.llm_monitoring import api
from backend_modules.main import app


class MonitoringApiTest(unittest.TestCase):
    def setUp(self) -> None:
        password_env = patch.dict(os.environ, {"POC_ACCESS_PASSWORD": "synthetic-demo-password"})
        password_env.start()
        self.addCleanup(password_env.stop)
        api._cache.clear()
        self.client = TestClient(app)
        token = self.client.post("/api/auth/login", json={"password": "synthetic-demo-password"}).json()["token"]
        self.client.headers.update({"Authorization": f"Bearer {token}"})

    def test_unconfigured_state(self) -> None:
        with patch.object(api.observability, "enabled", return_value=False), patch.object(api.observability, "fetch_calls") as fetch:
            response = self.client.get("/api/monitoring/calls")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["configured"])
        self.assertEqual(response.json()["metrics"]["calls"], 0)
        fetch.assert_not_called()

    def test_totals_count_all_calls_table_is_limited_and_cached(self) -> None:
        rows = [
            {
                "name": "plan-code",
                "start_time": datetime(2026, 11, 3, 8, 0, tzinfo=timezone.utc),
                "model": "demo-model",
                "cost": 0.01,
                "latency": 1.5,
                "input_tokens": 60,
                "output_tokens": 40,
                "total_tokens": 100,
                "status": "ok",
            }
            for _ in range(205)
        ]
        with patch.object(api.observability, "enabled", return_value=True), patch.object(api.observability, "fetch_calls", return_value=rows) as fetch:
            first = self.client.get("/api/monitoring/calls?window=7d")
            second = self.client.get("/api/monitoring/calls?window=7d")
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.json()["metrics"]["calls"], 205)
        self.assertEqual(first.json()["metrics"]["total_tokens"], 20500)
        self.assertAlmostEqual(first.json()["metrics"]["total_cost_usd"], 2.05)
        self.assertEqual(first.json()["metrics"]["average_latency_seconds"], 1.5)
        self.assertEqual(first.json()["shown_calls"], 200)
        self.assertEqual(first.json()["calls"][0]["name"], "Ask AI")
        fetch.assert_called_once_with(days=7)

    def test_langfuse_error_is_reported_without_details(self) -> None:
        with patch.object(api.observability, "enabled", return_value=True), patch.object(api.observability, "fetch_calls", side_effect=RuntimeError("secret URL")):
            response = self.client.get("/api/monitoring/calls?window=all")
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("secret URL", response.text)


if __name__ == "__main__":
    unittest.main()
