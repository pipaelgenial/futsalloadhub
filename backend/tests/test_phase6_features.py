"""
Phase 6 backend tests:
- POST /api/sessions accepts session_type and defaults to 'training'.
- Invalid session_type returns 400 'Tipo de sessão inválido'.
- PUT /api/sessions/{id} updates session_type and validates.
- GET /api/calendar exposes session_types map per day and session_type per athlete entry.
- Seed creates sessions with weekday-mapped session_type distribution
  (Sat=match, Tue=gym, Sun=recovery, others=training).
"""
import os
from datetime import date, timedelta

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
COACH_EMAIL = "treinador@futsal.pt"
COACH_PASSWORD = "treinador123"


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": COACH_EMAIL, "password": COACH_PASSWORD})
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    token = r.json().get("token")
    if token:
        s.headers.update({"Authorization": f"Bearer {token}"})
    # ensure demo data
    seed = s.post(f"{BASE_URL}/api/seed/demo")
    assert seed.status_code in (200, 201)
    return s


@pytest.fixture(scope="module")
def athlete_id(client):
    r = client.get(f"{BASE_URL}/api/athletes")
    assert r.status_code == 200
    athletes = r.json()
    assert len(athletes) > 0
    return athletes[0]["id"]


# ---------- POST /api/sessions session_type ----------
class TestSessionTypeCreate:
    def test_create_with_explicit_session_type_match(self, client, athlete_id):
        payload = {
            "athlete_id": athlete_id,
            "date": date.today().isoformat(),
            "rpe": 7,
            "duration_min": 60,
            "sleep_quality": 4,
            "wellness": 7,
            "session_type": "match",
        }
        r = client.post(f"{BASE_URL}/api/sessions", json=payload)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["session_type"] == "match"
        assert data["load"] == 420
        # verify persistence
        ses_id = data["id"]
        list_r = client.get(f"{BASE_URL}/api/sessions", params={"athlete_id": athlete_id})
        assert list_r.status_code == 200
        match = next((s for s in list_r.json() if s["id"] == ses_id), None)
        assert match is not None
        assert match["session_type"] == "match"

    def test_create_defaults_to_training_when_omitted(self, client, athlete_id):
        payload = {
            "athlete_id": athlete_id,
            "date": date.today().isoformat(),
            "rpe": 5,
            "duration_min": 50,
            "sleep_quality": 4,
            "wellness": 6,
        }
        r = client.post(f"{BASE_URL}/api/sessions", json=payload)
        assert r.status_code == 200, r.text
        assert r.json()["session_type"] == "training"

    def test_create_invalid_session_type_returns_400(self, client, athlete_id):
        payload = {
            "athlete_id": athlete_id,
            "date": date.today().isoformat(),
            "rpe": 5,
            "duration_min": 50,
            "sleep_quality": 4,
            "wellness": 6,
            "session_type": "yoga",
        }
        r = client.post(f"{BASE_URL}/api/sessions", json=payload)
        assert r.status_code == 400, r.text
        body = r.json()
        detail = body.get("detail") or body.get("message") or ""
        assert "Tipo de sessão inválido" in detail or "inv" in detail.lower()

    @pytest.mark.parametrize("stype", ["training", "match", "gym", "recovery"])
    def test_create_all_valid_types(self, client, athlete_id, stype):
        payload = {
            "athlete_id": athlete_id,
            "date": date.today().isoformat(),
            "rpe": 4,
            "duration_min": 30,
            "sleep_quality": 4,
            "wellness": 7,
            "session_type": stype,
        }
        r = client.post(f"{BASE_URL}/api/sessions", json=payload)
        assert r.status_code == 200, r.text
        assert r.json()["session_type"] == stype


