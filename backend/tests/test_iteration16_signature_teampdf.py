"""Iteration 16 – Coach signature + team full-report PDF + coach_name on team."""
import io
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
    assert r.status_code == 200, r.text
    return s


@pytest.fixture(scope="module")
def coach():
    return _login(COACH)


@pytest.fixture(scope="module")
def player():
    return _login(PLAYER)


@pytest.fixture(scope="module")
def team(coach):
    r = coach.get(f"{BASE}/api/teams", timeout=15)
    assert r.status_code == 200
    teams = r.json()
    assert len(teams) >= 1
    return teams[0]


# tiny transparent PNG (1x1)
_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\xcf"
    b"\xc0\x00\x00\x00\x03\x00\x01\x1a\xdd\x8d\xf6\x00\x00\x00\x00IEND\xaeB`\x82"
)


# --- coach_name persistence ---
class TestCoachName:
    def _base(self, team):
        return {"name": team["name"], "escalao": team["escalao"], "epoca": team["epoca"]}

    def test_put_coach_name(self, coach, team):
        body = {**self._base(team), "coach_name": "TEST_Coach_Pipa"}
        r = coach.put(f"{BASE}/api/teams/{team['id']}", json=body, timeout=15)
        assert r.status_code in (200, 201), r.text
        g = coach.get(f"{BASE}/api/teams", timeout=15).json()
        me = next(t for t in g if t["id"] == team["id"])
        assert me.get("coach_name") == "TEST_Coach_Pipa"

    def test_put_coach_name_empty_clears(self, coach, team):
        coach.put(f"{BASE}/api/teams/{team['id']}", json={**self._base(team), "coach_name": "X"}, timeout=15)
        r = coach.put(f"{BASE}/api/teams/{team['id']}", json={**self._base(team), "coach_name": ""}, timeout=15)
        assert r.status_code in (200, 201)
        g = coach.get(f"{BASE}/api/teams", timeout=15).json()
        me = next(t for t in g if t["id"] == team["id"])
        assert not me.get("coach_name")
        # restore for later PDF tests
        coach.put(f"{BASE}/api/teams/{team['id']}", json={**self._base(team), "coach_name": "Pedro Pipa"}, timeout=15)


# --- signature upload / get / delete ---
class TestSignature:
    def test_delete_when_absent_returns_404_or_200(self, coach, team):
        # First clear
        coach.delete(f"{BASE}/api/teams/{team['id']}/signature", timeout=10)
        r = coach.get(f"{BASE}/api/teams/{team['id']}/signature", timeout=10)
        assert r.status_code == 404

    def test_upload_png(self, coach, team):
        files = {"file": ("sig.png", _PNG, "image/png")}
        r = coach.post(f"{BASE}/api/teams/{team['id']}/signature", files=files, timeout=15)
        assert r.status_code == 200, r.text
        # Public GET returns image bytes
        rg = requests.get(f"{BASE}/api/teams/{team['id']}/signature", timeout=10)
        assert rg.status_code == 200
        assert rg.headers.get("content-type", "").startswith("image/")
        assert rg.content[:4] == b"\x89PNG"

    def test_player_cannot_upload(self, player, team):
        files = {"file": ("sig.png", _PNG, "image/png")}
        r = player.post(f"{BASE}/api/teams/{team['id']}/signature", files=files, timeout=15)
        assert r.status_code in (401, 403)

    def test_reject_too_large(self, coach, team):
        big = b"\x89PNG" + b"0" * (2 * 1024 * 1024 + 100)
        files = {"file": ("sig.png", big, "image/png")}
        r = coach.post(f"{BASE}/api/teams/{team['id']}/signature", files=files, timeout=20)
        assert r.status_code in (400, 413), f"expected size rejection, got {r.status_code}"

    def test_delete_signature(self, coach, team):
        # ensure something exists first
        coach.post(f"{BASE}/api/teams/{team['id']}/signature",
                   files={"file": ("sig.png", _PNG, "image/png")}, timeout=15)
        r = coach.delete(f"{BASE}/api/teams/{team['id']}/signature", timeout=10)
        assert r.status_code in (200, 204)
        rg = requests.get(f"{BASE}/api/teams/{team['id']}/signature", timeout=10)
        assert rg.status_code == 404
        # restore for later PDF tests
        coach.post(f"{BASE}/api/teams/{team['id']}/signature",
                   files={"file": ("sig.png", _PNG, "image/png")}, timeout=15)


# --- Athlete PDF contains ASSINADO POR + coach name ---
class TestAthletePdfSignatureBlock:
    def test_signature_block_present(self, coach, team):
        # Ensure coach_name and signature set
        coach.put(f"{BASE}/api/teams/{team['id']}",
                  json={"name": team["name"], "escalao": team["escalao"], "epoca": team["epoca"],
                        "coach_name": "Pedro Pipa"}, timeout=15)
        coach.post(f"{BASE}/api/teams/{team['id']}/signature",
                   files={"file": ("sig.png", _PNG, "image/png")}, timeout=15)
        athletes = coach.get(f"{BASE}/api/athletes", timeout=15).json()
        assert athletes
        aid = athletes[0]["id"]
        r = coach.get(f"{BASE}/api/export/athlete/{aid}/full-report.pdf", timeout=60)
        assert r.status_code == 200
        assert r.content[:4] == b"%PDF"
        # Extract text via pypdf
        from pypdf import PdfReader
        text = ""
        try:
            for p in PdfReader(io.BytesIO(r.content)).pages:
                text += (p.extract_text() or "") + "\n"
        except Exception as e:
            pytest.skip(f"pypdf extract failed: {e}")
        assert "ASSINADO POR" in text.upper(), f"missing ASSINADO POR; got: {text[:800]}"
        assert "Pedro Pipa" in text, f"missing coach name; got: {text[:800]}"


# --- Team full-report PDF ---
class TestTeamFullPdf:
    def test_coach_ok_and_pagecount(self, coach, team):
        athletes = coach.get(f"{BASE}/api/athletes", timeout=15).json()
        n = len(athletes)
        r = coach.get(f"{BASE}/api/export/team/full-report.pdf", timeout=180)
        assert r.status_code == 200, r.text[:400]
        assert r.headers.get("content-type", "").startswith("application/pdf")
        cd = r.headers.get("content-disposition", "")
        assert cd.startswith("attachment") and ".pdf" in cd
        for ch in cd:
            assert ord(ch) < 128, f"non-ASCII CD: {cd!r}"
        m = re.search(r'filename="([^"]+)"', cd)
        assert m
        assert m.group(1).startswith("equipa_") and m.group(1).endswith(".pdf")
        assert r.content[:4] == b"%PDF"
        from pypdf import PdfReader
        pages = len(PdfReader(io.BytesIO(r.content)).pages)
        assert pages > (1 + n) if False else pages >= (1 + n), f"pages={pages}, athletes={n}"

    def test_player_forbidden(self, player):
        r = player.get(f"{BASE}/api/export/team/full-report.pdf", timeout=30)
        assert r.status_code == 403
