"""Regression tests for athlete PDF export fix (NETWORK ERROR bug).

Covers:
- ASCII-only Content-Disposition filename for athletes with accented names.
- PDF magic bytes + size sanity.
- HTML-special chars in athlete name should not crash endpoint.
- All 8 demo athletes still export.
- Team backup + team-detailed regressions.
- Player role gets 403 on export.
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


def _validate_pdf_response(r, athlete_name):
    assert r.status_code == 200, f"status={r.status_code} body={r.text[:400]}"
    assert r.headers.get("content-type", "").startswith("application/pdf")
    cd = r.headers.get("content-disposition", "")
    assert "attachment" in cd and ".pdf" in cd
    # ASCII-only header check
    for ch in cd:
        assert ord(ch) < 128, f"non-ASCII in Content-Disposition: {cd!r}"
    body = r.content
    assert body[:4] == b"%PDF", f"missing PDF magic for {athlete_name}"
    assert len(body) > 2000, f"pdf too small ({len(body)}) for {athlete_name}"


def test_all_demo_athletes_export_pdf(coach, athletes):
    assert len(athletes) >= 1
    accented_seen = False
    for a in athletes:
        r = coach.get(f"{BASE}/api/export/athlete/{a['id']}/full-report.pdf", timeout=60)
        _validate_pdf_response(r, a["name"])
        if any(ord(c) > 127 for c in a["name"]):
            accented_seen = True
            # Filename should be ASCII slug
            m = re.search(r'filename="([^"]+)"', r.headers.get("content-disposition", ""))
            assert m, "no filename attr"
            fname = m.group(1)
            assert all(ord(c) < 128 for c in fname)
    assert accented_seen, "demo data should include accented names (André/João/etc)"


def test_andre_lopes_specifically(coach, athletes):
    target = next((a for a in athletes if "André" in a["name"] or "Andre" in a["name"]), None)
    if not target:
        pytest.skip("André Lopes not in demo data")
    r = coach.get(f"{BASE}/api/export/athlete/{target['id']}/full-report.pdf", timeout=60)
    _validate_pdf_response(r, target["name"])
    cd = r.headers.get("content-disposition", "")
    assert "Andre" in cd, f"expected ASCII 'Andre' slug in {cd}"


def test_html_special_chars_in_athlete_name(coach):
    # Get a valid position from an existing athlete to satisfy schema
    payload = {
        "name": 'Test & <Special> "Chars" TEST_',
        "position": "Ala",
        "jersey_number": 99,
    }
    r = coach.post(f"{BASE}/api/athletes", json=payload, timeout=15)
    assert r.status_code in (200, 201), f"create failed: {r.status_code} {r.text}"
    aid = r.json()["id"]
    try:
        rp = coach.get(f"{BASE}/api/export/athlete/{aid}/full-report.pdf", timeout=60)
        _validate_pdf_response(rp, payload["name"])
    finally:
        coach.delete(f"{BASE}/api/athletes/{aid}", timeout=15)


def test_player_role_gets_403(player, athletes):
    if not athletes:
        pytest.skip("no athletes")
    aid = athletes[0]["id"]
    r = player.get(f"{BASE}/api/export/athlete/{aid}/full-report.pdf", timeout=20)
    assert r.status_code == 403


def test_team_backup_zip_regression(coach):
    r = coach.get(f"{BASE}/api/export/team-backup.zip", timeout=60)
    assert r.status_code == 200
    assert r.content[:2] == b"PK"


def test_team_detailed_exclude_regression(coach, athletes):
    if len(athletes) < 2:
        pytest.skip("need 2+ athletes")
    ids = f"{athletes[0]['id']},{athletes[1]['id']}"
    r = coach.get(f"{BASE}/api/analytics/team-detailed?exclude_athlete_ids={ids}", timeout=20)
    assert r.status_code == 200
    assert isinstance(r.json(), dict)


def test_nonexistent_athlete_returns_404(coach):
    r = coach.get(f"{BASE}/api/export/athlete/does-not-exist/full-report.pdf", timeout=20)
    assert r.status_code == 404
