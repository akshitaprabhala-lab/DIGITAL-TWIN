"""TwinMed backend regression test suite.

Covers: auth (login/register/me/logout), catalog, patients CRUD,
analyse, disease-scan, simulate (metformin), optimise (AI rationale),
case-summary + save-case + patient cases list.
"""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") if os.environ.get("REACT_APP_BACKEND_URL") else None
if not BASE_URL:
    # fallback to frontend .env
    from pathlib import Path
    envf = Path("/app/frontend/.env")
    for line in envf.read_text().splitlines():
        if line.startswith("REACT_APP_BACKEND_URL="):
            BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
            break

API = f"{BASE_URL}/api"

SEED_EMAIL = "doctor@twinmed.app"
SEED_PW = "twinmed123"


# ---------------- fixtures ----------------
@pytest.fixture(scope="session")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="session")
def auth_token(session):
    r = session.post(f"{API}/auth/login", json={"email": SEED_EMAIL, "password": SEED_PW}, timeout=15)
    assert r.status_code == 200, f"Seed login failed: {r.status_code} {r.text}"
    data = r.json()
    assert "token" in data
    return data["token"]


@pytest.fixture(scope="session")
def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="session")
def anaya_patient_id(auth_headers):
    r = requests.get(f"{API}/patients", headers=auth_headers, timeout=15)
    assert r.status_code == 200
    patients = r.json()
    anaya = next((p for p in patients if p["name"] == "Anaya Sharma"), None)
    assert anaya, "Anaya Sharma seed patient not found"
    return anaya["id"]


# ---------------- health / root ----------------
class TestRoot:
    def test_root(self, session):
        r = session.get(f"{API}/", timeout=15)
        assert r.status_code == 200
        assert r.json().get("status") == "ok"


