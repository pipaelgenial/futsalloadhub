"""Iteration 14 backend tests:
- GET /api/analytics/team-detailed with exclude_athlete_ids
- GET /api/export/team-backup.zip (auth as coach)
- POST /api/import/team-backup?mode=merge (dedupe) and mode=replace
"""
import io
import os
import zipfile
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
COACH = {"email": "treinador@futsal.pt", "password": "treinador123"}


@pytest.fixture(scope="module")
def coach_client():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json=COACH)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return s


def test_team_detailed_baseline(coach_client):
    r = coach_client.get(f"{BASE_URL}/api/analytics/team-detailed")
    assert r.status_code == 200
    d = r.json()
    assert d.get("team") is not None
    assert isinstance(d.get("series"), list)


def test_team_detailed_exclude_athlete_ids(coach_client):
    # get list of athletes
    r = coach_client.get(f"{BASE_URL}/api/athletes")
    assert r.status_code == 200
    athletes = r.json()
    assert len(athletes) >= 2
    excl = [athletes[0]["id"], athletes[1]["id"]]
    r2 = coach_client.get(
        f"{BASE_URL}/api/analytics/team-detailed",
        params={"exclude_athlete_ids": ",".join(excl)},
    )
    assert r2.status_code == 200
    d = r2.json()
    assert d.get("excluded_manual") == 2
    # Series must differ from baseline (excluded athletes reduce daily load avg)
    base = coach_client.get(f"{BASE_URL}/api/analytics/team-detailed").json()
    base_sum = sum(pt.get("load", 0) for pt in base["series"])
    new_sum = sum(pt.get("load", 0) for pt in d["series"])
    assert base_sum != new_sum, "Excluding athletes should change series load"


def test_export_team_backup_zip(coach_client):
    r = coach_client.get(f"{BASE_URL}/api/export/team-backup.zip")
    assert r.status_code == 200
    assert r.headers.get("content-type", "").startswith("application/zip")
    cd = r.headers.get("content-disposition", "")
    assert "backup_" in cd
    # Team name is "Sporting Futsal Lisboa" -> sanitized token
    assert "Sporting" in cd
    zf = zipfile.ZipFile(io.BytesIO(r.content))
    names = zf.namelist()
    assert "atletas.csv" in names
    assert "sessoes.csv" in names
    a_csv = zf.read("atletas.csv").decode("utf-8-sig")
    s_csv = zf.read("sessoes.csv").decode("utf-8-sig")
    assert ";" in a_csv.splitlines()[0]  # semicolon delimited
    assert len(a_csv.splitlines()) >= 2  # header + at least 1 athlete
    # Stash for reuse via pytest cache
    pytest.zip_bytes = r.content
    pytest.expected_athletes = len(a_csv.splitlines()) - 1
    pytest.expected_sessions = len(s_csv.splitlines()) - 1


def test_import_merge_all_duplicates(coach_client):
    zip_bytes = getattr(pytest, "zip_bytes", None)
    assert zip_bytes, "run export test first"
    files = {"file": ("backup.zip", zip_bytes, "application/zip")}
    r = coach_client.post(f"{BASE_URL}/api/import/team-backup", params={"mode": "merge"}, files=files)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d.get("ok") is True
    assert d.get("athletes_matched") == pytest.expected_athletes
    assert d.get("athletes_created") == 0
    assert d.get("sessions_created") == 0  # all duplicates in merge
    assert d.get("sessions_skipped") == pytest.expected_sessions


def test_import_replace_wipes_and_reinserts(coach_client):
    zip_bytes = getattr(pytest, "zip_bytes", None)
    assert zip_bytes, "run export test first"
    files = {"file": ("backup.zip", zip_bytes, "application/zip")}
    r = coach_client.post(f"{BASE_URL}/api/import/team-backup", params={"mode": "replace"}, files=files)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d.get("ok") is True
    # After replace: all athletes newly created, all sessions inserted
    assert d.get("athletes_created") == pytest.expected_athletes
    assert d.get("sessions_created") == pytest.expected_sessions
    # sanity: same count of athletes in DB
    r2 = coach_client.get(f"{BASE_URL}/api/athletes")
    assert len(r2.json()) == pytest.expected_athletes


def test_import_invalid_mode(coach_client):
    zip_bytes = getattr(pytest, "zip_bytes", None) or b"PK"
    files = {"file": ("backup.zip", zip_bytes, "application/zip")}
    r = coach_client.post(f"{BASE_URL}/api/import/team-backup", params={"mode": "bogus"}, files=files)
    assert r.status_code == 400
