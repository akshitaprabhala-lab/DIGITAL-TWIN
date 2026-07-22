"""TwinMed backend regression test suite.

Covers: auth (login/register/me/logout), catalog, patients CRUD,
analyse, disease-scan, simulate (metformin, lisinopril, salbutamol),
optimise (AI rationale + combination therapy), case-summary + save-case
+ patient cases list, virtual clinical trial, live sensor SSE stream.
"""
import os
import json
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


# ---------------- Deeper models: cardiovascular + respiratory ----------------
class TestDeeperModels:
    """Verify simulate now uses mechanistic BP / SpO2 ODE integration."""

    @pytest.fixture(scope="class")
    def marcus_id(self, auth_headers):
        r = requests.get(f"{API}/patients", headers=auth_headers, timeout=15)
        assert r.status_code == 200
        m = next((p for p in r.json() if p["name"] == "Marcus Bell"), None)
        assert m, "Marcus Bell seed patient missing"
        return m["id"]

    def test_simulate_lisinopril_bp_trajectory(self, auth_headers, marcus_id):
        r = requests.post(f"{API}/simulate", headers=auth_headers,
                          json={"patient_id": marcus_id, "drug_id": "lisinopril",
                                "dose": 20, "threshold": "standard"},
                          timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["system"] == "cardiovascular"
        assert d["target"] == "systolic_bp"
        assert d["x_label"] == "days"
        assert d["series"] and len(d["series"]) > 5
        # treated must fall below baseline over time
        assert d["series"][-1]["treated"] < d["series"][0]["baseline"]
        # predicted value must be a plausible BP number
        assert 90 <= d["predicted_value"] <= 160

    def test_simulate_salbutamol_spo2_trajectory(self, auth_headers, marcus_id):
        r = requests.post(f"{API}/simulate", headers=auth_headers,
                          json={"patient_id": marcus_id, "drug_id": "salbutamol",
                                "dose": 200, "threshold": "standard"},
                          timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["system"] == "respiratory"
        assert d["target"] == "spo2"
        assert d["x_label"] == "minutes"
        assert d["series"] and len(d["series"]) > 5
        # SpO2 goes UP with salbutamol
        max_treated = max(pt["treated"] for pt in d["series"])
        assert max_treated > d["series"][0]["baseline"]
        assert 85 <= d["predicted_value"] <= 100


# ---------------- Combination therapy ----------------
class TestCombinationTherapy:
    """Verify optimise proposes a combination when single-agent can't reach the band."""

    @pytest.fixture(scope="class")
    def marcus_id(self, auth_headers):
        r = requests.get(f"{API}/patients", headers=auth_headers, timeout=15)
        m = next((p for p in r.json() if p["name"] == "Marcus Bell"), None)
        assert m
        return m["id"]

    @pytest.fixture(scope="class")
    def anaya_id(self, auth_headers):
        r = requests.get(f"{API}/patients", headers=auth_headers, timeout=15)
        a = next((p for p in r.json() if p["name"] == "Anaya Sharma"), None)
        assert a
        return a["id"]

    def test_lisinopril_combo_with_amlodipine(self, auth_headers, marcus_id):
        r = requests.post(f"{API}/optimise", headers=auth_headers,
                          json={"patient_id": marcus_id, "drug_id": "lisinopril",
                                "threshold": "standard"},
                          timeout=60)
        assert r.status_code == 200, r.text
        d = r.json()
        # Marcus Bell has systolic 156 mmHg — lisinopril alone cannot reach 90–120 band
        assert d["combination"] is not None, "Expected combination when single-agent can't reach target"
        combo = d["combination"]
        assert combo["primary"]["id"] == "lisinopril"
        assert combo["secondary"]["id"] == "amlodipine"
        assert combo["secondary"]["dose"] > 0
        # combination should lower predicted value vs single-agent max-dose predicted
        assert combo["predicted_value"] < d["predicted_value"], (
            f"combo {combo['predicted_value']} should be < single {d['predicted_value']}")
        # trajectory embeds combination effect
        assert d["trajectory"]["system"] == "cardiovascular"

    def test_metformin_combo_with_empagliflozin_on_south_asian(self, auth_headers, anaya_id):
        # Anaya is south_asian with fasting_glucose=158 and SA band is 70-90 (very tight)
        r = requests.post(f"{API}/optimise", headers=auth_headers,
                          json={"patient_id": anaya_id, "drug_id": "metformin",
                                "threshold": "south_asian"},
                          timeout=60)
        assert r.status_code == 200, r.text
        d = r.json()
        # single-agent metformin (max 2000 mg) drops 32 mg/dL → 126 which is above 90 SA cap
        assert d["combination"] is not None, "SA threshold should trigger combination"
        assert d["combination"]["primary"]["id"] == "metformin"
        assert d["combination"]["secondary"]["id"] == "empagliflozin"
        assert d["combination"]["predicted_value"] < d["predicted_value"]


# ---------------- Virtual clinical trial ----------------
class TestVirtualTrial:
    """POST /api/trial/run runs a drug across a cohort of synthetic twins."""

    def _assert_shape(self, d, size):
        # required keys
        for k in ("drug", "target_label", "unit", "band", "cohort_size",
                  "dose_summary", "best_dose", "breakdown", "twins", "summary"):
            assert k in d, f"missing {k}"
        assert d["cohort_size"] == size
        assert isinstance(d["dose_summary"], list) and len(d["dose_summary"]) >= 1
        for row in d["dose_summary"]:
            for k in ("dose", "pct_in_range", "pct_responder", "pct_side_effect", "mean_predicted"):
                assert k in row
            assert 0 <= row["pct_in_range"] <= 100
            assert 0 <= row["pct_responder"] <= 100
            assert 0 <= row["pct_side_effect"] <= 100
        # best_dose is a member of dose_summary
        assert d["best_dose"]["dose"] in [r["dose"] for r in d["dose_summary"]]
        # breakdown sums roughly = cohort size (in_range and improved are mutually exclusive by def)
        bd = d["breakdown"]
        assert bd["in_range"] + bd["improved"] + bd["no_change"] == size or (
            bd["in_range"] + bd["improved"] + bd["no_change"] <= size)
        assert 0 <= bd["side_effect"] <= size
        # twins array
        assert isinstance(d["twins"], list) and len(d["twins"]) == size
        for tw in d["twins"][:3]:
            for k in ("id", "baseline", "predicted", "in_range", "side_effect"):
                assert k in tw
        # AI summary
        assert isinstance(d["summary"], str) and len(d["summary"]) > 20

    def test_trial_metformin(self, auth_headers):
        r = requests.post(f"{API}/trial/run", headers=auth_headers,
                          json={"drug_id": "metformin", "cohort_size": 40, "seed": 42},
                          timeout=90)
        assert r.status_code == 200, r.text
        d = r.json()
        self._assert_shape(d, 40)
        assert d["drug"]["id"] == "metformin"
        # metformin trial should have a healthy responder rate at best dose
        assert d["best_dose"]["pct_responder"] > 20

    def test_trial_lisinopril(self, auth_headers):
        r = requests.post(f"{API}/trial/run", headers=auth_headers,
                          json={"drug_id": "lisinopril", "cohort_size": 40, "seed": 7},
                          timeout=90)
        assert r.status_code == 200, r.text
        d = r.json()
        self._assert_shape(d, 40)
        assert d["drug"]["id"] == "lisinopril"

    def test_trial_salbutamol(self, auth_headers):
        r = requests.post(f"{API}/trial/run", headers=auth_headers,
                          json={"drug_id": "salbutamol", "cohort_size": 40, "seed": 3},
                          timeout=90)
        assert r.status_code == 200, r.text
        d = r.json()
        self._assert_shape(d, 40)
        assert d["drug"]["id"] == "salbutamol"

    def test_trial_unknown_drug(self, auth_headers):
        r = requests.post(f"{API}/trial/run", headers=auth_headers,
                          json={"drug_id": "nope", "cohort_size": 20}, timeout=15)
        assert r.status_code == 404


# ---------------- Live sensor SSE stream ----------------
class TestSensorStream:
    """GET /api/sensor/stream/{pid} is an unauthenticated SSE feed."""

    @pytest.fixture(scope="class")
    def anaya_id(self, auth_headers):
        r = requests.get(f"{API}/patients", headers=auth_headers, timeout=15)
        a = next((p for p in r.json() if p["name"] == "Anaya Sharma"), None)
        return a["id"]

    def test_sse_unauthenticated_and_streams_events(self, anaya_id):
        # Fresh session (no bearer, no cookie) — endpoint is intentionally unauth
        url = f"{API}/sensor/stream/{anaya_id}?seconds=3"
        with requests.get(url, stream=True, timeout=20) as r:
            assert r.status_code == 200
            ctype = r.headers.get("content-type", "")
            assert "text/event-stream" in ctype, f"unexpected content-type {ctype}"

            events = []
            done = False
            for raw in r.iter_lines(decode_unicode=True):
                if not raw:
                    continue
                if not raw.startswith("data:"):
                    continue
                payload = raw[len("data:"):].strip()
                obj = json.loads(payload)
                if obj.get("done"):
                    done = True
                    break
                events.append(obj)
                if len(events) >= 3:  # keep it fast, just verify schema on first few
                    pass
        # verify at least a handful of sensor events arrived and schema is correct
        assert len(events) >= 4, f"expected multiple SSE events, got {len(events)}"
        first = events[0]
        assert "sensor" in first and "model_glucose" in first
        for k in ("lactate", "cortisol", "sodium", "heart_rate", "spo2"):
            assert k in first["sensor"], f"missing sensor key {k}"
        # sweat glucose is NOT read directly — but the derived model_glucose must be present
        assert isinstance(first["model_glucose"], (int, float))
        assert done or len(events) > 4  # either the done sentinel arrived, or enough events did

    def test_sse_unknown_patient(self):
        r = requests.get(f"{API}/sensor/stream/does-not-exist?seconds=2", timeout=10)
        assert r.status_code == 404


# ---------------- Mechanistic Iron (hematologic) model ----------------
class TestIronMechanistic:
    """Priya Nair has Hb 9.4 g/dL — ferrous_sulfate should raise Hb via ODE."""

    @pytest.fixture(scope="class")
    def priya_id(self, auth_headers):
        r = requests.get(f"{API}/patients", headers=auth_headers, timeout=15)
        p = next((x for x in r.json() if x["name"] == "Priya Nair"), None)
        assert p, "Priya Nair seed patient missing"
        return p["id"]

    def test_simulate_ferrous_sulfate_hb_rises(self, auth_headers, priya_id):
        r = requests.post(f"{API}/simulate", headers=auth_headers,
                          json={"patient_id": priya_id, "drug_id": "ferrous_sulfate",
                                "dose": 130, "threshold": "standard"},
                          timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["system"] == "hematologic"
        assert d["target"] == "hemoglobin"
        assert d["x_label"] == "days"
        assert d["series"] and len(d["series"]) > 5
        # Hb should rise from ~9.4
        assert d["series"][0]["treated"] <= d["series"][-1]["treated"], \
            "treated Hb should be non-decreasing over time"
        assert d["series"][-1]["treated"] > 9.4, \
            f"treated final Hb {d['series'][-1]['treated']} should exceed 9.4"
        assert 9.4 <= d["predicted_value"] <= 16.0

    def test_ferrous_dose_sensitivity(self, auth_headers, priya_id):
        r_low = requests.post(f"{API}/simulate", headers=auth_headers,
                              json={"patient_id": priya_id, "drug_id": "ferrous_sulfate",
                                    "dose": 65, "threshold": "standard"}, timeout=30)
        r_hi = requests.post(f"{API}/simulate", headers=auth_headers,
                             json={"patient_id": priya_id, "drug_id": "ferrous_sulfate",
                                   "dose": 130, "threshold": "standard"}, timeout=30)
        assert r_low.status_code == 200 and r_hi.status_code == 200
        low_final = r_low.json()["series"][-1]["treated"]
        hi_final = r_hi.json()["series"][-1]["treated"]
        assert hi_final > low_final, \
            f"130mg final Hb {hi_final} should exceed 65mg final Hb {low_final}"

    def test_optimise_ferrous_sulfate(self, auth_headers, priya_id):
        r = requests.post(f"{API}/optimise", headers=auth_headers,
                          json={"patient_id": priya_id, "drug_id": "ferrous_sulfate",
                                "threshold": "standard"}, timeout=60)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["drug"]["id"] == "ferrous_sulfate"
        assert d["recommended_dose"] > 0
        # trajectory embedded and mechanistic
        assert d["trajectory"]["system"] == "hematologic"
        assert d["predicted_value"] > d["baseline_value"], \
            f"predicted {d['predicted_value']} should exceed baseline {d['baseline_value']}"


# ---------------- Mechanistic Thyroid (endocrine) model ----------------
class TestThyroidMechanistic:
    """Priya has TSH 8.7 — levothyroxine should suppress TSH into 0.4–4.0 band."""

    @pytest.fixture(scope="class")
    def priya_id(self, auth_headers):
        r = requests.get(f"{API}/patients", headers=auth_headers, timeout=15)
        p = next((x for x in r.json() if x["name"] == "Priya Nair"), None)
        assert p
        return p["id"]

    def test_simulate_levothyroxine_tsh_falls(self, auth_headers, priya_id):
        r = requests.post(f"{API}/simulate", headers=auth_headers,
                          json={"patient_id": priya_id, "drug_id": "levothyroxine",
                                "dose": 75, "threshold": "standard"}, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["system"] == "endocrine"
        assert d["target"] == "tsh"
        assert d["x_label"] == "days"
        assert d["series"] and len(d["series"]) > 5
        # TSH must fall from ~8.7
        assert d["series"][0]["treated"] >= d["series"][-1]["treated"]
        assert d["series"][-1]["treated"] < 8.7

    def test_optimise_levothyroxine_hits_band(self, auth_headers, priya_id):
        r = requests.post(f"{API}/optimise", headers=auth_headers,
                          json={"patient_id": priya_id, "drug_id": "levothyroxine",
                                "threshold": "standard"}, timeout=60)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["drug"]["id"] == "levothyroxine"
        lo, hi = d["band"]
        # expected ~75 mcg → TSH ~3.3 within [0.4, 4.0]
        assert lo <= d["predicted_value"] <= hi, \
            f"predicted TSH {d['predicted_value']} not in band {d['band']}"
        assert d["achieves_target"] is True
        assert d["trajectory"]["system"] == "endocrine"


# ---------------- Trial history persistence ----------------
class TestTrialHistory:
    def test_run_persists_and_list_and_detail(self, auth_headers):
        # run a small trial
        r = requests.post(f"{API}/trial/run", headers=auth_headers,
                          json={"drug_id": "metformin", "cohort_size": 20, "seed": 11},
                          timeout=90)
        assert r.status_code == 200, r.text
        run = r.json()
        assert "id" in run and run["id"]
        trial_id = run["id"]

        # list is lightweight (no twins/dose_summary)
        r_list = requests.get(f"{API}/trials", headers=auth_headers, timeout=15)
        assert r_list.status_code == 200
        rows = r_list.json()
        assert isinstance(rows, list) and len(rows) >= 1
        this_row = next((x for x in rows if x["id"] == trial_id), None)
        assert this_row is not None, "just-run trial should appear in /api/trials list"
        assert "twins" not in this_row, "list must exclude 'twins' (lightweight)"
        assert "dose_summary" not in this_row, "list must exclude 'dose_summary'"
        assert this_row["drug"]["id"] == "metformin"
        assert this_row["cohort_size"] == 20
        assert "best_dose" in this_row and this_row["best_dose"]["dose"]

        # newest-first ordering
        if len(rows) >= 2:
            assert rows[0]["created_at"] >= rows[1]["created_at"]

        # detail returns full doc with twins + dose_summary
        r_det = requests.get(f"{API}/trials/{trial_id}", headers=auth_headers, timeout=15)
        assert r_det.status_code == 200
        det = r_det.json()
        assert det["id"] == trial_id
        assert "twins" in det and len(det["twins"]) == 20
        assert "dose_summary" in det and len(det["dose_summary"]) >= 1
        assert "summary" in det and isinstance(det["summary"], str)

    def test_trial_detail_not_found(self, auth_headers):
        r = requests.get(f"{API}/trials/does-not-exist", headers=auth_headers, timeout=10)
        assert r.status_code == 404

    def test_trials_list_requires_auth(self):
        r = requests.get(f"{API}/trials", timeout=10)
        assert r.status_code == 401
