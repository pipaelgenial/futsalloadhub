"""Iteration 18: session_multipliers config + warning_kind field.

Covers:
- POST/PUT /api/teams with session_multipliers accept/reject
- Multipliers flow into /api/analytics/athlete session_multiplier + load_adjusted
- warning_kind field present on metrics
- Regressions: full report PDFs & weekly/monthly export
"""
import os
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


# ------------------ TeamIn session_multipliers ------------------
class TestMultipliersEndpoint:
    def test_put_valid_multipliers_persist(self, sess, team):
        payload = {
            "name": team["name"],
            "escalao": team.get("escalao"),
            "epoca": team.get("epoca"),
            "session_multipliers": {"training": 1.1, "match": 1.5, "gym": 0.9, "recovery": 0.5},
        }
        r = sess.put(f"{BASE_URL}/api/teams/{team['id']}", json=payload, timeout=30)
        assert r.status_code == 200, r.text
        # verify persistence via GET
        r2 = sess.get(f"{BASE_URL}/api/teams", timeout=30)
        t = next(x for x in r2.json() if x["id"] == team["id"])
        sm = t.get("session_multipliers") or {}
        assert sm.get("training") == 1.1
        assert sm.get("match") == 1.5
        assert sm.get("gym") == 0.9
        assert sm.get("recovery") == 0.5

    @pytest.mark.parametrize("bad", [
        {"training": 0},
        {"training": 5},
        {"match": "foo"},
        {"gym": -1},
    ])
    def test_put_invalid_multipliers_400(self, sess, team, bad):
        payload = {
            "name": team["name"],
            "escalao": team.get("escalao"),
            "epoca": team.get("epoca"),
            "session_multipliers": bad,
        }
        r = sess.put(f"{BASE_URL}/api/teams/{team['id']}", json=payload, timeout=30)
        assert r.status_code == 400, f"expected 400 for {bad}, got {r.status_code} {r.text}"

    def test_multipliers_flow_into_analytics(self, sess, team):
        # Set match multiplier to 1.5, gym to 0.9
        payload = {
            "name": team["name"],
            "escalao": team.get("escalao"),
            "epoca": team.get("epoca"),
            "session_multipliers": {"training": 1.0, "match": 1.5, "gym": 0.9, "recovery": 0.7},
        }
        r = sess.put(f"{BASE_URL}/api/teams/{team['id']}", json=payload, timeout=30)
        assert r.status_code == 200

        # Get an athlete
        ra = sess.get(f"{BASE_URL}/api/athletes", timeout=30)
        assert ra.status_code == 200
        athletes = ra.json()
        assert athletes, "no athletes in demo seed"
        aid = athletes[0]["id"]

        r = sess.get(f"{BASE_URL}/api/analytics/athlete/{aid}", timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "metrics" in data and "warning_kind" in data["metrics"]
        sessions = data.get("sessions", [])
        # For any match session, session_multiplier==1.5 and load_adjusted==load*1.5
        checked_match = checked_train = False
        for s in sessions:
            st = s.get("session_type")
            mult = s.get("session_multiplier")
            la = s.get("load_adjusted")
            assert mult is not None
            assert la is not None
            if st == "match":
                assert mult == 1.5, f"match mult {mult}"
                assert abs(la - round(s["load"] * 1.5, 1)) < 0.2
                checked_match = True
            elif st == "training":
                assert mult == 1.0
                checked_train = True
        assert checked_train or checked_match, "no training/match sessions to validate"

    def test_reset_defaults(self, sess, team):
        # Restore expected defaults 1.0/1.2/1.0/0.7
        payload = {
            "name": team["name"],
            "escalao": team.get("escalao"),
            "epoca": team.get("epoca"),
            "session_multipliers": {"training": 1.0, "match": 1.2, "gym": 1.0, "recovery": 0.7},
        }
        r = sess.put(f"{BASE_URL}/api/teams/{team['id']}", json=payload, timeout=30)
        assert r.status_code == 200


# ------------------ warning_kind field ------------------
class TestWarningKind:
    def test_warning_kind_key_present(self, sess):
        athletes = sess.get(f"{BASE_URL}/api/athletes", timeout=30).json()
        assert athletes
        found_kinds = set()
        for a in athletes[:8]:
            r = sess.get(f"{BASE_URL}/api/analytics/athlete/{a['id']}", timeout=30)
            assert r.status_code == 200
            m = r.json()["metrics"]
            assert "warning_kind" in m
            wk = m["warning_kind"]
            assert wk in (None, "detraining", "acwr_alert", "monotony", "strain", "wellness")
            found_kinds.add(wk)
        # At least one athlete should have a warning_kind set (per context: demo => detraining)
        assert found_kinds - {None}, f"no warning_kind observed across demo athletes: {found_kinds}"

    def test_warning_kind_null_when_not_warning(self, sess):
        # Analytics/team returns metrics per athlete; when risk != warning, warning_kind must be None
        r = sess.get(f"{BASE_URL}/api/analytics/team", timeout=30)
        assert r.status_code == 200
        for a in r.json().get("athletes", []):
            m = a.get("metrics", {})
            if m.get("risk") != "warning":
                assert m.get("warning_kind") is None, f"expected null wk for risk={m.get('risk')}"


# ------------------ regressions ------------------
class TestRegressionsExports:
    def test_athlete_full_pdf(self, sess):
        ra = sess.get(f"{BASE_URL}/api/athletes", timeout=30).json()
        aid = ra[0]["id"]
        r = sess.get(f"{BASE_URL}/api/export/athlete/{aid}/full-report.pdf", timeout=60)
        assert r.status_code == 200
        assert r.content[:4] == b"%PDF"

    def test_team_full_pdf(self, sess):
        r = sess.get(f"{BASE_URL}/api/export/team/full-report.pdf", timeout=90)
        assert r.status_code == 200
        assert r.content[:4] == b"%PDF"

    def test_weekly_export(self, sess):
        ra = sess.get(f"{BASE_URL}/api/athletes", timeout=30).json()
        aid = ra[0]["id"]
        r = sess.get(f"{BASE_URL}/api/export/weekly/{aid}.pdf", timeout=60)
        assert r.status_code == 200, r.text[:200]
        assert r.content[:4] == b"%PDF"

    def test_monthly_export(self, sess):
        ra = sess.get(f"{BASE_URL}/api/athletes", timeout=30).json()
        aid = ra[0]["id"]
        r = sess.get(f"{BASE_URL}/api/export/monthly/{aid}.pdf", timeout=60)
        assert r.status_code == 200, r.text[:200]
        assert r.content[:4] == b"%PDF"
