"""Phase 4 backend tests: team avg_sleep/avg_monotony, team-detailed, monthly team
overview, calendar, planned-sessions CRUD, seed/demo planned count, reset-all planned.
"""
import os
from datetime import date, timedelta

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"


@pytest.fixture(scope="module")
def coach():
    s = requests.Session()
    r = s.post(f"{API}/auth/login",
               json={"email": "treinador@futsal.pt", "password": "treinador123"}, timeout=20)
    assert r.status_code == 200, r.text
    s.headers.update({"Authorization": f"Bearer {r.json()['token']}"})
    seed = s.post(f"{API}/seed/demo", timeout=60)
    assert seed.status_code == 200, seed.text
    return s


# ----------- Team summary new fields -----------
class TestTeamSummaryNewFields:
    def test_team_has_avg_sleep_avg_monotony_zone(self, coach):
        r = coach.get(f"{API}/analytics/team", timeout=30)
        assert r.status_code == 200
        summary = r.json()["summary"]
        for k in ("avg_sleep", "avg_monotony", "avg_monotony_zone"):
            assert k in summary, f"missing field {k} in team summary: {list(summary.keys())}"
        assert isinstance(summary["avg_sleep"], (int, float))
        assert isinstance(summary["avg_monotony"], (int, float))
        assert summary["avg_monotony_zone"] in (
            "high_variation", "ideal", "moderate_high", "critical", "no_data"
        )


# ----------- Team-detailed -----------
class TestTeamDetailed:
    def test_team_detailed_structure(self, coach):
        r = coach.get(f"{API}/analytics/team-detailed", timeout=30)
        assert r.status_code == 200
        d = r.json()
        for k in ("team", "metrics", "series", "n_athletes"):
            assert k in d, f"missing {k}"
        assert len(d["series"]) == 60, f"expected 60 series entries got {len(d['series'])}"
        for entry in d["series"][:3]:
            for f in ("date", "load", "acute", "chronic", "acwr"):
                assert f in entry
        m = d["metrics"]
        for f in ("sufficient_data", "acwr_zone", "monotony_zone", "strain_zone"):
            assert f in m, f"metrics missing {f}"


# ----------- Monthly team overview -----------
class TestMonthlyTeamOverview:
    def test_monthly_team_overview(self, coach):
        r = coach.get(f"{API}/analytics/monthly/team/overview?months=6", timeout=30)
        assert r.status_code == 200
        d = r.json()
        for k in ("team", "athletes_count", "months", "evolution", "evolution_pct"):
            assert k in d, f"missing {k}"
        assert len(d["months"]) == 6
        # months should have aggregates
        for m in d["months"][:2]:
            assert "month" in m
            for f in ("total_load", "sessions", "avg_load", "avg_sleep"):
                assert f in m, f"month missing {f}: keys={list(m.keys())}"


# ----------- Calendar -----------
class TestCalendar:
    def test_calendar_28_days_structure(self, coach):
        start = date.today().isoformat()
        r = coach.get(f"{API}/calendar?start={start}&days=28", timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("team", "start", "end", "days", "athletes"):
            assert k in d
        assert len(d["days"]) == 28
        for day in d["days"][:3]:
            for f in ("date", "weekday", "total_load", "athletes_count",
                      "athletes", "planned"):
                assert f in day, f"day missing {f}"

    def test_calendar_includes_planned(self, coach):
        # seed already created 5 planned sessions in next ~10 days
        start = date.today().isoformat()
        r = coach.get(f"{API}/calendar?start={start}&days=28", timeout=20)
        days = r.json()["days"]
        total_planned = sum(len(d["planned"]) for d in days)
        assert total_planned >= 5, f"expected >=5 planned in next 28 days, got {total_planned}"


# ----------- Planned sessions CRUD -----------
class TestPlannedSessions:
    def test_create_list_delete(self, coach):
        # Get team to get athletes optional
        ath = coach.get(f"{API}/athletes", timeout=15).json()
        a_ids = [ath[0]["id"], ath[1]["id"]]
        future = (date.today() + timedelta(days=3)).isoformat()
        # CREATE
        r = coach.post(f"{API}/planned-sessions", json={
            "date": future, "planned_rpe": 7, "planned_duration": 75,
            "notes": "TEST_planned", "athlete_ids": a_ids
        }, timeout=15)
        assert r.status_code == 200, r.text
        created = r.json()
        assert created["planned_rpe"] == 7
        assert created["planned_duration"] == 75
        assert created["planned_load"] == 7 * 75
        assert "id" in created
        pid = created["id"]

        # LIST (with start/end filter)
        start = (date.today() - timedelta(days=1)).isoformat()
        end = (date.today() + timedelta(days=10)).isoformat()
        rl = coach.get(f"{API}/planned-sessions?start={start}&end={end}", timeout=15)
        assert rl.status_code == 200
        items = rl.json()
        assert any(p["id"] == pid for p in items), "created planned not in filtered list"

        # DELETE
        rd = coach.delete(f"{API}/planned-sessions/{pid}", timeout=15)
        assert rd.status_code == 200
        # verify gone
        rl2 = coach.get(f"{API}/planned-sessions", timeout=15).json()
        assert not any(p["id"] == pid for p in rl2)


# ----------- Seed/demo planned count + reset-all -----------
class TestSeedAndReset:
    """Runs LAST – wipes data."""
    def test_seed_returns_planned_count(self, coach):
        r = coach.post(f"{API}/seed/demo", timeout=60)
        assert r.status_code == 200
        d = r.json()
        assert "planned" in d
        assert d["planned"] == 5

    def test_reset_all_returns_planned_deleted(self, coach):
        # ensure planned exists
        coach.post(f"{API}/seed/demo", timeout=60)
        # add an explicit one
        coach.post(f"{API}/planned-sessions", json={
            "date": (date.today() + timedelta(days=2)).isoformat(),
            "planned_rpe": 5, "planned_duration": 60
        }, timeout=15)
        r = coach.post(f"{API}/reset-all", timeout=30)
        assert r.status_code == 200
        deleted = r.json()["deleted"]
        assert "planned" in deleted
        assert deleted["planned"] >= 5

        # re-seed for next testing agent to have fresh data
        coach.post(f"{API}/seed/demo", timeout=60)
