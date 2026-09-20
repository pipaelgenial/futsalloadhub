"""Iteration 19:
- Calendar total_load now uses adjusted (base × session_multiplier) plus new total_load_base field.
- POST /api/teams parity with PUT for invalid session_multipliers (must 400).
- Regressions: analytics warning_kind + full-report PDFs still 200.
"""
import os
from datetime import date, timedelta
import requests
import pytest


def _load_frontend_env():
    p = "/app/frontend/.env"
    if os.path.exists(p):
        with open(p) as f:
            for ln in f:
                if ln.startswith("REACT_APP_BACKEND_URL="):
                    return ln.split("=", 1)[1].strip()
    return os.environ.get("REACT_APP_BACKEND_URL", "")


BASE_URL = _load_frontend_env().rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL missing"
COACH = {"email": "treinador@futsal.pt", "password": "treinador123"}


@pytest.fixture(scope="module")
def sess():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json=COACH, timeout=30)
    assert r.status_code == 200, r.text
    tok = r.json().get("access_token") or r.json().get("token")
    if tok:
        s.headers["Authorization"] = f"Bearer {tok}"
    return s


@pytest.fixture(scope="module")
def team(sess):
    r = sess.get(f"{BASE_URL}/api/teams", timeout=30)
    assert r.status_code == 200
    teams = r.json()
    active = next((t for t in teams if t.get("active")), teams[0])
    return active


def _find_range_with_sessions(sess, days=90):
    """Fetch calendar across a wide window; return earliest date containing sessions."""
    today = date.today()
    start = (today - timedelta(days=days)).isoformat()
    r = sess.get(f"{BASE_URL}/api/calendar", params={"start": start, "days": days + 30}, timeout=60)
    assert r.status_code == 200, r.text
    body = r.json()
    days_list = body.get("days", [])
    return body, days_list


# ---------------- Calendar total_load adjusted ----------------
class TestCalendarAdjustedLoad:
    def test_calendar_returns_total_load_base_and_adjusted(self, sess, team):
        # Ensure known defaults for the test
        payload = {
            "name": team["name"],
            "escalao": team.get("escalao"),
            "epoca": team.get("epoca"),
            "session_multipliers": {"training": 1.0, "match": 1.2, "gym": 1.0, "recovery": 0.7},
        }
        r = sess.put(f"{BASE_URL}/api/teams/{team['id']}", json=payload, timeout=30)
        assert r.status_code == 200

        _, days_list = _find_range_with_sessions(sess)
        assert days_list, "calendar returned no days"

        # every day dict must expose both fields
        for d in days_list:
            assert "total_load" in d
            assert "total_load_base" in d
            # Sanity: recompute adjusted from athletes list must equal total_load
            recomputed = round(sum(a.get("load_adjusted", 0) for a in d.get("athletes", [])), 1)
            assert abs(recomputed - d["total_load"]) < 0.5, (
                f"day {d['date']}: recomputed adjusted {recomputed} != total_load {d['total_load']}"
            )
            recomputed_base = round(sum(a.get("load", 0) for a in d.get("athletes", [])), 1)
            assert abs(recomputed_base - d["total_load_base"]) < 0.5

    def test_days_with_match_or_recovery_differ_from_base(self, sess, team):
        # Reset to defaults with match=1.2, recovery=0.7 (different from 1.0)
        payload = {
            "name": team["name"],
            "escalao": team.get("escalao"),
            "epoca": team.get("epoca"),
            "session_multipliers": {"training": 1.0, "match": 1.2, "gym": 1.0, "recovery": 0.7},
        }
        sess.put(f"{BASE_URL}/api/teams/{team['id']}", json=payload, timeout=30)

        _, days_list = _find_range_with_sessions(sess)
        checked = False
        for d in days_list:
            types = d.get("session_types", {}) or {}
            has_match = types.get("match", 0) > 0
            has_recovery = types.get("recovery", 0) > 0
            if has_match or has_recovery:
                # adjusted should differ from base
                assert d["total_load"] != d["total_load_base"], (
                    f"day {d['date']} has match/recovery but total_load == base: {d}"
                )
                checked = True
        if not checked:
            pytest.skip("No match/recovery days in fixture window to validate")

    def test_training_only_day_adjusted_equals_base(self, sess, team):
        # Defaults training=1.0 gym=1.0 -> adjusted == base on those days
        _, days_list = _find_range_with_sessions(sess)
        checked = False
        for d in days_list:
            types = d.get("session_types", {}) or {}
            if not types:
                continue
            # only training and/or gym present
            keys = set(types.keys())
            if keys and keys.issubset({"training", "gym"}):
                assert abs(d["total_load"] - d["total_load_base"]) < 0.5, (
                    f"training/gym only day {d['date']}: {d['total_load']} vs base {d['total_load_base']}"
                )
                checked = True
        if not checked:
            pytest.skip("No training/gym-only days in fixture window")

    def test_match_multiplier_change_flows_into_calendar(self, sess, team):
        # Snapshot with match=1.2
        payload_base = {
            "name": team["name"],
            "escalao": team.get("escalao"),
            "epoca": team.get("epoca"),
            "session_multipliers": {"training": 1.0, "match": 1.2, "gym": 1.0, "recovery": 0.7},
        }
        sess.put(f"{BASE_URL}/api/teams/{team['id']}", json=payload_base, timeout=30)
        _, days_a = _find_range_with_sessions(sess)
        by_date_a = {d["date"]: d for d in days_a}

        # Bump match multiplier to 1.5
        payload_bump = dict(payload_base)
        payload_bump["session_multipliers"] = {"training": 1.0, "match": 1.5, "gym": 1.0, "recovery": 0.7}
        r = sess.put(f"{BASE_URL}/api/teams/{team['id']}", json=payload_bump, timeout=30)
        assert r.status_code == 200

        _, days_b = _find_range_with_sessions(sess)
        by_date_b = {d["date"]: d for d in days_b}

        try:
            found_match_day = False
            for d_date, d_a in by_date_a.items():
                if (d_a.get("session_types") or {}).get("match", 0) <= 0:
                    continue
                d_b = by_date_b.get(d_date)
                if not d_b:
                    continue
                # base must remain the same, adjusted must be higher
                assert abs(d_a["total_load_base"] - d_b["total_load_base"]) < 0.5
                assert d_b["total_load"] > d_a["total_load"], (
                    f"day {d_date} adjusted did not increase after mult 1.2->1.5: {d_a['total_load']} vs {d_b['total_load']}"
                )
                # Numerically: extra = base_match_load * (1.5-1.2)
                match_load_base = sum(
                    a.get("load", 0) for a in d_b.get("athletes", []) if a.get("session_type") == "match"
                )
                expected_delta = match_load_base * 0.3
                actual_delta = d_b["total_load"] - d_a["total_load"]
                assert abs(actual_delta - expected_delta) < 1.0, (
                    f"day {d_date}: delta {actual_delta} vs expected {expected_delta}"
                )
                found_match_day = True
                break
            if not found_match_day:
                pytest.skip("No match day found in calendar window to validate multiplier flow")
        finally:
            # Restore defaults
            sess.put(f"{BASE_URL}/api/teams/{team['id']}", json=payload_base, timeout=30)


