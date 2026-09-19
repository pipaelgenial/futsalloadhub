"""Iteration 17: bug fix for 500 in weekly/monthly PDF exports.

Root cause: `dict.get(k, 0)` returns None when key is present but value is None
(happens for empty periods in weekly_summary/monthly_summary). f'{None:.0f}'
raises TypeError. Fix: `(v.get(k) or 0)`.

Also verifies:
- ASCII-only Content-Disposition filename.
- Regression on athlete/team full-report exports.
- Player role gets 403.
"""
import os
import re
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
COACH = {"email": "treinador@futsal.pt", "password": "treinador123"}
PLAYER = {"email": "jogador1@futsal.pt", "password": "jogador123"}


def _login(creds):
    s = requests.Session()
    r = s.post(f"{BASE}/api/auth/login", json=creds, timeout=20)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def coach():
    return _login(COACH)


@pytest.fixture(scope="module")
def player():
    return _login(PLAYER)


@pytest.fixture(scope="module")
def athletes(coach):
    r = coach.get(f"{BASE}/api/athletes", timeout=15)
    assert r.status_code == 200
    return r.json()


def _assert_pdf(r, label):
    assert r.status_code == 200, f"[{label}] status={r.status_code} body={r.text[:400]}"
    assert r.headers.get("content-type", "").startswith("application/pdf"), \
        f"[{label}] ct={r.headers.get('content-type')}"
    body = r.content
    assert body[:4] == b"%PDF", f"[{label}] missing %PDF magic (got {body[:8]!r})"
    assert len(body) > 1500, f"[{label}] pdf too small: {len(body)}"
    cd = r.headers.get("content-disposition", "")
    assert "attachment" in cd and ".pdf" in cd
    # ASCII-only header
    for ch in cd:
        assert ord(ch) < 128, f"[{label}] non-ASCII in CD: {cd!r}"


def test_weekly_pdf_all_demo_athletes(coach, athletes):
    assert len(athletes) >= 1
    for a in athletes:
        r = coach.get(f"{BASE}/api/export/weekly/{a['id']}.pdf", timeout=60)
        _assert_pdf(r, f"weekly {a['name']}")


def test_monthly_pdf_all_demo_athletes(coach, athletes):
    assert len(athletes) >= 1
    for a in athletes:
        r = coach.get(f"{BASE}/api/export/monthly/{a['id']}.pdf", timeout=60)
        _assert_pdf(r, f"monthly {a['name']}")


def test_weekly_pdf_athlete_with_zero_sessions(coach):
    """Reproduce the specific None-value crash: an athlete with 0 sessions."""
    payload = {"name": "TEST_ZeroSessions Athlete", "position": "Ala", "jersey_number": 88}
    r = coach.post(f"{BASE}/api/athletes", json=payload, timeout=15)
    assert r.status_code in (200, 201), f"create failed: {r.status_code} {r.text}"
    aid = r.json()["id"]
    try:
        rw = coach.get(f"{BASE}/api/export/weekly/{aid}.pdf", timeout=60)
        _assert_pdf(rw, "weekly zero-sessions")
        rm = coach.get(f"{BASE}/api/export/monthly/{aid}.pdf", timeout=60)
        _assert_pdf(rm, "monthly zero-sessions")
    finally:
        coach.delete(f"{BASE}/api/athletes/{aid}", timeout=15)


def test_weekly_pdf_ascii_filename_for_accented_athlete(coach, athletes):
    target = next((a for a in athletes if any(ord(c) > 127 for c in a["name"])), None)
    if not target:
        pytest.skip("no accented demo athlete")
    r = coach.get(f"{BASE}/api/export/weekly/{target['id']}.pdf", timeout=60)
    _assert_pdf(r, f"weekly {target['name']}")
    cd = r.headers.get("content-disposition", "")
    m = re.search(r'filename="([^"]+)"', cd)
    assert m, f"no filename in {cd}"
    fname = m.group(1)
    assert fname.startswith("semanal_")
    assert all(ord(c) < 128 for c in fname)


def test_monthly_pdf_ascii_filename_for_accented_athlete(coach, athletes):
    target = next((a for a in athletes if any(ord(c) > 127 for c in a["name"])), None)
    if not target:
        pytest.skip("no accented demo athlete")
    r = coach.get(f"{BASE}/api/export/monthly/{target['id']}.pdf", timeout=60)
    _assert_pdf(r, f"monthly {target['name']}")
    cd = r.headers.get("content-disposition", "")
    m = re.search(r'filename="([^"]+)"', cd)
    assert m, f"no filename in {cd}"
    fname = m.group(1)
    assert fname.startswith("mensal_")
    assert all(ord(c) < 128 for c in fname)


def test_weekly_pdf_player_gets_403(player, athletes):
    if not athletes:
        pytest.skip("no athletes")
    r = player.get(f"{BASE}/api/export/weekly/{athletes[0]['id']}.pdf", timeout=20)
    assert r.status_code == 403


def test_monthly_pdf_player_gets_403(player, athletes):
    if not athletes:
        pytest.skip("no athletes")
    r = player.get(f"{BASE}/api/export/monthly/{athletes[0]['id']}.pdf", timeout=20)
    assert r.status_code == 403


# --- Quick regressions -------------------------------------------------------

def test_regression_athlete_full_report(coach, athletes):
    r = coach.get(f"{BASE}/api/export/athlete/{athletes[0]['id']}/full-report.pdf", timeout=60)
    _assert_pdf(r, "athlete full-report")


def test_regression_team_full_report(coach):
    r = coach.get(f"{BASE}/api/export/team/full-report.pdf", timeout=120)
    _assert_pdf(r, "team full-report")


def test_regression_team_backup_zip(coach):
    r = coach.get(f"{BASE}/api/export/team-backup.zip", timeout=60)
    assert r.status_code == 200
    assert r.content[:2] == b"PK"