# ---------- PUT /api/sessions/{id} session_type ----------
class TestSessionTypeUpdate:
    def test_update_session_type_to_gym(self, client, athlete_id):
        # create one
        create_r = client.post(
            f"{BASE_URL}/api/sessions",
            json={
                "athlete_id": athlete_id,
                "date": date.today().isoformat(),
                "rpe": 6,
                "duration_min": 45,
                "sleep_quality": 3,
                "wellness": 7,
                "session_type": "training",
            },
        )
        assert create_r.status_code == 200
        sid = create_r.json()["id"]
        # update
        upd = client.put(
            f"{BASE_URL}/api/sessions/{sid}", json={"session_type": "gym"}
        )
        assert upd.status_code == 200, upd.text
        # verify persisted
        list_r = client.get(f"{BASE_URL}/api/sessions", params={"athlete_id": athlete_id})
        match = next((s for s in list_r.json() if s["id"] == sid), None)
        assert match is not None
        assert match["session_type"] == "gym"

    def test_update_invalid_session_type_returns_400(self, client, athlete_id):
        create_r = client.post(
            f"{BASE_URL}/api/sessions",
            json={
                "athlete_id": athlete_id,
                "date": date.today().isoformat(),
                "rpe": 6,
                "duration_min": 45,
                "sleep_quality": 3,
                "wellness": 7,
                "session_type": "training",
            },
        )
        sid = create_r.json()["id"]
        bad = client.put(
            f"{BASE_URL}/api/sessions/{sid}", json={"session_type": "stretching"}
        )
        assert bad.status_code == 400, bad.text
        detail = bad.json().get("detail", "")
        assert "Tipo de sessão inválido" in detail


# ---------- GET /api/calendar exposes session_types ----------
class TestCalendarSessionTypes:
    def test_calendar_days_have_session_types_map(self, client):
        start = (date.today() - timedelta(days=27)).isoformat()
        r = client.get(f"{BASE_URL}/api/calendar", params={"start": start, "days": 28})
        assert r.status_code == 200, r.text
        data = r.json()
        days = data["days"]
        assert len(days) == 28
        # session_types map present on every day
        for d in days:
            assert "session_types" in d
            assert isinstance(d["session_types"], dict)
            # each athlete in athletes list has session_type
            for a in d["athletes"]:
                assert "session_type" in a
                assert a["session_type"] in {"training", "match", "gym", "recovery"}
        # at least one day has non-empty session_types map
        assert any(d["session_types"] for d in days)

    def test_calendar_session_types_have_all_4_types_over_28d(self, client):
        start = (date.today() - timedelta(days=27)).isoformat()
        r = client.get(f"{BASE_URL}/api/calendar", params={"start": start, "days": 28})
        days = r.json()["days"]
        seen_types = set()
        for d in days:
            seen_types.update(d["session_types"].keys())
        # Over 4 weeks we should see all 4 types from seed distribution
        assert {"training", "match", "gym", "recovery"}.issubset(seen_types), (
            f"Expected all 4 types, saw {seen_types}"
        )


# ---------- Seed distribution by weekday ----------
class TestSeedSessionTypeByWeekday:
    def test_seed_weekday_distribution(self, client):
        # Use 30-day window for stable sampling
        start_d = date.today() - timedelta(days=29)
        r = client.get(
            f"{BASE_URL}/api/calendar",
            params={"start": start_d.isoformat(), "days": 30},
        )
        assert r.status_code == 200
        days = r.json()["days"]
        # build (weekday -> {type: count})
        per_wd = {wd: {"training": 0, "match": 0, "gym": 0, "recovery": 0} for wd in range(7)}
        for d in days:
            wd = d["weekday"]
            for t, c in d["session_types"].items():
                per_wd[wd][t] += c
        # Sat=5 -> match dominates
        sat = per_wd[5]
        assert sat["match"] >= sum(v for k, v in sat.items() if k != "match"), per_wd
        # Tue=1 -> gym dominates
        tue = per_wd[1]
        assert tue["gym"] >= sum(v for k, v in tue.items() if k != "gym"), per_wd
        # Sun=6 -> recovery dominates
        sun = per_wd[6]
        assert sun["recovery"] >= sum(v for k, v in sun.items() if k != "recovery"), per_wd
        # Mon/Wed/Thu/Fri -> training dominates (sample Wed)
        wed = per_wd[2]
        assert wed["training"] >= sum(v for k, v in wed.items() if k != "training"), per_wd
