"""Synthetic CSV through Ask AI sessions, follow-ups, and downloads."""

from __future__ import annotations

import json
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd
from fastapi.testclient import TestClient

from backend_modules.ask_ai import engine, session_store
from backend_modules.main import app


class AskAiApiTest(unittest.TestCase):
    def setUp(self) -> None:
        password_env = patch.dict(os.environ, {"POC_ACCESS_PASSWORD": "synthetic-demo-password"})
        password_env.start()
        self.addCleanup(password_env.stop)
        session_store._sessions.clear()
        self.client = TestClient(app)
        token = self.client.post("/api/auth/login", json={"password": "synthetic-demo-password"}).json()["token"]
        self.client.headers.update({"Authorization": f"Bearer {token}"})

    def test_session_profile_followup_downloads_and_end(self) -> None:
        created = self.client.post(
            "/api/ask-ai/sessions",
            files=[("files", ("sales.csv", b"month,amount\nJan,10\nFeb,20\n", "text/csv"))],
        )
        self.assertEqual(created.status_code, 201, created.text)
        session_id = created.json()["session_id"]
        alias = created.json()["tables"][0]["Variable"]
        preview = self.client.get(f"/api/ask-ai/sessions/{session_id}/tables/{alias}")
        self.assertEqual(preview.status_code, 200, preview.text)
        self.assertEqual(preview.json()["total_rows"], 2)

        histories = []

        def fake_answer(question, prepared, router, settings, history=None):
            histories.append(list(history or []))
            return engine.AnswerResult(
                ok=True,
                text=f"Answer to {question}",
                tables=[engine.ResultTable("Monthly sales", pd.DataFrame({"month": ["Jan", "Feb"], "amount": [10, 20]}), 2)],
                figures=[b"\x89PNG\r\n\x1a\nexample"],
                plotly_figures=[json.dumps({"data": [{"type": "bar", "x": ["Jan", "Feb"], "y": [10, 20]}], "layout": {}})],
                history=[{"role": "user", "content": question}, {"role": "assistant", "content": "Result"}],
            )

        with patch("backend_modules.ask_ai.api.engine.answer_question", side_effect=fake_answer):
            first = self.client.post(f"/api/ask-ai/sessions/{session_id}/questions", json={"question": "Total sales?"})
            self.assertEqual(first.status_code, 200, first.text)
            answer_id = first.json()["id"]
            self.assertEqual(first.json()["tables"][0]["rows"][0]["amount"], 10)
            self.assertEqual(first.json()["plotly_figures"][0]["data"][0]["type"], "bar")
            self.assertTrue(first.json()["png_figures"][0].startswith("data:image/png;base64,"))

            second = self.client.post(f"/api/ask-ai/sessions/{session_id}/questions", json={"question": "And by month?"})
            self.assertEqual(second.status_code, 200)
            self.assertEqual(len(histories[0]), 0)
            self.assertEqual(len(histories[1]), 2)

        excel = self.client.get(f"/api/ask-ai/sessions/{session_id}/answers/{answer_id}/tables.xlsx")
        self.assertEqual(excel.status_code, 200, excel.text)
        self.assertTrue(excel.content.startswith(b"PK"))
        restored = self.client.get(f"/api/ask-ai/sessions/{session_id}/answers/{answer_id}")
        self.assertEqual(restored.status_code, 200)
        self.assertEqual(restored.json()["tables"][0]["rows"][1]["amount"], 20)
        png = self.client.get(f"/api/ask-ai/sessions/{session_id}/answers/{answer_id}/charts/0.png")
        self.assertEqual(png.status_code, 200)
        self.assertTrue(png.content.startswith(b"\x89PNG"))

        cleared = self.client.post(f"/api/ask-ai/sessions/{session_id}/clear")
        self.assertEqual(cleared.status_code, 200)
        self.assertEqual(self.client.get(f"/api/ask-ai/sessions/{session_id}").json()["messages"], [])
        self.assertEqual(self.client.delete(f"/api/ask-ai/sessions/{session_id}").status_code, 204)
        self.assertEqual(self.client.get(f"/api/ask-ai/sessions/{session_id}").status_code, 404)

    def test_question_uses_uploaded_rows_in_real_code_runner(self) -> None:
        created = self.client.post(
            "/api/ask-ai/sessions",
            files=[("files", ("sales.csv", b"month,amount\nJan,10\nFeb,20\n", "text/csv"))],
        )
        self.assertEqual(created.status_code, 201, created.text)
        session_id = created.json()["session_id"]
        alias = created.json()["tables"][0]["Variable"]
        replies = iter([
            SimpleNamespace(text=f"```python\nresult = {alias}['amount'].sum()\n```", model=SimpleNamespace(label="test-model")),
            SimpleNamespace(text="Total is 30.", model=SimpleNamespace(label="test-model")),
        ])
        with patch.object(engine.LLMRouter, "chat", side_effect=lambda *args, **kwargs: next(replies)):
            response = self.client.post(f"/api/ask-ai/sessions/{session_id}/questions", json={"question": "What is total sales?"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.json()["ok"])
        self.assertEqual(response.json()["runs"], 1)
        self.assertEqual(response.json()["text"], "Total is 30.")

    def test_multiple_files_are_available_in_one_session(self) -> None:
        response = self.client.post(
            "/api/ask-ai/sessions",
            files=[
                ("files", ("clients.csv", b"client_id,name\nC1,Alpha\nC2,Beta\n", "text/csv")),
                ("files", ("spend.csv", b"client_id,amount\nC1,10\nC2,20\n", "text/csv")),
            ],
        )
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(len(response.json()["tables"]), 2)
        self.assertEqual(response.json()["tables"][0]["Rows"], 2)


if __name__ == "__main__":
    unittest.main()
