"""Phase 5 backend tests: wellness field, session update endpoint, weekly summary,
team weekly overview, team summary avg_wellness, wellness-based risk."""
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


@pytest.fixture(scope="module")
def first_athlete(coach):
    r = coach.get(f"{API}/athletes", timeout=20)
    assert r.status_code == 200
    ats = r.json()
    assert ats, "no athletes seeded"
    return ats[0]


# ---------- Wellness on session creation ----------
class TestSessionWellnessField:
    def test_create_session_with_wellness(self, coach, first_athlete):
        today = date.today().isoformat()
        payload = {
            "athlete_id": first_athlete["id"],
            "date": today,
            "rpe": 6,
            "duration_min": 60,
            "sleep_quality": 4,
            "wellness": 8,
            "notes": "TEST_wellness",
        }
        r = coach.post(f"{API}/sessions", json=payload, timeout=20)
        assert r.status_code == 200, r.text
        s = r.json()
        assert s["wellness"] == 8
        assert s["load"] == 360
        # cleanup
        coach.delete(f"{API}/sessions/{s['id']}", timeout=10)

    def test_create_session_default_wellness(self, coach, first_athlete):
        today = date.today().isoformat()
        payload = {
            "athlete_id": first_athlete["id"],
            "date": today,
            "rpe": 5,
            "duration_min": 60,
            "sleep_quality": 3,
        }
        r = coach.post(f"{API}/sessions", json=payload, timeout=20)
        assert r.status_code == 200
        s = r.json()
        assert s["wellness"] == 7, f"expected default 7 got {s.get('wellness')}"
        coach.delete(f"{API}/sessions/{s['id']}", timeout=10)

    def test_wellness_out_of_range_rejected(self, coach, first_athlete):
        payload = {
            "athlete_id": first_athlete["id"],
            "date": date.today().isoformat(),
            "rpe": 5, "duration_min": 60, "sleep_quality": 3, "wellness": 11,
        }
        r = coach.post(f"{API}/sessions", json=payload, timeout=20)
        assert r.status_code in (400, 422)

    def test_seed_creates_wellness_in_range(self, coach):
        r = coach.get(f"{API}/sessions", timeout=30)
        assert r.status_code == 200
        sessions = r.json()
        assert len(sessions) > 0
        with_wellness = [s for s in sessions if s.get("wellness") is not None]
        assert len(with_wellness) > 0
        vals = [s["wellness"] for s in with_wellness]
        assert min(vals) >= 4 and max(vals) <= 9, f"seed wellness out of [4,9]: {min(vals)}-{max(vals)}"


# ---------- PUT /api/sessions/{id} ----------
class TestSessionUpdate:
    def test_update_recomputes_load(self, coach, first_athlete):
        today = date.today().isoformat()
        c = coach.post(f"{API}/sessions", json={
            "athlete_id": first_athlete["id"], "date": today,
            "rpe": 5, "duration_min": 60, "sleep_quality": 3, "wellness": 6,
        }, timeout=20)
        sid = c.json()["id"]

        # update rpe -> new load = 7*60=420
        u = coach.put(f"{API}/sessions/{sid}", json={"rpe": 7}, timeout=20)
        assert u.status_code == 200, u.text
        d = u.json()
        assert d["rpe"] == 7
        assert d["load"] == 420
        assert "updated_at" in d

        # update wellness and duration -> load 7*90=630
        u2 = coach.put(f"{API}/sessions/{sid}",
                       json={"wellness": 9, "duration_min": 90}, timeout=20)
        assert u2.status_code == 200
        d2 = u2.json()
        assert d2["wellness"] == 9
        assert d2["duration_min"] == 90
        assert d2["load"] == 630

        # verify persistence
        listed = coach.get(f"{API}/sessions?athlete_id={first_athlete['id']}", timeout=20).json()
        match = next((x for x in listed if x["id"] == sid), None)
        assert match is not None
        assert match["wellness"] == 9 and match["load"] == 630

        coach.delete(f"{API}/sessions/{sid}", timeout=10)

    def test_update_nonexistent_returns_404(self, coach):
        r = coach.put(f"{API}/sessions/does-not-exist", json={"rpe": 5}, timeout=20)
        assert r.status_code == 404


