import unittest
from unittest.mock import patch

from flask import Flask

from app.routes.API_kingsman import api_kingsman_bp


class KingsmanCorsTests(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.config.update(
            SECRET_KEY="test-secret",
            TESTING=True,
            KINGSMAN_SCHEMA="kingsman_db",
            MUSIC_SCHOOL_SCHEMA="music_db",
            KINGSMAN_CORS_ORIGINS="https://portal.kingsman.test, https://admin.kingsman.test",
        )
        app.register_blueprint(api_kingsman_bp)
        self.client = app.test_client()

        execute_patcher = patch("app.routes.API_kingsman.db.session.execute")
        rollback_patcher = patch("app.routes.API_kingsman.db.session.rollback")
        self.mock_execute = execute_patcher.start()
        self.mock_rollback = rollback_patcher.start()
        self.addCleanup(execute_patcher.stop)
        self.addCleanup(rollback_patcher.stop)

    def test_health_sets_cors_headers_for_allowed_origin(self):
        response = self.client.get(
            "/api/kingsman/v1/health",
            headers={"Origin": "https://portal.kingsman.test"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("Access-Control-Allow-Origin"), "https://portal.kingsman.test")
        self.assertEqual(response.headers.get("Access-Control-Allow-Credentials"), "true")

    def test_health_does_not_set_cors_headers_for_disallowed_origin(self):
        response = self.client.get(
            "/api/kingsman/v1/health",
            headers={"Origin": "https://attacker.example"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.headers.get("Access-Control-Allow-Origin"))

    def test_options_preflight_returns_204_with_cors_headers(self):
        response = self.client.options(
            "/api/kingsman/v1/auth/login",
            headers={"Origin": "https://admin.kingsman.test"},
        )

        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.data, b"")
        self.assertEqual(response.headers.get("Access-Control-Allow-Origin"), "https://admin.kingsman.test")
        self.assertIn("OPTIONS", response.headers.get("Access-Control-Allow-Methods", ""))


if __name__ == "__main__":
    unittest.main()
