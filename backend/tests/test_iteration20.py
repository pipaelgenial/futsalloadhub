"""Iteration 20 — Re-test the PDF 500 fix.

Focus:
  * GET /api/export/athlete/{id}/full-report.pdf → 200 + %PDF for ALL 8 demo athletes.
  * GET /api/export/team/full-report.pdf → 200 + %PDF with >= 1+N pages.
  * Tamper team.logo_data_b64 with garbage → both PDFs must STILL be 200 (fallback
    to placeholder Drawing). Restore afterwards.
  * Regressions from iter19: calendar total_load adjusted + total_load_base;
    POST /api/teams still rejects invalid multipliers with 400.
  * Weekly/monthly athlete PDFs still 200.
"""
import base64
import io
import os
from datetime import date, timedelta

import pytest
import requests


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


# ------------- fixtures -------------
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


@pytest.fixture(scope="module")
def athletes(sess):
    r = sess.get(f"{BASE_URL}/api/athletes", timeout=30)
    assert r.status_code == 200
    a = r.json()
    assert a, "no demo athletes"
    return a


def _count_pdf_pages(content: bytes) -> int:
    # Cheap page count: count '/Type /Page' occurrences (excluding /Pages).
    # Good enough for a smoke check.
    n = content.count(b"/Type /Page")
    n_pages = content.count(b"/Type /Pages")
    return max(n - n_pages, 0)


# ------------- PRIMARY: PDFs with real (possibly mock) logo -------------
class TestPDFPrimary:
    def test_all_athlete_full_pdfs_return_200(self, sess, athletes):
        assert len(athletes) >= 1, "expect at least one athlete"
        failures = []
        for a in athletes:
            r = sess.get(f"{BASE_URL}/api/export/athlete/{a['id']}/full-report.pdf", timeout=90)
            if r.status_code != 200 or r.content[:4] != b"%PDF":
                failures.append((a["id"], a.get("name"), r.status_code, r.text[:200]))
        assert not failures, f"athlete full-pdf failures: {failures}"

    def test_team_full_pdf_returns_200_and_enough_pages(self, sess, athletes):
        r = sess.get(f"{BASE_URL}/api/export/team/full-report.pdf", timeout=180)
        assert r.status_code == 200, r.text[:500]
        assert r.content[:4] == b"%PDF"
        pages = _count_pdf_pages(r.content)
        # cover page + one page per athlete (minimum)
        assert pages >= 1 + len(athletes), f"expected >= {1 + len(athletes)} pages, got {pages}"


# ------------- PRIMARY: corrupt-logo fallback -------------
class TestCorruptLogoFallback:
    """Tamper team.logo_data_b64 with pure garbage, regenerate PDFs, restore."""

    @pytest.fixture(scope="class")
    def _tamper(self, request):
        # Direct Mongo access to set/restore the logo blob.
        pytest.importorskip("pymongo")
        from pymongo import MongoClient

        # Load MONGO_URL/DB_NAME from backend/.env (not exported in test shell)
        env_map = {}
        with open("/app/backend/.env") as f:
            for ln in f:
                if "=" in ln and not ln.startswith("#"):
                    k, v = ln.strip().split("=", 1)
                    env_map[k] = v.strip().strip('"').strip("'")
        mongo_url = os.environ.get("MONGO_URL") or env_map.get("MONGO_URL")
        db_name = os.environ.get("DB_NAME") or env_map.get("DB_NAME")
        assert mongo_url and db_name, "MONGO_URL / DB_NAME missing"
        client = MongoClient(mongo_url)
        db = client[db_name]

        # locate the active team the coach owns
        coach_team = db.teams.find_one({"name": {"$regex": "Sporting Futsal", "$options": "i"}})
        if not coach_team:
            # fallback: any team with an athlete count
            coach_team = db.teams.find_one({"active": True}) or db.teams.find_one({})
        assert coach_team, "no team found in mongo"

        original = coach_team.get("logo_data_b64")
        # replace with random garbage that's valid base64 but NOT a valid image
        garbage_b64 = base64.b64encode(b"NOT-A-REAL-IMAGE-\x00\x01\x02random-bytes").decode()
        db.teams.update_one({"_id": coach_team["_id"]}, {"$set": {"logo_data_b64": garbage_b64}})

        def _restore():
            if original is None:
                db.teams.update_one({"_id": coach_team["_id"]}, {"$unset": {"logo_data_b64": ""}})
            else:
                db.teams.update_one({"_id": coach_team["_id"]}, {"$set": {"logo_data_b64": original}})
            client.close()

        request.addfinalizer(_restore)
        return coach_team["_id"]

    def test_athlete_pdf_with_corrupt_logo(self, sess, athletes, _tamper):
        aid = athletes[0]["id"]
        r = sess.get(f"{BASE_URL}/api/export/athlete/{aid}/full-report.pdf", timeout=90)
        assert r.status_code == 200, f"corrupt-logo athlete pdf failed: {r.status_code} {r.text[:400]}"
        assert r.content[:4] == b"%PDF"

    def test_team_pdf_with_corrupt_logo(self, sess, _tamper):
        r = sess.get(f"{BASE_URL}/api/export/team/full-report.pdf", timeout=180)
        assert r.status_code == 200, f"corrupt-logo team pdf failed: {r.status_code} {r.text[:400]}"
        assert r.content[:4] == b"%PDF"


# ------------- Regression: calendar adjusted -------------
class TestCalendarRegression:
    def test_calendar_exposes_total_load_and_base(self, sess):
        start = (date.today() - timedelta(days=45)).isoformat()
        r = sess.get(f"{BASE_URL}/api/calendar", params={"start": start, "days": 90}, timeout=60)
        assert r.status_code == 200
        days = r.json().get("days", [])
        assert days, "no calendar days"
        for d in days:
            assert "total_load" in d
            assert "total_load_base" in d
        # Find at least one day with match/recovery and confirm adjusted != base
        differ = [d for d in days if (d.get("session_types") or {}).get("match", 0) > 0
                                    or (d.get("session_types") or {}).get("recovery", 0) > 0]
        if differ:
            found = any(abs(d["total_load"] - d["total_load_base"]) > 0.4 for d in differ)
            assert found, "expected at least one match/recovery day where adjusted != base"


# ------------- Regression: POST /api/teams parity -------------
class TestPostTeamsParityRegression:
    @pytest.mark.parametrize("bad", [{"training": -1}, {"training": 5}, {"match": 0}])
    def test_post_invalid_multipliers_400(self, sess, bad):
        payload = {"name": "TEST_iter20_bad", "escalao": "Seniores",
                   "epoca": "2025/2026", "session_multipliers": bad}
        r = sess.post(f"{BASE_URL}/api/teams", json=payload, timeout=30)
        assert r.status_code == 400, f"expected 400 for {bad}, got {r.status_code}"


# ------------- Regression: weekly/monthly PDFs -------------
class TestWeeklyMonthlyRegression:
    def test_weekly_pdf_200(self, sess, athletes):
        aid = athletes[0]["id"]
        r = sess.get(f"{BASE_URL}/api/export/weekly/{aid}.pdf", timeout=60)
        assert r.status_code == 200
        assert r.content[:4] == b"%PDF"

    def test_monthly_pdf_200(self, sess, athletes):
        aid = athletes[0]["id"]
        r = sess.get(f"{BASE_URL}/api/export/monthly/{aid}.pdf", timeout=60)
        assert r.status_code == 200
        assert r.content[:4] == b"%PDF"
