import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient
from httpx import Cookies
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import CHINA
from app.main import create_app
from app.models import LoginSession, User, WorkRecord


class AuthTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.app = create_app(self.root)
        self.client = TestClient(self.app)
        self.client.__enter__()
        self.database = self.app.state.database

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.temp.cleanup()

    @staticmethod
    def account(username):
        return username.lower().translate(str.maketrans("0123456789", "abcdefghij"))

    def register(self, username="Worker01"):
        cookies = Cookies(self.client.cookies)
        self.client.cookies.clear()
        self.login("admin")
        result = self.client.post("/api/users", json={"username": self.account(username), "name": username})
        self.client.post("/api/auth/logout")
        self.client.cookies.clear()
        self.client.cookies.update(cookies)
        return result

    def login(self, username="Worker01", password="123456"):
        return self.client.post("/api/auth/login", json={"username": self.account(username), "password": password})

    def test_admin_creation_validation_defaults_and_unique(self):
        for name in ("invalid account", "bad_name", "中文", "worker@example.com", "abc\n"):
            self.assertEqual(self.register(name).status_code, 422)
        self.assertEqual(self.register().status_code, 201)
        self.assertEqual(self.register("worker01").status_code, 409)
        self.assertEqual(self.login().status_code, 200)
        data = self.client.get("/api/auth/me").json()
        self.assertEqual((data["name"], data["position"], data["role"]), ("Worker01", "普工", "user"))
        self.assertNotIn("password_hash", data)
        with Session(self.database.accounts) as db:
            self.assertNotEqual(db.scalar(select(User).where(User.username == self.account("Worker01"))).password_hash, "123456")
        self.assertEqual(self.client.post("/api/auth/register", json={"username":"newuser@hengbao.com"}).status_code, 404)
        self.assertEqual(self.client.post("/api/users", json={"username":"other@hengbao.com"}).status_code, 403)

    def test_login_cookie_expiry_and_logout(self):
        self.register()
        self.assertEqual(self.client.get("/api/auth/me").status_code, 401)
        self.assertEqual(self.login(password="incorrect").status_code, 401)
        response = self.login()
        cookie = response.headers["set-cookie"]
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=strict", cookie)
        self.assertIn("expires=", cookie)
        with Session(self.database.accounts) as db:
            login = db.scalar(select(LoginSession))
            expiry = login.expires_at.replace(tzinfo=timezone.utc).astimezone(CHINA)
            self.assertEqual((expiry.hour, expiry.minute, expiry.second), (0, 0, 0))
            self.assertEqual(expiry.date(), datetime.now(CHINA).date() + timedelta(days=1))
        self.assertEqual(self.client.get("/api/auth/me").status_code, 200)
        token = self.client.cookies.get("itime_session")
        self.assertEqual(self.client.post("/api/auth/logout").status_code, 204)
        self.client.cookies.set("itime_session", token)
        self.assertEqual(self.client.get("/api/auth/me").status_code, 401)

    def test_expired_or_disabled_sessions_are_rejected(self):
        self.register()
        self.login()
        with Session(self.database.accounts) as db:
            db.scalar(select(LoginSession)).expires_at = datetime(2000, 1, 1)
            db.commit()
        self.assertEqual(self.client.get("/api/auth/me").status_code, 401)
        self.login()
        with Session(self.database.accounts) as db:
            db.scalar(select(User).where(User.username == self.account("Worker01"))).is_active = False
            db.commit()
        self.assertEqual(self.client.get("/api/auth/me").status_code, 401)
        self.assertEqual(self.login().status_code, 401)
        self.assertEqual(self.register().status_code, 409)

    def test_admin_and_password_change_revoke_sessions(self):
        self.assertEqual(self.login("admin").json()["role"], "admin")
        body = {"current_password": "wrong", "new_password": "newpass123"}
        self.assertEqual(self.client.post("/api/auth/password", json=body).status_code, 400)
        body["current_password"] = "123456"
        self.assertEqual(self.client.post("/api/auth/password", json=body).status_code, 204)
        self.assertEqual(self.client.get("/api/auth/me").status_code, 401)
        self.assertEqual(self.login("admin").status_code, 401)
        self.assertFalse(self.login("admin", "newpass123").json()["must_change_password"])

    def test_cross_site_request_rejected(self):
        response = self.client.post("/api/users", json={"username": "workerone@hengbao.com"}, headers={"Origin": "http://other.example"})
        self.assertEqual(response.status_code, 403)

    def test_initialize_does_not_reset_admin(self):
        self.login("admin")
        self.client.post("/api/auth/password", json={"current_password": "123456", "new_password": "changed123"})
        other = create_app(self.root)
        with TestClient(other) as client:
            self.assertEqual(client.post("/api/auth/login", json={"username": "admin", "password": "changed123"}).status_code, 200)

    def test_year_files_are_separate_and_guard_dates(self):
        first = self.database.year_engine(2025)
        second = self.database.year_engine(2026)
        with Session(first) as db:
            db.add(WorkRecord(user_id=1, work_date=date(2025, 6, 1), project="test", task_type="开发", description="test", hours_tenths=15))
            db.commit()
        with Session(second) as db:
            self.assertIsNone(db.scalar(select(WorkRecord)))
            db.add(WorkRecord(user_id=1, work_date=date(2025, 6, 1), project="test", task_type="开发", description="test", hours_tenths=15))
            with self.assertRaises(IntegrityError):
                db.commit()
            db.rollback()
        self.assertTrue((self.root / "2025/worktime.sqlite3").is_file())
        self.assertTrue((self.root / "2026/worktime.sqlite3").is_file())
        for year in ("../../bad", "2026", 0, True, 2101):
            with self.assertRaises(ValueError):
                self.database.year_engine(year)


if __name__ == "__main__":
    unittest.main()
