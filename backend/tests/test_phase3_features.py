"""Phase 3 backend API tests: refined risk zones, reset-all, photo upload/get/delete."""
import io
import os
import struct
import zlib
from datetime import date, timedelta

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"


def _make_png_bytes(size_bytes: int = 0) -> bytes:
    """Generate a valid minimal 1x1 PNG. If size_bytes > minimal, pad via tEXt chunk."""
    sig = b"\x89PNG\r\n\x1a\n"

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
    raw = b"\x00\xff\x00\x00"
    idat = chunk(b"IDAT", zlib.compress(raw))
    iend = chunk(b"IEND", b"")
    png = sig + ihdr + idat + iend
    if size_bytes > len(png):
        pad_len = size_bytes - len(png) - 12  # 12 bytes overhead per chunk
        if pad_len > 0:
            png = sig + ihdr + idat + chunk(b"tEXt", b"x" * pad_len) + iend
    return png


@pytest.fixture(scope="module")
def coach():
    s = requests.Session()
    r = s.post(f"{API}/auth/login",
               json={"email": "treinador@futsal.pt", "password": "treinador123"}, timeout=20)
    assert r.status_code == 200, r.text
    s.headers.update({"Authorization": f"Bearer {r.json()['token']}"})
    # Reseed demo data to start clean
    seed = s.post(f"{API}/seed/demo", timeout=60)
    assert seed.status_code == 200
    return s


@pytest.fixture(scope="module")
def athletes(coach):
    r = coach.get(f"{API}/athletes", timeout=15)
    assert r.status_code == 200
    a = r.json()
    assert len(a) >= 2
    return a