# ---------- Athlete metrics include wellness fields ----------
class TestAthleteMetricsWellness:
    def test_metrics_has_wellness_fields(self, coach, first_athlete):
        r = coach.get(f"{API}/analytics/athlete/{first_athlete['id']}", timeout=30)
        assert r.status_code == 200
        m = r.json()["metrics"]
        for k in ("wellness_7d", "wellness_zone", "avg_wellness"):
            assert k in m, f"missing {k} in metrics: {list(m.keys())}"
        assert m["wellness_zone"] in (
            "depleted", "fatigued", "moderate", "good", "excellent", "no_data"
        )
        assert isinstance(m["wellness_7d"], (int, float))


# ---------- Wellness-based risk integration ----------
class TestWellnessRisk:
    def test_low_wellness_forces_danger(self, coach, first_athlete):
        # Insert 7 sessions in last 7 days with wellness=1 to trigger 'depleted'
        today = date.today()
        created = []
        for i in range(7):
            r = coach.post(f"{API}/sessions", json={
                "athlete_id": first_athlete["id"],
                "date": (today - timedelta(days=i)).isoformat(),
                "rpe": 5, "duration_min": 60, "sleep_quality": 3, "wellness": 1,
            }, timeout=20)
            assert r.status_code == 200
            created.append(r.json()["id"])
        try:
            ana = coach.get(f"{API}/analytics/athlete/{first_athlete['id']}", timeout=30)
            assert ana.status_code == 200
            m = ana.json()["metrics"]
            # wellness_7d is averaged with the seeded sessions in the same week
            # so we may land in 'depleted' (<=2) or 'fatigued' (3-4) zone.
            assert m["wellness_zone"] in ("depleted", "fatigued"), (
                f"got zone={m['wellness_zone']} w7d={m['wellness_7d']}"
            )
            joined = " ".join(m.get("risk_reasons", []))
            if m["wellness_zone"] == "depleted":
                assert m["risk"] == "danger"
                assert "Bem-estar corporal crítico" in joined, m.get("risk_reasons")
            else:  # fatigued -> escalates safe→warning or warning→danger
                assert m["risk"] in ("warning", "danger")
                assert "Bem-estar corporal baixo" in joined, m.get("risk_reasons")
        finally:
            for sid in created:
                coach.delete(f"{API}/sessions/{sid}", timeout=10)


# ---------- Weekly summary per athlete ----------
class TestWeeklySummary:
    def test_weekly_athlete_structure(self, coach, first_athlete):
        r = coach.get(f"{API}/analytics/weekly/{first_athlete['id']}?weeks=8", timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("athlete", "weeks", "evolution", "evolution_pct"):
            assert k in d
        assert len(d["weeks"]) == 8
        sample = d["weeks"][0]
        for f in ("week", "label", "start_date", "end_date", "sessions",
                  "total_load", "avg_load", "avg_sleep", "avg_wellness",
                  "delta_load", "delta_load_pct"):
            assert f in sample, f"missing {f} in weekly entry: {list(sample.keys())}"
        # 7-day span
        sd = date.fromisoformat(sample["start_date"])
        ed = date.fromisoformat(sample["end_date"])
        assert (ed - sd).days == 6
        # label format Sxx/yy
        assert sample["label"].startswith("S")
        assert "/" in sample["label"]


# ---------- Weekly team overview ----------
class TestWeeklyTeamOverview:
    def test_weekly_team_overview(self, coach):
        r = coach.get(f"{API}/analytics/weekly/team/overview?weeks=8", timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("team", "athletes_count", "weeks", "evolution", "evolution_pct"):
            assert k in d
        assert len(d["weeks"]) == 8
        s = d["weeks"][-1]
        assert "avg_wellness" in s
        assert isinstance(s["avg_wellness"], (int, float))


# ---------- Team summary avg_wellness ----------
class TestTeamSummaryAvgWellness:
    def test_team_summary_has_avg_wellness(self, coach):
        r = coach.get(f"{API}/analytics/team", timeout=30)
        assert r.status_code == 200
        summary = r.json()["summary"]
        assert "avg_wellness" in summary
        assert isinstance(summary["avg_wellness"], (int, float))
