"""
Iteration 12 — Role-based access (admin/coach/player), admin panel,
athlete invite flow, and player-only views.
Covers items 1-12 of the review request.
"""
import os
import uuid

import pytest
import requests
from dotenv import load_dotenv

load_dotenv("/app/frontend/.env")
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "pedrompsantos84@gmail.com"
ADMIN_PASSWORD = "amarense"
COACH_EMAIL = "treinador@futsal.pt"
COACH_PASSWORD = "treinador123"


# ------------------ helpers ------------------
def _bearer(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _login(email, password, expect=200):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password})
    assert r.status_code == expect, f"login {email}: {r.status_code} {r.text}"
    return r


@pytest.fixture(scope="session")
def admin_token():
    r = _login(ADMIN_EMAIL, ADMIN_PASSWORD)
    data = r.json()
    assert data["role"] == "admin"
    assert data["status"] == "active"
    assert data.get("token")
    return data["token"]


@pytest.fixture(scope="session")
def coach_token():
    r = _login(COACH_EMAIL, COACH_PASSWORD)
    return r.json()["token"]


# Unique suffix for emails so re-runs don't collide
RUN_ID = uuid.uuid4().hex[:8]


# ============================================================
# 1) Bootstrap admin
# ============================================================
class TestAdminBootstrap:
    def test_admin_login_returns_admin_role(self):
        r = _login(ADMIN_EMAIL, ADMIN_PASSWORD)
        d = r.json()
        assert d["role"] == "admin"
        assert d["status"] == "active"
        assert isinstance(d.get("token"), str)

    def test_admin_can_list_users(self, admin_token):
        r = requests.get(f"{API}/admin/users", headers=_bearer(admin_token))
        assert r.status_code == 200
        users = r.json()
        assert isinstance(users, list) and len(users) >= 1
        emails = [u["email"] for u in users]
        assert ADMIN_EMAIL in emails
        # bootstrap admin must include stats
        admin = next(u for u in users if u["email"] == ADMIN_EMAIL)
        assert "stats" in admin


# ============================================================
# 2) Coach register pending + immediate login blocked
# ============================================================
@pytest.fixture(scope="session")
def pending_coach():
    email = f"test_coach_{RUN_ID}@futsal.pt"
    pwd = "coachpass123"
    r = requests.post(f"{API}/auth/register", json={
        "email": email, "password": pwd, "name": "TEST Coach Pending"
    })
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["status"] == "pending"
    assert "token" not in data
    assert "aguarda validação" in data.get("message", "").lower()
    return {"email": email, "password": pwd, "id": data["id"]}


class TestRegisterPending:
    def test_pending_coach_cannot_login(self, pending_coach):
        r = requests.post(f"{API}/auth/login", json={
            "email": pending_coach["email"], "password": pending_coach["password"]
        })
        assert r.status_code == 403
        assert "aguarda valida" in r.json().get("detail", "").lower()


# ============================================================
# 3) Admin validate -> 4) suspend/reactivate
# ============================================================
class TestAdminLifecycle:
    def test_validate_then_login_works(self, admin_token, pending_coach):
        r = requests.post(
            f"{API}/admin/users/{pending_coach['id']}/validate",
            headers=_bearer(admin_token),
        )
        assert r.status_code == 200
        assert r.json()["status"] == "active"
        # Now coach login works
        r2 = _login(pending_coach["email"], pending_coach["password"])
        pending_coach["token"] = r2.json()["token"]

    def test_suspend_blocks_login(self, admin_token, pending_coach):
        r = requests.post(
            f"{API}/admin/users/{pending_coach['id']}/suspend",
            headers=_bearer(admin_token),
        )
        assert r.status_code == 200
        assert r.json()["status"] == "suspended"
        r2 = requests.post(f"{API}/auth/login", json={
            "email": pending_coach["email"], "password": pending_coach["password"]
        })
        assert r2.status_code == 403
        assert "suspensa" in r2.json().get("detail", "").lower()

    def test_reactivate_unblocks_login(self, admin_token, pending_coach):
        r = requests.post(
            f"{API}/admin/users/{pending_coach['id']}/reactivate",
            headers=_bearer(admin_token),
        )
        assert r.status_code == 200
        assert r.json()["status"] == "active"
        r2 = _login(pending_coach["email"], pending_coach["password"])
        pending_coach["token"] = r2.json()["token"]


