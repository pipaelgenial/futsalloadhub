"""Backend tests for configurable load_thresholds (iteration 11)."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")
if not BASE_URL:
    # fallback to frontend .env via dotenv-style read
    fe_env = "/app/frontend/.env"
    if os.path.exists(fe_env):
        for line in open(fe_env):
            if line.startswith("REACT_APP_BACKEND_URL"):
                BASE_URL = line.split("=", 1)[1].strip().strip('"')
                break
BASE_URL = (BASE_URL or "").rstrip("/")

EMAIL = "treinador@futsal.pt"
PASSWORD = "treinador123"
DEFAULTS = {"ideal": 300, "moderate": 600, "high": 900, "very_high": 1200}


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=20)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    tok = r.json().get("token")
    s.headers.update({"Authorization": f"Bearer {tok}", "Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def cleanup_state(client):
    """Track created teams; at the end delete them and reset demo team thresholds to defaults."""
    created = []
    # capture initial active team id and its thresholds
    r = client.get(f"{BASE_URL}/api/team")
    initial_team = r.json() if r.status_code == 200 and r.json() else None
    yield created, initial_team
    # cleanup created teams
    for tid in created:
        try:
            client.delete(f"{BASE_URL}/api/teams/{tid}")
        except Exception:
            pass
    # reset demo team thresholds to defaults
    if initial_team and initial_team.get("id"):
        try:
            client.put(f"{BASE_URL}/api/teams/{initial_team['id']}", json={
                "name": initial_team["name"],
                "escalao": initial_team["escalao"],
                "epoca": initial_team["epoca"],
                "load_thresholds": DEFAULTS,
            })
        except Exception:
            pass


# 1) GET /api/team returns load_thresholds (defaults present)
def test_get_team_has_thresholds(client):
    r = client.get(f"{BASE_URL}/api/team")
    assert r.status_code == 200
    team = r.json()
    assert team and "load_thresholds" in team
    t = team["load_thresholds"]
    for k in ("ideal", "moderate", "high", "very_high"):
        assert k in t
        assert isinstance(t[k], int)
    assert 0 < t["ideal"] < t["moderate"] < t["high"] < t["very_high"]


# 2) GET /api/teams returns load_thresholds in each team
def test_get_teams_has_thresholds(client):
    r = client.get(f"{BASE_URL}/api/teams")
    assert r.status_code == 200
    teams = r.json()
    assert isinstance(teams, list) and len(teams) >= 1
    for t in teams:
        assert "load_thresholds" in t
        lt = t["load_thresholds"]
        for k in ("ideal", "moderate", "high", "very_high"):
            assert k in lt


# 3) POST /api/teams with custom thresholds persists and returns them
def test_create_team_with_custom_thresholds(client, cleanup_state):
    created, _ = cleanup_state
    payload = {
        "name": "TEST_Sub13",
        "escalao": "Sub-13",
        "epoca": "2025/2026",
        "load_thresholds": {"ideal": 200, "moderate": 400, "high": 600, "very_high": 800},
    }
    r = client.post(f"{BASE_URL}/api/teams", json=payload)
    if r.status_code == 400 and "Limite" in r.text:
        pytest.skip("max teams reached, skipping creation tests")
    assert r.status_code == 200, r.text
    body = r.json()
    created.append(body["id"])
    assert body["load_thresholds"] == {"ideal": 200, "moderate": 400, "high": 600, "very_high": 800}
    # verify via GET /api/teams
    teams = client.get(f"{BASE_URL}/api/teams").json()
    match = next((t for t in teams if t["id"] == body["id"]), None)
    assert match and match["load_thresholds"]["ideal"] == 200


# 4) POST /api/teams without thresholds uses defaults
def test_create_team_without_thresholds_uses_defaults(client, cleanup_state):
    created, _ = cleanup_state
    payload = {"name": "TEST_Defaults", "escalao": "Sénior", "epoca": "2025/2026"}
    r = client.post(f"{BASE_URL}/api/teams", json=payload)
    if r.status_code == 400 and "Limite" in r.text:
        pytest.skip("max teams reached")
    assert r.status_code == 200, r.text
    body = r.json()
    created.append(body["id"])
    assert body["load_thresholds"] == DEFAULTS


# 5) PUT /api/teams/{id} with invalid thresholds -> 400
def test_put_invalid_thresholds_returns_400(client, cleanup_state):
    created, _ = cleanup_state
    # ensure we have a team to update
    if not created:
        # create one
        r = client.post(f"{BASE_URL}/api/teams", json={
            "name": "TEST_ForInvalid", "escalao": "Sub-17", "epoca": "2025/2026",
        })
        if r.status_code != 200:
            pytest.skip("cannot create team")
        created.append(r.json()["id"])
    tid = created[0]
    # non-increasing
    bad = {"ideal": 600, "moderate": 400, "high": 900, "very_high": 1200}
    r = client.put(f"{BASE_URL}/api/teams/{tid}", json={
        "name": "TEST_X", "escalao": "Sub-17", "epoca": "2025/2026",
        "load_thresholds": bad,
    })
    assert r.status_code == 400
    assert "imiares" in r.text or "inv" in r.text.lower()
    # negatives
    bad2 = {"ideal": -1, "moderate": 400, "high": 600, "very_high": 800}
    r2 = client.put(f"{BASE_URL}/api/teams/{tid}", json={
        "name": "TEST_X", "escalao": "Sub-17", "epoca": "2025/2026",
        "load_thresholds": bad2,
    })
    assert r2.status_code == 400


# 6) PUT /api/teams/{id} with valid thresholds updates
def test_put_valid_thresholds_updates(client, cleanup_state):
    created, _ = cleanup_state
    if not created:
        pytest.skip("no team available")
    tid = created[0]
    new_th = {"ideal": 350, "moderate": 700, "high": 1050, "very_high": 1400}
    r = client.put(f"{BASE_URL}/api/teams/{tid}", json={
        "name": "TEST_Updated", "escalao": "Sub-19", "epoca": "2025/2026",
        "load_thresholds": new_th,
    })
    assert r.status_code == 200, r.text
    assert r.json()["load_thresholds"] == new_th
    # verify persisted
    teams = client.get(f"{BASE_URL}/api/teams").json()
    match = next((t for t in teams if t["id"] == tid), None)
    assert match and match["load_thresholds"] == new_th
