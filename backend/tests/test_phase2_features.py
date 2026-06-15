"""Phase 2 backend API tests: monthly summary, compare athletes, injuries."""
import os
from datetime import date
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"


@pytest.fixture(scope="module")
def coach():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": "treinador@futsal.pt", "password": "treinador123"}, timeout=20)
    assert r.status_code == 200, r.text
    s.headers.update({"Authorization": f"Bearer {r.json()['token']}"})
    # ensure demo data exists
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


# ---------------- Monthly Summary ----------------
class TestMonthlySummary:
    def test_monthly_returns_6_months(self, coach, athletes):
        aid = athletes[0]["id"]
        r = coach.get(f"{API}/analytics/monthly/{aid}?months=6", timeout=20)
        assert r.status_code == 200
        d = r.json()
        assert d["athlete"]["id"] == aid
        assert len(d["months"]) == 6
        # each month entry has required keys
        for m in d["months"]:
            for k in ("month", "sessions", "total_load", "avg_load", "avg_sleep", "delta_load_pct"):
                assert k in m
        # at least one month has data (seed=45 days)
        assert any(m["avg_load"] > 0 for m in d["months"])
        assert d["evolution"] in ("subiu", "desceu", "estável", "indeterminado")

    def test_monthly_delta_between_consecutive(self, coach, athletes):
        # find athlete with data in >=2 months to actually check delta
        aid = athletes[0]["id"]
        r = coach.get(f"{API}/analytics/monthly/{aid}?months=6", timeout=20)
        months = r.json()["months"]
        # find first month after a previous one with data
        prev_avg = None
        for m in months:
            if m["avg_load"] > 0 and prev_avg is not None and prev_avg > 0:
                expected_pct = round((m["avg_load"] - prev_avg) / prev_avg * 100, 1)
                assert m["delta_load_pct"] == expected_pct
                break
            if m["avg_load"] > 0:
                prev_avg = m["avg_load"]

    def test_monthly_404_unknown_athlete(self, coach):
        r = coach.get(f"{API}/analytics/monthly/non-existent-id?months=6", timeout=20)
        assert r.status_code == 404


# ---------------- Compare ----------------
class TestCompare:
    def test_compare_two_athletes(self, coach, athletes):
        a1, a2 = athletes[0]["id"], athletes[1]["id"]
        r = coach.get(f"{API}/analytics/compare", params={"a1": a1, "a2": a2}, timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d["a1"]["athlete"]["id"] == a1
        assert d["a2"]["athlete"]["id"] == a2
        for side in ("a1", "a2"):
            for k in ("acute", "chronic", "acwr", "monotony", "strain", "risk"):
                assert k in d[side]["metrics"]
        assert len(d["merged_series"]) == 60
        for p in d["merged_series"][:3]:
            for k in ("date", "a1_acwr", "a2_acwr"):
                assert k in p

    def test_compare_404_unknown(self, coach, athletes):
        r = coach.get(f"{API}/analytics/compare", params={"a1": athletes[0]["id"], "a2": "nope"}, timeout=20)
        assert r.status_code == 404


# ---------------- Injuries ----------------
class TestInjuries:
    def test_list_injuries_seeded(self, coach, athletes):
        # demo seed creates 3 injuries
        r = coach.get(f"{API}/injuries", timeout=15)
        assert r.status_code == 200
        items = r.json()
        assert len(items) >= 3
        # João Silva should have a Contratura/Lombar/low
        joao = next((a for a in athletes if a["name"] == "João Silva"), None)
        assert joao is not None
        ri = coach.get(f"{API}/injuries", params={"athlete_id": joao["id"]}, timeout=15)
        items_j = ri.json()
        assert any(i["type"] == "Contratura" and i["body_part"] == "Lombar" and i["severity"] == "low" for i in items_j)

    def test_create_invalid_severity_returns_400(self, coach, athletes):
        payload = {
            "athlete_id": athletes[0]["id"],
            "type": "Test", "body_part": "Test",
            "start_date": date.today().isoformat(),
            "severity": "extreme",
        }
        r = coach.post(f"{API}/injuries", json=payload, timeout=15)
        # Pydantic field is plain str so backend validates manually -> 400
        assert r.status_code == 400, f"got {r.status_code}: {r.text}"

    def test_create_and_delete_injury(self, coach, athletes):
        aid = athletes[2]["id"]
        payload = {
            "athlete_id": aid,
            "type": "TEST_Lesão muscular",
            "body_part": "Coxa esquerda",
            "start_date": date.today().isoformat(),
            "severity": "high",
        }
        r = coach.post(f"{API}/injuries", json=payload, timeout=15)
        assert r.status_code == 200, r.text
        inj = r.json()
        assert inj["severity"] == "high"
        assert inj["end_date"] is None
        iid = inj["id"]

        # GET to verify persistence
        lst = coach.get(f"{API}/injuries", params={"athlete_id": aid}, timeout=15).json()
        assert any(i["id"] == iid for i in lst)

        # delete
        rd = coach.delete(f"{API}/injuries/{iid}", timeout=15)
        assert rd.status_code == 200
        lst2 = coach.get(f"{API}/injuries", params={"athlete_id": aid}, timeout=15).json()
        assert not any(i["id"] == iid for i in lst2)

    def test_create_unknown_athlete_404(self, coach):
        payload = {
            "athlete_id": "nonexistent",
            "type": "x", "body_part": "y",
            "start_date": date.today().isoformat(),
            "severity": "low",
        }
        r = coach.post(f"{API}/injuries", json=payload, timeout=15)
        assert r.status_code == 404
