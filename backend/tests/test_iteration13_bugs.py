"""Iteration 13 — rest/injury edit fix, image DB persistence, exclude_injured checkbox."""
import base64
import os
import struct
import zlib
from datetime import date

import pytest
import requests
from dotenv import load_dotenv

load_dotenv("/app/frontend/.env")
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"

COACH = {"email": "treinador@futsal.pt", "password": "treinador123"}


def _png_bytes():
    # tiny 1x1 red PNG
    sig = b"\x89PNG\r\n\x1a\n"
    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    raw = b"\x00\xff\x00\x00"
    idat = zlib.compress(raw)
    return sig + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{API}/auth/login", json=COACH)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def headers(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def athlete_id(headers):
    r = requests.get(f"{API}/athletes", headers=headers)
    assert r.status_code == 200
    ath = r.json()
    assert len(ath) > 0, "no athletes seeded"
    return ath[0]["id"]


@pytest.fixture(scope="module")
def team_id(headers):
    r = requests.get(f"{API}/team", headers=headers)
    assert r.status_code == 200
    return r.json()["id"]


# -------- BUG 1: edit rest/injury sessions without changing anything --------
class TestEditRestInjury:
    def _cleanup(self, headers, sid):
        requests.delete(f"{API}/sessions/{sid}", headers=headers)

    def test_edit_rest_session_no_change(self, headers, athlete_id):
        d = "2024-11-01"
        # delete any prior
        r0 = requests.get(f"{API}/sessions", headers=headers, params={"athlete_id": athlete_id})
        for s in r0.json():
            if s["date"] == d:
                requests.delete(f"{API}/sessions/{s['id']}", headers=headers)
        r = requests.post(f"{API}/sessions/rest", headers=headers,
                          json={"athlete_id": athlete_id, "date": d})
        assert r.status_code == 200, r.text
        sid = r.json()["id"]
        # PUT with empty body first (all optional)
        r2 = requests.put(f"{API}/sessions/{sid}", headers=headers, json={})
        assert r2.status_code == 200, f"empty PUT failed: {r2.status_code} {r2.text}"
        assert r2.json()["session_type"] == "rest"
        assert r2.json()["rpe"] == 0
        assert r2.json()["duration_min"] == 0
        # PUT with rpe=0, duration=0 explicit
        r3 = requests.put(f"{API}/sessions/{sid}", headers=headers,
                          json={"rpe": 0, "duration_min": 0})
        assert r3.status_code == 200, r3.text
        self._cleanup(headers, sid)

    def test_edit_injury_session_no_change(self, headers, athlete_id):
        d = "2024-11-02"
        r0 = requests.get(f"{API}/sessions", headers=headers, params={"athlete_id": athlete_id})
        for s in r0.json():
            if s["date"] == d:
                requests.delete(f"{API}/sessions/{s['id']}", headers=headers)
        r = requests.post(f"{API}/sessions/injury", headers=headers,
                          json={"athlete_id": athlete_id, "date": d})
        assert r.status_code == 200, r.text
        sid = r.json()["id"]
        r2 = requests.put(f"{API}/sessions/{sid}", headers=headers, json={})
        assert r2.status_code == 200
        assert r2.json()["session_type"] == "injury"
        r3 = requests.put(f"{API}/sessions/{sid}", headers=headers,
                          json={"rpe": 0, "duration_min": 0})
        assert r3.status_code == 200
        self._cleanup(headers, sid)

    def test_edit_training_session_rpe_zero_blocked(self, headers, athlete_id):
        d = "2024-11-03"
        r0 = requests.get(f"{API}/sessions", headers=headers, params={"athlete_id": athlete_id})
        for s in r0.json():
            if s["date"] == d:
                requests.delete(f"{API}/sessions/{s['id']}", headers=headers)
        r = requests.post(f"{API}/sessions", headers=headers, json={
            "athlete_id": athlete_id, "date": d, "rpe": 5, "duration_min": 60,
            "session_type": "training", "sleep_quality": 3
        })
        assert r.status_code == 200, r.text
        sid = r.json()["id"]
        r2 = requests.put(f"{API}/sessions/{sid}", headers=headers, json={"rpe": 0})
        assert r2.status_code == 400, f"expected 400, got {r2.status_code} {r2.text}"
        assert "≥ 1" in r2.text or "requerem RPE" in r2.text
        self._cleanup(headers, sid)