# ---------------- Refined Risk Zones ----------------
class TestRiskZones:
    def test_team_analytics_has_new_zone_fields(self, coach):
        r = coach.get(f"{API}/analytics/team", timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert len(d["athletes"]) >= 1
        for a in d["athletes"]:
            m = a["metrics"]
            for k in ("acwr_zone", "monotony_zone", "strain_zone",
                      "risk_label", "risk_description", "risk_reasons"):
                assert k in m, f"missing {k} for {a['name']}"
            assert m["acwr_zone"] in ("detraining", "sweet_spot", "alert", "high_risk", "no_data")
            assert m["monotony_zone"] in ("high_variation", "ideal", "moderate_high", "critical", "no_data")
            assert m["strain_zone"] in ("low", "moderate", "elevated", "extreme", "no_data")
            assert isinstance(m["risk_reasons"], list)

    def test_zone_thresholds_consistent_with_values(self, coach):
        r = coach.get(f"{API}/analytics/team", timeout=30)
        for a in r.json()["athletes"]:
            m = a["metrics"]
            acwr, mono, strain = m["acwr"], m["monotony"], m["strain"]
            if acwr == 0:
                assert m["acwr_zone"] == "no_data"
            elif acwr < 0.8:
                assert m["acwr_zone"] == "detraining"
            elif acwr <= 1.3:
                assert m["acwr_zone"] == "sweet_spot"
            elif acwr < 1.5:
                assert m["acwr_zone"] == "alert"
            else:
                assert m["acwr_zone"] == "high_risk"

            if mono == 0:
                assert m["monotony_zone"] == "no_data"
            elif mono < 1.0:
                assert m["monotony_zone"] == "high_variation"
            elif mono <= 1.5:
                assert m["monotony_zone"] == "ideal"
            elif mono <= 2.0:
                assert m["monotony_zone"] == "moderate_high"
            else:
                assert m["monotony_zone"] == "critical"

            if strain == 0:
                assert m["strain_zone"] == "no_data"
            elif strain < 1500:
                assert m["strain_zone"] == "low"
            elif strain <= 3000:
                assert m["strain_zone"] == "moderate"
            elif strain <= 6000:
                assert m["strain_zone"] == "elevated"
            else:
                assert m["strain_zone"] == "extreme"

    def test_critical_monotony_escalates_to_danger(self, coach, athletes):
        """Create monotonous sessions for one athlete: same RPE+duration daily for 7 days
        to push monotony>2 and strain extreme → risk must escalate to danger.
        """
        aid = athletes[-1]["id"]  # last athlete to not affect others tests too much
        today = date.today()
        # 7 identical sessions => std=0 still triggers monotony=0 fallback; need slight
        # variability so std>0 but mean/std > 2. Use small variation.
        loads = [(10, 90), (10, 95), (10, 90), (10, 90), (10, 95), (10, 90), (10, 90)]
        created_ids = []
        for i, (rpe, dur) in enumerate(loads):
            d = (today - timedelta(days=i)).isoformat()
            r = coach.post(f"{API}/sessions", json={
                "athlete_id": aid, "date": d, "rpe": rpe,
                "duration_min": dur, "sleep_quality": 4,
                "notes": "TEST_monotony_spike",
            }, timeout=15)
            assert r.status_code == 200, r.text
            created_ids.append(r.json()["id"])

        # fetch analytics
        r = coach.get(f"{API}/analytics/athlete/{aid}", timeout=20)
        m = r.json()["metrics"]
        # monotony should be high (>2) → critical zone
        assert m["monotony"] > 2.0, f"expected monotony>2, got {m['monotony']}"
        assert m["monotony_zone"] == "critical"
        # strain >6000 → extreme. Load per day = 900 → week=6300 * monotony ~ extreme
        assert m["strain_zone"] == "extreme", f"strain={m['strain']} zone={m['strain_zone']}"
        # risk should be danger (even if acwr sweet_spot)
        assert m["risk"] == "danger", f"risk={m['risk']} reasons={m['risk_reasons']}"
        assert any("Monotonia" in r or "Strain" in r for r in m["risk_reasons"])
        assert m["risk_description"]

        # cleanup
        for sid in created_ids:
            coach.delete(f"{API}/sessions/{sid}", timeout=10)


# ---------------- Photo Upload / Get / Delete ----------------
class TestPhotos:
    def test_upload_png_success(self, coach, athletes):
        aid = athletes[0]["id"]
        png = _make_png_bytes()
        files = {"file": ("test.png", io.BytesIO(png), "image/png")}
        r = coach.post(f"{API}/athletes/{aid}/photo", files=files, timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["ok"] is True
        assert "photo_path" in data and data["photo_path"].endswith(".png")
        assert data["url"] == f"/api/athletes/{aid}/photo"

        # athlete document has photo_path
        ra = coach.get(f"{API}/athletes", timeout=15).json()
        athlete = next(a for a in ra if a["id"] == aid)
        assert athlete.get("photo_path"), "photo_path missing on athlete doc"

    def test_get_photo_is_public_and_correct_content_type(self, coach, athletes):
        aid = athletes[0]["id"]
        # use unauthenticated session
        r = requests.get(f"{API}/athletes/{aid}/photo", timeout=20)
        assert r.status_code == 200, r.text
        assert r.headers["content-type"].startswith("image/")
        assert len(r.content) > 8 and r.content[:8] == b"\x89PNG\r\n\x1a\n"

    def test_upload_invalid_extension_rejected(self, coach, athletes):
        aid = athletes[0]["id"]
        files = {"file": ("evil.txt", io.BytesIO(b"hello"), "text/plain")}
        r = coach.post(f"{API}/athletes/{aid}/photo", files=files, timeout=15)
        assert r.status_code == 400

    def test_upload_oversize_rejected(self, coach, athletes):
        aid = athletes[1]["id"]
        big = b"x" * (5 * 1024 * 1024 + 100)  # >5MB
        files = {"file": ("big.png", io.BytesIO(big), "image/png")}
        r = coach.post(f"{API}/athletes/{aid}/photo", files=files, timeout=30)
        assert r.status_code == 400

    def test_upload_jpg_and_webp_accepted(self, coach, athletes):
        aid = athletes[1]["id"]
        # JPG (re-use png bytes content; extension is what matters per backend)
        png = _make_png_bytes()
        for fname, ctype in (("photo.jpg", "image/jpeg"), ("photo.webp", "image/webp")):
            r = coach.post(f"{API}/athletes/{aid}/photo",
                           files={"file": (fname, io.BytesIO(png), ctype)}, timeout=15)
            assert r.status_code == 200, f"{fname}: {r.text}"
            assert r.json()["photo_path"].endswith(fname.rsplit(".", 1)[-1])

    def test_delete_photo(self, coach, athletes):
        aid = athletes[0]["id"]
        r = coach.delete(f"{API}/athletes/{aid}/photo", timeout=15)
        assert r.status_code == 200
        assert r.json()["ok"] is True

        # athlete doc photo_path null
        ra = coach.get(f"{API}/athletes", timeout=15).json()
        athlete = next(a for a in ra if a["id"] == aid)
        assert not athlete.get("photo_path")

        # public GET now 404
        r2 = requests.get(f"{API}/athletes/{aid}/photo", timeout=15)
        assert r2.status_code == 404

    def test_upload_unknown_athlete_404(self, coach):
        files = {"file": ("test.png", io.BytesIO(_make_png_bytes()), "image/png")}
        r = coach.post(f"{API}/athletes/nope-id/photo", files=files, timeout=15)
        assert r.status_code == 404


# ---------------- Reset All ----------------
class TestResetAll:
    """Must run LAST since it wipes the user's data."""
    def test_reset_all_deletes_everything(self, coach):
        # ensure there is data first
        seed = coach.post(f"{API}/seed/demo", timeout=60)
        assert seed.status_code == 200

        # upload a photo so file deletion path is exercised
        athletes = coach.get(f"{API}/athletes", timeout=15).json()
        aid = athletes[0]["id"]
        coach.post(f"{API}/athletes/{aid}/photo",
                   files={"file": ("p.png", io.BytesIO(_make_png_bytes()), "image/png")},
                   timeout=20)

        r = coach.post(f"{API}/reset-all", timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["ok"] is True
        deleted = data["deleted"]
        for k in ("team", "athletes", "sessions", "injuries"):
            assert k in deleted
        assert deleted["team"] == 1
        assert deleted["athletes"] >= 8  # seed creates 8
        assert deleted["sessions"] > 0
        assert deleted["injuries"] >= 3

        # team is null, athletes empty
        rt = coach.get(f"{API}/team", timeout=15)
        assert rt.status_code == 200
        assert rt.json() is None
        ra = coach.get(f"{API}/athletes", timeout=15)
        assert ra.status_code == 200
        assert ra.json() == []

    def test_reset_all_idempotent_when_no_data(self, coach):
        r = coach.post(f"{API}/reset-all", timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["ok"] is True
        # when no team exists, counts stay zero
        assert d["deleted"]["team"] == 0
        assert d["deleted"]["athletes"] == 0
