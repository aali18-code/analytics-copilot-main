"""Password login, protected APIs, logout, and CORS preflight."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend_modules import auth
from backend_modules.main import app


class AuthTest(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)
        auth._tokens.clear()
        auth._failed.clear()

    def tearDown(self) -> None:
        auth._tokens.clear()
        auth._failed.clear()

    def test_missing_configuration_fails_closed(self) -> None:
        with patch.dict(os.environ, {"POC_ACCESS_PASSWORD": ""}):
            self.assertEqual(self.client.get("/api/dashboard/periods").status_code, 503)
            self.assertEqual(self.client.post("/api/auth/login", json={"password": "anything"}).status_code, 503)
        self.assertEqual(self.client.get("/api/health").status_code, 200)

    def test_login_protected_routes_and_logout(self) -> None:
        with patch.dict(os.environ, {"POC_ACCESS_PASSWORD": "synthetic-demo-password"}):
            self.assertEqual(self.client.get("/api/dashboard/periods").status_code, 401)
            self.assertEqual(self.client.get("/api/monitoring/calls").status_code, 401)
            self.assertEqual(self.client.post("/api/ask-ai/sessions", files=[]).status_code, 401)
            self.assertEqual(self.client.post("/api/auth/login", json={"password": "incorrect"}).status_code, 401)
            logged_in = self.client.post("/api/auth/login", json={"password": "synthetic-demo-password"})
            self.assertEqual(logged_in.status_code, 200)
            self.assertEqual(logged_in.headers.get("Cache-Control"), "no-store")
            token = logged_in.json()["token"]
            headers = {"Authorization": f"Bearer {token}"}
            self.assertTrue(self.client.get("/api/auth/me", headers=headers).json()["authenticated"])
            self.assertEqual(self.client.get("/api/dashboard/periods", headers=headers).status_code, 200)
            self.assertEqual(self.client.post("/api/auth/logout", headers=headers).status_code, 200)
            self.assertEqual(self.client.get("/api/dashboard/periods", headers=headers).status_code, 401)

    def test_preflight_allows_authorization_from_local_frontend(self) -> None:
        response = self.client.options(
            "/api/dashboard/periods",
            headers={"Origin": "http://127.0.0.1:5173", "Access-Control-Request-Method": "GET", "Access-Control-Request-Headers": "authorization"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("Access-Control-Allow-Origin"), "http://127.0.0.1:5173")
        self.assertIn("authorization", response.headers.get("Access-Control-Allow-Headers", "").lower())

    def test_expired_token_is_rejected(self) -> None:
        with patch.dict(os.environ, {"POC_ACCESS_PASSWORD": "synthetic-demo-password"}):
            token = self.client.post("/api/auth/login", json={"password": "synthetic-demo-password"}).json()["token"]
            auth._tokens[auth._digest(token)] = 0
            response = self.client.get("/api/dashboard/periods", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(response.status_code, 401)

    def test_repeated_bad_passwords_are_limited(self) -> None:
        with patch.dict(os.environ, {"POC_ACCESS_PASSWORD": "synthetic-demo-password"}):
            for _ in range(auth.MAX_FAILED_ATTEMPTS):
                self.assertEqual(self.client.post("/api/auth/login", json={"password": "incorrect"}).status_code, 401)
            blocked = self.client.post("/api/auth/login", json={"password": "synthetic-demo-password"})
        self.assertEqual(blocked.status_code, 429)


if __name__ == "__main__":
    unittest.main()