# ---------------- auth ----------------
class TestAuth:
    def test_login_seed(self, session):
        r = session.post(f"{API}/auth/login", json={"email": SEED_EMAIL, "password": SEED_PW}, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["email"] == SEED_EMAIL
        assert d["role"] == "doctor"
        assert isinstance(d["token"], str) and len(d["token"]) > 20

    def test_login_wrong_password(self, session):
        r = session.post(f"{API}/auth/login", json={"email": SEED_EMAIL, "password": "wrong"}, timeout=15)
        assert r.status_code == 401

    def test_me_requires_auth(self):
        # fresh session without cookies
        r = requests.get(f"{API}/auth/me", timeout=15)
        assert r.status_code == 401

    def test_me_with_bearer(self, auth_headers):
        r = requests.get(f"{API}/auth/me", headers=auth_headers, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["email"] == SEED_EMAIL
        assert "password_hash" not in d

    def test_register_new_doctor(self, session):
        email = f"test_{uuid.uuid4().hex[:8]}@twinmed.app"
        r = session.post(f"{API}/auth/register",
                         json={"email": email, "password": "abc12345", "name": "Test Doc"},
                         timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["email"] == email.lower()
        assert d["role"] == "doctor"
        assert d["token"]
        # duplicate
        r2 = requests.post(f"{API}/auth/register",
                           json={"email": email, "password": "abc12345", "name": "Dup"},
                           timeout=15)
        assert r2.status_code == 400


# ---------------- catalog ----------------
class TestCatalog:
    def test_catalog(self, auth_headers):
        r = requests.get(f"{API}/catalog", headers=auth_headers, timeout=15)
        assert r.status_code == 200
        d = r.json()
        for key in ("parameters", "organs", "diseases", "drugs"):
            assert key in d
        # metformin exists
        drug_ids = [x["id"] for x in d["drugs"]]
        assert "metformin" in drug_ids
        assert "fasting_glucose" in d["parameters"]
        # SA threshold present
        assert "south_asian" in d["parameters"]["fasting_glucose"]

    def test_catalog_requires_auth(self):
        r = requests.get(f"{API}/catalog", timeout=15)
        assert r.status_code == 401


# ---------------- patients ----------------
class TestPatients:
    def test_seed_patients_present(self, auth_headers):
        r = requests.get(f"{API}/patients", headers=auth_headers, timeout=15)
        assert r.status_code == 200
        names = {p["name"] for p in r.json()}
        assert {"Anaya Sharma", "Marcus Bell", "Priya Nair"} <= names

    def test_get_patient_returns_twin(self, auth_headers, anaya_patient_id):
        r = requests.get(f"{API}/patients/{anaya_patient_id}", headers=auth_headers, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["name"] == "Anaya Sharma"
        assert "twin" in d
        assert d["twin"]["basal_glucose"] == 158

    def test_create_update_delete_patient(self, auth_headers):
        payload = {
            "name": "TEST_Patient_1", "age": 40, "sex": "male", "ethnicity": "other",
            "weight_kg": 78, "height_cm": 172, "history": "Test", "medications": [],
            "conditions": [],
            "parameters": {"fasting_glucose": 96, "hba1c": 5.4, "systolic_bp": 118,
                           "diastolic_bp": 76, "heart_rate": 70, "spo2": 98,
                           "hemoglobin": 14.1, "tsh": 1.9, "ldl": 92}
        }
        r = requests.post(f"{API}/patients", headers=auth_headers, json=payload, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        pid = d["id"]
        assert d["twin"]["basal_glucose"] == 96
        # GET back
        r2 = requests.get(f"{API}/patients/{pid}", headers=auth_headers, timeout=15)
        assert r2.status_code == 200
        assert r2.json()["name"] == "TEST_Patient_1"

        # Update
        payload["parameters"]["fasting_glucose"] = 140
        payload["name"] = "TEST_Patient_1_up"
        r3 = requests.put(f"{API}/patients/{pid}", headers=auth_headers, json=payload, timeout=15)
        assert r3.status_code == 200
        # verify persistence via GET
        r4 = requests.get(f"{API}/patients/{pid}", headers=auth_headers, timeout=15)
        assert r4.json()["name"] == "TEST_Patient_1_up"
        assert r4.json()["parameters"]["fasting_glucose"] == 140

        # DELETE
        r5 = requests.delete(f"{API}/patients/{pid}", headers=auth_headers, timeout=15)
        assert r5.status_code == 200
        r6 = requests.get(f"{API}/patients/{pid}", headers=auth_headers, timeout=15)
        assert r6.status_code == 404


# ---------------- analyse ----------------
class TestAnalyse:
    def test_analyse_std_vs_sa(self, auth_headers):
        params = {"fasting_glucose": 95, "hba1c": 5.5}
        r = requests.post(f"{API}/analyse", headers=auth_headers,
                          json={"parameters": params, "threshold": "standard"}, timeout=15)
        assert r.status_code == 200
        std = {a["key"]: a for a in r.json()["analysis"]}
        assert std["fasting_glucose"]["in_range"] is True

        r2 = requests.post(f"{API}/analyse", headers=auth_headers,
                           json={"parameters": params, "threshold": "south_asian"}, timeout=15)
        sa = {a["key"]: a for a in r2.json()["analysis"]}
        # 95 fasting is high on SA (band 70-90)
        assert sa["fasting_glucose"]["in_range"] is False
        assert sa["fasting_glucose"]["side"] == "high"


# ---------------- disease scan ----------------
class TestDiseaseScan:
    def test_disease_scan_anaya(self, auth_headers, anaya_patient_id):
        r = requests.post(f"{API}/disease-scan", headers=auth_headers,
                          json={"patient_id": anaya_patient_id, "threshold": "standard"},
                          timeout=60)
        assert r.status_code == 200, r.text
        d = r.json()
        assert isinstance(d["flags"], list)
        assert isinstance(d["summary"], str) and len(d["summary"]) > 10
        # Anaya has elevated fasting_glucose+hba1c => should flag t2dm
        disease_ids = [f["disease_id"] for f in d["flags"]]
        assert "t2dm" in disease_ids


# ---------------- simulate ----------------
class TestSimulate:
    def test_simulate_metformin_lowers_glucose(self, auth_headers, anaya_patient_id):
        r = requests.post(f"{API}/simulate", headers=auth_headers,
                          json={"patient_id": anaya_patient_id, "drug_id": "metformin",
                                "dose": 1500, "threshold": "standard", "meal_carbs_g": 60},
                          timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["system"] == "metabolic"
        assert d["target"] == "fasting_glucose"
        assert d["series"]
        # peak_treated should be lower than peak_baseline for a T2D patient
        assert d["peak_treated"] < d["peak_baseline"]

    def test_simulate_unknown_drug(self, auth_headers, anaya_patient_id):
        r = requests.post(f"{API}/simulate", headers=auth_headers,
                          json={"patient_id": anaya_patient_id, "drug_id": "nope", "dose": 1000},
                          timeout=15)
        assert r.status_code == 404


# ---------------- optimise ----------------
class TestOptimise:
    def test_optimise_metformin(self, auth_headers, anaya_patient_id):
        r = requests.post(f"{API}/optimise", headers=auth_headers,
                          json={"patient_id": anaya_patient_id, "drug_id": "metformin",
                                "threshold": "standard"},
                          timeout=60)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["drug"]["id"] == "metformin"
        assert d["recommended_dose"] > 0
        assert 0.0 <= d["confidence"] <= 1.0
        assert isinstance(d["rationale"], str) and len(d["rationale"]) > 20
        assert d["baseline_value"] > d["predicted_value"]  # metformin lowers glucose
        assert "trajectory" in d and d["trajectory"]["series"]


# ---------------- case summary + save case ----------------
class TestCaseAndSave:
    def test_case_summary_and_save(self, auth_headers, anaya_patient_id):
        r = requests.post(f"{API}/case-summary", headers=auth_headers,
                          json={"patient_id": anaya_patient_id, "threshold": "standard",
                                "tried": ["Metformin 1500 mg/day -> 158 -> 130"]},
                          timeout=60)
        assert r.status_code == 200, r.text
        d = r.json()
        assert isinstance(d["summary"], str) and len(d["summary"]) > 20
        assert isinstance(d["out_of_range"], list) and len(d["out_of_range"]) > 0
        assert isinstance(d["analysis"], list)

        # save case
        payload = {"analysis": d["analysis"], "summary": d["summary"], "tried": ["Metformin 1500"]}
        r2 = requests.post(f"{API}/save-case", headers=auth_headers,
                           json={"patient_id": anaya_patient_id, "payload": payload},
                           timeout=15)
        assert r2.status_code == 200
        assert "id" in r2.json()

        # list cases
        r3 = requests.get(f"{API}/patients/{anaya_patient_id}/cases", headers=auth_headers, timeout=15)
        assert r3.status_code == 200
        cases = r3.json()
        assert isinstance(cases, list) and len(cases) >= 1