# ============================================================
# 6) Admin self-protection
# ============================================================
class TestAdminSelfProtection:
    def test_cannot_delete_admin(self, admin_token):
        # find admin id
        r = requests.get(f"{API}/admin/users", headers=_bearer(admin_token))
        admin = next(u for u in r.json() if u["email"] == ADMIN_EMAIL)
        r2 = requests.delete(
            f"{API}/admin/users/{admin['id']}", headers=_bearer(admin_token)
        )
        assert r2.status_code == 400
        assert "admin" in r2.json().get("detail", "").lower()

    def test_cannot_suspend_admin(self, admin_token):
        r = requests.get(f"{API}/admin/users", headers=_bearer(admin_token))
        admin = next(u for u in r.json() if u["email"] == ADMIN_EMAIL)
        r2 = requests.post(
            f"{API}/admin/users/{admin['id']}/suspend", headers=_bearer(admin_token)
        )
        assert r2.status_code == 400


# ============================================================
# 7) + 8) Invite flow + 9) + 10) + 11) Player restrictions/sessions
# ============================================================
@pytest.fixture(scope="session")
def coach_setup(pending_coach):
    """Validated coach with a team + an athlete (for invite tests)."""
    headers = _bearer(pending_coach["token"])
    # ensure team exists
    r = requests.get(f"{API}/teams", headers=headers)
    teams = r.json()
    if not teams:
        rt = requests.post(f"{API}/teams", json={
            "name": "TEST Team", "escalao": "Sénior", "epoca": "2025/2026"
        }, headers=headers)
        assert rt.status_code == 200, rt.text
        team = rt.json()
    else:
        team = teams[0]
    # ensure active team set
    requests.post(f"{API}/teams/{team['id']}/activate", headers=headers)
    # create athlete
    ra = requests.post(f"{API}/athletes", json={
        "name": "TEST Athlete Invite", "position": "Pivô", "jersey_number": 99
    }, headers=headers)
    assert ra.status_code == 200, ra.text
    athlete = ra.json()
    return {"team": team, "athlete": athlete, "headers": headers, "coach": pending_coach}