# -------- BUG 2: image persistence in Mongo (base64) --------
class TestPhotoPersistence:
    def test_athlete_photo_db_persists_after_disk_delete(self, headers, athlete_id):
        png = _png_bytes()
        files = {"file": ("test.png", png, "image/png")}
        r = requests.post(f"{API}/athletes/{athlete_id}/photo", headers=headers, files=files)
        assert r.status_code == 200, r.text
        # GET returns image
        g1 = requests.get(f"{API}/athletes/{athlete_id}/photo")
        assert g1.status_code == 200
        assert g1.headers.get("content-type", "").startswith("image/")
        # confirm photo_updated_at on athlete
        alist = requests.get(f"{API}/athletes", headers=headers).json()
        me = [a for a in alist if a["id"] == athlete_id][0]
        assert me.get("photo_updated_at"), "photo_updated_at not set"
        # simulate ephemeral disk: delete the file locally
        upload_dir = "/app/backend/uploads/athletes"
        deleted = False
        if os.path.isdir(upload_dir):
            for fn in os.listdir(upload_dir):
                if fn.startswith(athlete_id):
                    os.remove(os.path.join(upload_dir, fn))
                    deleted = True
        # GET again — must still work via DB base64
        g2 = requests.get(f"{API}/athletes/{athlete_id}/photo")
        assert g2.status_code == 200, f"disk deleted but DB fallback missing: {g2.status_code}"
        assert g2.headers.get("content-type", "").startswith("image/")
        assert len(g2.content) == len(png), "content differs"
        # cleanup
        requests.delete(f"{API}/athletes/{athlete_id}/photo", headers=headers)
        g3 = requests.get(f"{API}/athletes/{athlete_id}/photo")
        assert g3.status_code == 404

    def test_team_logo_db_persists_after_disk_delete(self, headers, team_id):
        png = _png_bytes()
        files = {"file": ("logo.png", png, "image/png")}
        r = requests.post(f"{API}/teams/{team_id}/logo", headers=headers, files=files)
        assert r.status_code == 200, r.text
        g1 = requests.get(f"{API}/teams/{team_id}/logo")
        assert g1.status_code == 200
        upload_dir = "/app/backend/uploads/teams"
        if os.path.isdir(upload_dir):
            for fn in os.listdir(upload_dir):
                if fn.startswith(team_id):
                    os.remove(os.path.join(upload_dir, fn))
        g2 = requests.get(f"{API}/teams/{team_id}/logo")
        assert g2.status_code == 200
        assert len(g2.content) == len(png)
        requests.delete(f"{API}/teams/{team_id}/logo", headers=headers)
        g3 = requests.get(f"{API}/teams/{team_id}/logo")
        assert g3.status_code == 404


# -------- FEATURE 3: exclude_injured query param on team-detailed --------
class TestExcludeInjured:
    @pytest.mark.asyncio
    async def _toggle_injured(self, athlete_id, value):
        from motor.motor_asyncio import AsyncIOMotorClient
        cli = AsyncIOMotorClient("mongodb://localhost:27017")
        db = cli["futsal_load_db"]
        await db.athletes.update_one({"id": athlete_id}, {"$set": {"is_injured": value}})
        cli.close()

    def test_default_and_exclude_true(self, headers, athlete_id):
        # baseline
        r0 = requests.get(f"{API}/analytics/team-detailed", headers=headers)
        assert r0.status_code == 200, r0.text
        j0 = r0.json()
        assert j0.get("exclude_injured") is False
        assert "injured_count" in j0
        n_total = j0["n_athletes"]

        # mark one athlete as injured via direct mongo call using motor synchronously
        import asyncio
        from motor.motor_asyncio import AsyncIOMotorClient

        async def _set(v):
            cli = AsyncIOMotorClient("mongodb://localhost:27017")
            await cli["futsal_load_db"].athletes.update_one({"id": athlete_id}, {"$set": {"is_injured": v}})
            cli.close()

        asyncio.get_event_loop().run_until_complete(_set(True))
        try:
            r1 = requests.get(f"{API}/analytics/team-detailed", headers=headers)
            j1 = r1.json()
            assert j1["exclude_injured"] is False
            assert j1["injured_count"] >= 1
            assert j1["n_athletes"] == n_total, "default include-all must keep same count"

            r2 = requests.get(f"{API}/analytics/team-detailed?exclude_injured=true", headers=headers)
            j2 = r2.json()
            assert j2["exclude_injured"] is True
            assert j2["injured_count"] >= 1
            assert j2["n_athletes"] == n_total - 1, f"expected {n_total-1} got {j2['n_athletes']}"
        finally:
            asyncio.get_event_loop().run_until_complete(_set(False))
