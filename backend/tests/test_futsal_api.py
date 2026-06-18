"""Futsal Load Hub backend API tests."""
import os
import uuid

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://futsal-load-hub.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"


@pytest.fixture(scope="module")
def coach_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": "treinador@futsal.pt", "password": "treinador123"}, timeout=20)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    data = r.json()
    assert "token" in data and data["email"] == "treinador@futsal.pt"
    s.headers.update({"Authorization": f"Bearer {data['token']}"})
    return s


@pytest.fixture(scope="module")
def new_coach_session():
    s = requests.Session()
    email = f"TEST_{uuid.uuid4().hex[:8]}@futsal.pt"
    r = s.post(f"{API}/auth/register", json={"email": email, "password": "test123", "name": "Test Coach"}, timeout=20)
    assert r.status_code == 200, f"Register failed: {r.status_code} {r.text}"
    data = r.json()
    s.headers.update({"Authorization": f"Bearer {data['token']}"})
    s.test_email = email
    return s


# ---------------- Auth ----------------
class TestAuth:
    def test_login_success(self, coach_session):
        r = coach_session.get(f"{API}/auth/me", timeout=15)
        assert r.status_code == 200
        assert r.json()["email"] == "treinador@futsal.pt"

    def test_login_invalid(self):
        r = requests.post(f"{API}/auth/login", json={"email": "treinador@futsal.pt", "password": "wrong"}, timeout=15)
        assert r.status_code == 401

    def test_register_new(self, new_coach_session):
        r = new_coach_session.get(f"{API}/auth/me", timeout=15)
        assert r.status_code == 200
        assert r.json()["email"] == new_coach_session.test_email.lower()

    def test_register_duplicate(self, new_coach_session):
        r = requests.post(f"{API}/auth/register", json={"email": new_coach_session.test_email, "password": "test123", "name": "Dup"}, timeout=15)
        assert r.status_code == 400

    def test_unauth_me(self):
        r = requests.get(f"{API}/auth/me", timeout=15)
        assert r.status_code == 401


# ---------------- Seed Demo ----------------
class TestSeedAndAnalytics:
    def test_seed_demo(self, coach_session):
        r = coach_session.post(f"{API}/seed/demo", timeout=60)
        assert r.status_code == 200
        data = r.json()
        assert data["ok"] is True
        assert data["athletes"] == 8
        assert data["sessions"] > 100

    def test_team_after_seed(self, coach_session):
        r = coach_session.get(f"{API}/team", timeout=15)
        assert r.status_code == 200
        t = r.json()
        assert t["name"] == "Sporting Futsal Lisboa"
        assert t["escalao"] == "Sénior"
        assert t["epoca"] == "2025/2026"

    def test_athletes_list(self, coach_session):
        r = coach_session.get(f"{API}/athletes", timeout=15)
        assert r.status_code == 200
        ath = r.json()
        assert len(ath) == 8
        assert all("id" in a and "name" in a for a in ath)

    def test_team_analytics(self, coach_session):
        r = coach_session.get(f"{API}/analytics/team", timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d["team"]["name"] == "Sporting Futsal Lisboa"
        assert d["summary"]["athletes_count"] == 8
        assert len(d["athletes"]) == 8
        # Each athlete must have metrics
        for a in d["athletes"]:
            assert "metrics" in a and "acwr" in a["metrics"] and "risk" in a["metrics"]

    def test_athlete_analytics(self, coach_session):
        ath = coach_session.get(f"{API}/athletes", timeout=15).json()
        aid = ath[0]["id"]
        r = coach_session.get(f"{API}/analytics/athlete/{aid}", timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d["athlete"]["id"] == aid
        assert "metrics" in d and "series" in d
        assert len(d["series"]) == 60
        assert all("acwr" in p and "date" in p for p in d["series"])


# ---------------- Team Profile (new user empty state) ----------------
class TestNewCoachFlow:
    def test_empty_team(self, new_coach_session):
        r = new_coach_session.get(f"{API}/team", timeout=15)
        assert r.status_code == 200
        # should be None / null
        assert r.json() is None

    def test_athletes_empty(self, new_coach_session):
        r = new_coach_session.get(f"{API}/athletes", timeout=15)
        assert r.status_code == 200
        assert r.json() == []

    def test_create_team(self, new_coach_session):
        r = new_coach_session.post(f"{API}/team", json={"name": "TEST_Team", "escalao": "Sub-19", "epoca": "2025/2026"}, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["name"] == "TEST_Team"
        # GET to verify persistence
        r2 = new_coach_session.get(f"{API}/team", timeout=15)
        assert r2.json()["escalao"] == "Sub-19"

    def test_athlete_crud(self, new_coach_session):
        r = new_coach_session.post(f"{API}/athletes", json={"name": "TEST_Atleta", "position": "Ala", "jersey_number": 7}, timeout=15)
        assert r.status_code == 200
        aid = r.json()["id"]
        # GET verify
        ath = new_coach_session.get(f"{API}/athletes", timeout=15).json()
        assert any(a["id"] == aid for a in ath)
        # session log
        from datetime import date
        rs = new_coach_session.post(f"{API}/sessions", json={
            "athlete_id": aid, "date": date.today().isoformat(),
            "rpe": 7, "duration_min": 90, "sleep_quality": 4
        }, timeout=15)
        assert rs.status_code == 200
        assert rs.json()["load"] == 630
        # analytics for athlete (insufficient_data expected since 1 session today)
        ra = new_coach_session.get(f"{API}/analytics/athlete/{aid}", timeout=20)
        assert ra.status_code == 200
        m = ra.json()["metrics"]
        assert m["sufficient_data"] is False
        assert m["days_since_first"] == 0
        # delete
        rd = new_coach_session.delete(f"{API}/athletes/{aid}", timeout=15)
        assert rd.status_code == 200

    def test_logout(self, new_coach_session):
        r = new_coach_session.post(f"{API}/auth/logout", timeout=15)
        assert r.status_code == 200