class TestInviteFlow:
    def test_coach_create_invite(self, coach_setup):
        ath_id = coach_setup["athlete"]["id"]
        r = requests.post(
            f"{API}/athletes/{ath_id}/invite", headers=coach_setup["headers"]
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["linked"] is False
        assert d["athlete_id"] == ath_id
        assert d["athlete_name"] == "TEST Athlete Invite"
        assert d["token"] and isinstance(d["token"], str)
        assert d["url"].endswith(f"/convite/{d['token']}")
        coach_setup["invite_token"] = d["token"]

    def test_refreshing_invite_replaces_token(self, coach_setup):
        ath_id = coach_setup["athlete"]["id"]
        old = coach_setup["invite_token"]
        r = requests.post(
            f"{API}/athletes/{ath_id}/invite", headers=coach_setup["headers"]
        )
        assert r.status_code == 200
        new_token = r.json()["token"]
        assert new_token != old
        coach_setup["invite_token"] = new_token

    def test_public_get_invite_info(self, coach_setup):
        tok = coach_setup["invite_token"]
        r = requests.get(f"{API}/invite/{tok}")  # public, no auth
        assert r.status_code == 200
        d = r.json()
        assert d["athlete_name"] == "TEST Athlete Invite"
        assert d["team_name"]

    def test_accept_invite_creates_player(self, coach_setup):
        tok = coach_setup["invite_token"]
        email = f"test_player_{RUN_ID}@futsal.pt"
        pwd = "playerpass123"
        r = requests.post(f"{API}/invite/{tok}/accept", json={
            "email": email, "password": pwd
        })
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["role"] == "player"
        assert d["status"] == "active"
        assert d["athlete_id"] == coach_setup["athlete"]["id"]
        assert d.get("token")
        coach_setup["player"] = {"email": email, "password": pwd, "token": d["token"], "id": d["id"]}

    def test_invite_consumed_after_accept(self, coach_setup):
        tok = coach_setup["invite_token"]
        r = requests.get(f"{API}/invite/{tok}")
        assert r.status_code == 410


class TestPlayerRestrictions:
    """Item 9 — backend forbids coach endpoints for players."""
    @pytest.mark.parametrize("path", [
        "/athletes", "/sessions", "/calendar?start=2026-01-01&days=7", "/teams",
    ])
    def test_player_blocked_from_coach_endpoint(self, coach_setup, path):
        ph = _bearer(coach_setup["player"]["token"])
        r = requests.get(f"{API}{path}", headers=ph)
        assert r.status_code == 403, f"{path} got {r.status_code}"
        assert "atleta" in r.json().get("detail", "").lower()

    def test_player_me_works(self, coach_setup):
        ph = _bearer(coach_setup["player"]["token"])
        r = requests.get(f"{API}/player/me", headers=ph)
        assert r.status_code == 200
        d = r.json()
        assert d["athlete"]["id"] == coach_setup["athlete"]["id"]
        assert d["team"]["name"] == coach_setup["team"]["name"]


class TestPlayerSessions:
    def test_player_create_session(self, coach_setup):
        ph = _bearer(coach_setup["player"]["token"])
        from datetime import date
        payload = {
            "date": date.today().isoformat(),
            "session_type": "training",
            "rpe": 7, "duration_min": 60,
            "sleep_quality": 4, "wellness": 8, "notes": "TEST_session"
        }
        r = requests.post(f"{API}/player/sessions", json=payload, headers=ph)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "load" not in d, f"player session must NOT expose load; got {d}"
        assert d["rpe"] == 7
        coach_setup["session_id"] = d["id"]

    def test_player_list_sessions_no_load(self, coach_setup):
        ph = _bearer(coach_setup["player"]["token"])
        r = requests.get(f"{API}/player/sessions", headers=ph)
        assert r.status_code == 200
        items = r.json()
        assert len(items) >= 1
        for s in items:
            assert "load" not in s, f"item {s.get('id')} leaks load: {s}"

    def test_player_delete_own_session(self, coach_setup):
        ph = _bearer(coach_setup["player"]["token"])
        sid = coach_setup["session_id"]
        r = requests.delete(f"{API}/player/sessions/{sid}", headers=ph)
        assert r.status_code == 200
        # second delete => 404
        r2 = requests.delete(f"{API}/player/sessions/{sid}", headers=ph)
        assert r2.status_code == 404

    def test_player_delete_other_session_404(self, coach_setup):
        ph = _bearer(coach_setup["player"]["token"])
        r = requests.delete(f"{API}/player/sessions/{uuid.uuid4()}", headers=ph)
        assert r.status_code == 404


# ============================================================
# 12) Athlete delete cascade also deletes linked player user
# ============================================================
class TestAthleteCascade:
    def test_athlete_delete_removes_player_user(self, coach_setup, admin_token):
        # Create a new athlete + invite + player, then delete the athlete
        headers = coach_setup["headers"]
        ra = requests.post(f"{API}/athletes", json={
            "name": "TEST Athlete Cascade", "position": "Fixo"
        }, headers=headers)
        assert ra.status_code == 200
        ath = ra.json()
        ri = requests.post(f"{API}/athletes/{ath['id']}/invite", headers=headers)
        tok = ri.json()["token"]
        email = f"test_cascade_player_{RUN_ID}@futsal.pt"
        rp = requests.post(f"{API}/invite/{tok}/accept", json={"email": email, "password": "cascade123"})
        assert rp.status_code == 200
        # Verify player user exists via admin
        ru = requests.get(f"{API}/admin/users", headers=_bearer(admin_token))
        assert any(u["email"] == email for u in ru.json())
        # Now delete the athlete (coach)
        rd = requests.delete(f"{API}/athletes/{ath['id']}", headers=headers)
        assert rd.status_code == 200, rd.text
        # Player user should be gone
        ru2 = requests.get(f"{API}/admin/users", headers=_bearer(admin_token))
        assert not any(u["email"] == email for u in ru2.json()), \
            "linked player account should be deleted with athlete"


# ============================================================
# 5) Admin delete coach cascade — runs LAST so it doubles as cleanup
# ============================================================
class TestZAdminDeleteCoachCascade:
    def test_delete_coach_cascade(self, admin_token, pending_coach, coach_setup):
        coach_id = pending_coach["id"]
        team_id = coach_setup["team"]["id"]
        # capture athlete + player to verify they vanish
        player = coach_setup.get("player", {})
        # Delete the coach
        r = requests.delete(
            f"{API}/admin/users/{coach_id}", headers=_bearer(admin_token)
        )
        assert r.status_code == 200, r.text
        # Verify via admin listing
        ru = requests.get(f"{API}/admin/users", headers=_bearer(admin_token))
        emails = [u["email"] for u in ru.json()]
        assert pending_coach["email"] not in emails
        if player:
            # linked player user must also be gone
            assert player["email"] not in emails, "linked player must be cascaded"
        # Coach login fails (404 -> 401 invalid credentials)
        r2 = requests.post(f"{API}/auth/login", json={
            "email": pending_coach["email"], "password": pending_coach["password"]
        })
        assert r2.status_code == 401
