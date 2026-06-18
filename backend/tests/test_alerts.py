"""Backend tests for the new /api/alerts endpoint (notifications feature)."""
import os
from datetime import date

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://futsal-load-hub.preview.emergentagent.com").rstrip("/")
EMAIL = "treinador@futsal.pt"
PASSWORD = "treinador123"


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    token = r.json().get("token")
    if token:
        s.headers.update({"Authorization": f"Bearer {token}"})
    return s


@pytest.fixture(scope="module")
def athlete_id(client):
    # use first existing athlete from active team
    r = client.get(f"{BASE_URL}/api/athletes")
    assert r.status_code == 200, r.text
    athletes = r.json()
    if not athletes:
        # seed demo if no team
        client.post(f"{BASE_URL}/api/seed/demo")
        r = client.get(f"{BASE_URL}/api/athletes")
        athletes = r.json()
    assert len(athletes) > 0, "No athletes available"
    return athletes[0]["id"]


def _get_alerts(client):
    r = client.get(f"{BASE_URL}/api/alerts")
    assert r.status_code == 200, f"GET /api/alerts failed: {r.status_code} {r.text}"
    data = r.json()
    assert isinstance(data, list), "Expected list response"
    return data


def test_alerts_endpoint_returns_list(client):
    alerts = _get_alerts(client)
    # validate shape if any alert exists
    for a in alerts:
        assert "id" in a
        assert "type" in a
        assert "severity" in a and a["severity"] in ("danger", "warning", "info")
        assert "athlete_id" in a
        assert "athlete_name" in a
        assert "title" in a
        assert "message" in a
        assert "created_at" in a
        # id pattern: {type}_{athlete_id} for athlete-bound; injury_open_{injury_id}
        if a["type"] != "injury_open":
            assert a["id"] == f"{a['type']}_{a['athlete_id']}", f"id mismatch: {a['id']}"


def test_alerts_sorted_by_severity(client):
    alerts = _get_alerts(client)
    order = {"danger": 0, "warning": 1, "info": 2}
    prev = -1
    for a in alerts:
        cur = order.get(a["severity"], 9)
        assert cur >= prev, f"alerts not sorted by severity: {[x['severity'] for x in alerts]}"
        prev = cur


def test_alert_for_open_high_severity_injury(client, athlete_id):
    # Create open high-severity injury
    payload = {
        "athlete_id": athlete_id,
        "type": "TEST_Lesao",
        "body_part": "tornozelo",
        "start_date": str(date.today()),
        "end_date": None,
        "severity": "high",
        "notes": "TEST notification alert",
    }
    r = client.post(f"{BASE_URL}/api/injuries", json=payload)
    assert r.status_code in (200, 201), r.text
    inj = r.json()
    injury_id = inj["id"]

    try:
        alerts = _get_alerts(client)
        injury_alerts = [a for a in alerts if a["type"] == "injury_open" and a["id"] == f"injury_open_{injury_id}"]
        assert len(injury_alerts) == 1, f"injury alert not found. Alerts: {alerts}"
        ia = injury_alerts[0]
        assert ia["severity"] == "danger", "high severity injury should be danger"
        assert ia["athlete_id"] == athlete_id
        assert ia["title"] == "Lesão em curso"
        # threshold key must exist (can be None)
        assert "threshold" in ia
        assert "value" in ia
    finally:
        # cleanup
        rdel = client.delete(f"{BASE_URL}/api/injuries/{injury_id}")
        assert rdel.status_code in (200, 204), rdel.text

    # Confirm alert removed
    alerts_after = _get_alerts(client)
    assert not any(a["id"] == f"injury_open_{injury_id}" for a in alerts_after), "alert should be gone after delete"


def test_alert_for_open_medium_severity_injury_is_warning(client, athlete_id):
    payload = {
        "athlete_id": athlete_id,
        "type": "TEST_LesaoMed",
        "body_part": "joelho",
        "start_date": str(date.today()),
        "end_date": None,
        "severity": "medium",
    }
    r = client.post(f"{BASE_URL}/api/injuries", json=payload)
    assert r.status_code in (200, 201), r.text
    injury_id = r.json()["id"]
    try:
        alerts = _get_alerts(client)
        match = [a for a in alerts if a["id"] == f"injury_open_{injury_id}"]
        assert len(match) == 1
        assert match[0]["severity"] == "warning"
    finally:
        client.delete(f"{BASE_URL}/api/injuries/{injury_id}")


def test_closed_injury_does_not_create_alert(client, athlete_id):
    payload = {
        "athlete_id": athlete_id,
        "type": "TEST_LesaoFechada",
        "body_part": "coxa",
        "start_date": str(date.today()),
        "end_date": str(date.today()),
        "severity": "high",
    }
    r = client.post(f"{BASE_URL}/api/injuries", json=payload)
    assert r.status_code in (200, 201), r.text
    injury_id = r.json()["id"]
    try:
        alerts = _get_alerts(client)
        assert not any(a["id"] == f"injury_open_{injury_id}" for a in alerts), "closed injury should not alert"
    finally:
        client.delete(f"{BASE_URL}/api/injuries/{injury_id}")


def test_alerts_requires_auth():
    r = requests.get(f"{BASE_URL}/api/alerts")
    assert r.status_code in (401, 403), f"Expected 401/403 for unauth, got {r.status_code}"