# ---------------- POST /api/teams parity ----------------
class TestPostTeamsParity:
    @pytest.mark.parametrize("bad", [
        {"training": -1},
        {"training": 5},
        {"training": "abc"},
        {"match": 0},
    ])
    def test_post_invalid_multipliers_returns_400(self, sess, bad):
        payload = {
            "name": "TEST_bad_mult",
            "escalao": "Seniores",
            "epoca": "2025/2026",
            "session_multipliers": bad,
        }
        r = sess.post(f"{BASE_URL}/api/teams", json=payload, timeout=30)
        assert r.status_code == 400, f"expected 400 for {bad}, got {r.status_code} {r.text[:200]}"
        detail = ""
        try:
            detail = r.json().get("detail", "")
        except Exception:
            pass
        assert "Multiplicad" in detail or "invalid" in detail.lower() or detail, (
            f"missing detail msg: {r.text[:200]}"
        )
        # Ensure the bad team was NOT created
        listing = sess.get(f"{BASE_URL}/api/teams", timeout=30).json()
        assert not any(t["name"] == "TEST_bad_mult" for t in listing), "invalid team should not be created"

    def test_post_valid_multipliers_creates_team(self, sess):
        payload = {
            "name": "TEST_iter19_valid",
            "escalao": "Seniores",
            "epoca": "2025/2026",
            "session_multipliers": {"training": 1.1, "match": 1.3, "gym": 0.9, "recovery": 0.6},
        }
        r = sess.post(f"{BASE_URL}/api/teams", json=payload, timeout=30)
        # Might fail if user hit max_teams. Handle gracefully.
        if r.status_code == 400 and "Limite" in r.text:
            pytest.skip(f"user has hit team limit: {r.text}")
        assert r.status_code == 200, r.text
        created = r.json()
        assert created["session_multipliers"]["training"] == 1.1
        assert created["session_multipliers"]["match"] == 1.3
        # cleanup
        sess.delete(f"{BASE_URL}/api/teams/{created['id']}", timeout=30)

    def test_post_without_multipliers_works(self, sess):
        payload = {
            "name": "TEST_iter19_no_mult",
            "escalao": "Seniores",
            "epoca": "2025/2026",
        }
        r = sess.post(f"{BASE_URL}/api/teams", json=payload, timeout=30)
        if r.status_code == 400 and "Limite" in r.text:
            pytest.skip(f"user has hit team limit: {r.text}")
        assert r.status_code == 200, r.text
        created = r.json()
        assert created.get("session_multipliers") in (None, {},)
        # cleanup
        sess.delete(f"{BASE_URL}/api/teams/{created['id']}", timeout=30)


# ---------------- Regressions ----------------
class TestRegressions:
    def test_analytics_warning_kind_present(self, sess):
        athletes = sess.get(f"{BASE_URL}/api/athletes", timeout=30).json()
        assert athletes
        aid = athletes[0]["id"]
        r = sess.get(f"{BASE_URL}/api/analytics/athlete/{aid}", timeout=30)
        assert r.status_code == 200
        m = r.json().get("metrics", {})
        assert "warning_kind" in m
        # _enrich_session applied — check session_multiplier / load_adjusted
        for s in r.json().get("sessions", [])[:5]:
            assert "session_multiplier" in s
            assert "load_adjusted" in s

    def test_athlete_full_pdf(self, sess):
        athletes = sess.get(f"{BASE_URL}/api/athletes", timeout=30).json()
        aid = athletes[0]["id"]
        r = sess.get(f"{BASE_URL}/api/export/athlete/{aid}/full-report.pdf", timeout=60)
        assert r.status_code == 200
        assert r.content[:4] == b"%PDF"

    def test_team_full_pdf(self, sess):
        r = sess.get(f"{BASE_URL}/api/export/team/full-report.pdf", timeout=90)
        assert r.status_code == 200
        assert r.content[:4] == b"%PDF"
