from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import os
import uuid
import json
import random
import asyncio
import logging
from datetime import datetime, timezone, timedelta

import jwt
import bcrypt
from fastapi import FastAPI, APIRouter, HTTPException, Request, Response, Depends
from fastapi.responses import StreamingResponse
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional, Dict, Any

import catalog
import twin_engine
import llm_service

# --------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

JWT_ALGORITHM = "HS256"


def get_jwt_secret():
    return os.environ["JWT_SECRET"]


def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def verify_password(pw: str, hashed: str) -> bool:
    return bcrypt.checkpw(pw.encode(), hashed.encode())


def create_access_token(uid, email):
    payload = {"sub": uid, "email": email, "type": "access",
               "exp": datetime.now(timezone.utc) + timedelta(hours=12)}
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)


def create_refresh_token(uid):
    payload = {"sub": uid, "type": "refresh",
               "exp": datetime.now(timezone.utc) + timedelta(days=7)}
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)


def set_auth_cookies(resp: Response, access, refresh):
    resp.set_cookie("access_token", access, httponly=True, secure=False,
                    samesite="lax", max_age=43200, path="/")
    resp.set_cookie("refresh_token", refresh, httponly=True, secure=False,
                    samesite="lax", max_age=604800, path="/")


async def get_current_user(request: Request) -> dict:
    token = request.cookies.get("access_token")
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0, "password_hash": 0})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


# --------------------------------------------------------------------------
# Models
# --------------------------------------------------------------------------
class RegisterInput(BaseModel):
    email: EmailStr
    password: str
    name: str


class LoginInput(BaseModel):
    email: EmailStr
    password: str


class PatientInput(BaseModel):
    name: str
    age: int
    sex: str
    ethnicity: str = "other"
    weight_kg: float = 70
    height_cm: float = 170
    history: str = ""
    medications: List[str] = []
    conditions: List[str] = []
    parameters: Dict[str, float] = {}


class SimulateInput(BaseModel):
    patient_id: str
    drug_id: str
    dose: float
    threshold: str = "standard"
    meal_carbs_g: float = 60


class OptimiseInput(BaseModel):
    patient_id: str
    drug_id: str
    threshold: str = "standard"


class SaveCaseInput(BaseModel):
    patient_id: str
    payload: Dict[str, Any]


class TrialInput(BaseModel):
    drug_id: str
    cohort_size: int = 60
    threshold: str = "standard"
    seed: Optional[int] = 42


# --------------------------------------------------------------------------
app = FastAPI()
api = APIRouter(prefix="/api")


@api.get("/")
async def root():
    return {"message": "TwinMed API", "status": "ok"}


# ---------------- Auth ----------------
@api.post("/auth/register")
async def register(body: RegisterInput, response: Response):
    email = body.email.lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="Email already registered")
    uid = str(uuid.uuid4())
    doc = {"id": uid, "email": email, "name": body.name, "role": "doctor",
           "password_hash": hash_password(body.password),
           "created_at": datetime.now(timezone.utc).isoformat()}
    await db.users.insert_one(doc)
    access, refresh = create_access_token(uid, email), create_refresh_token(uid)
    set_auth_cookies(response, access, refresh)
    return {"id": uid, "email": email, "name": body.name, "role": "doctor", "token": access}


@api.post("/auth/login")
async def login(body: LoginInput, response: Response):
    email = body.email.lower()
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    access, refresh = create_access_token(user["id"], email), create_refresh_token(user["id"])
    set_auth_cookies(response, access, refresh)
    return {"id": user["id"], "email": email, "name": user["name"],
            "role": user.get("role", "doctor"), "token": access}


@api.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
    return {"ok": True}


@api.get("/auth/me")
async def me(user: dict = Depends(get_current_user)):
    return user


# ---------------- Catalog ----------------
@api.get("/catalog")
async def get_catalog(user: dict = Depends(get_current_user)):
    return {
        "parameters": catalog.PARAMETERS,
        "organs": catalog.ORGANS,
        "diseases": catalog.DISEASES,
        "drugs": catalog.DRUGS,
    }


# ---------------- Patients ----------------
@api.get("/patients")
async def list_patients(user: dict = Depends(get_current_user)):
    docs = await db.patients.find({}, {"_id": 0}).to_list(500)
    return docs


@api.post("/patients")
async def create_patient(body: PatientInput, user: dict = Depends(get_current_user)):
    doc = body.model_dump()
    doc["id"] = str(uuid.uuid4())
    doc["seed"] = False
    doc["created_at"] = datetime.now(timezone.utc).isoformat()
    doc["twin"] = catalog.derive_twin_params(doc["parameters"], doc.get("weight_kg", 70))
    await db.patients.insert_one({**doc})
    doc.pop("_id", None)
    return doc


@api.get("/patients/{pid}")
async def get_patient(pid: str, user: dict = Depends(get_current_user)):
    doc = await db.patients.find_one({"id": pid}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Patient not found")
    doc["twin"] = catalog.derive_twin_params(doc.get("parameters", {}), doc.get("weight_kg", 70))
    return doc


@api.put("/patients/{pid}")
async def update_patient(pid: str, body: PatientInput, user: dict = Depends(get_current_user)):
    doc = body.model_dump()
    doc["twin"] = catalog.derive_twin_params(doc["parameters"], doc.get("weight_kg", 70))
    res = await db.patients.update_one({"id": pid}, {"$set": doc})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Patient not found")
    updated = await db.patients.find_one({"id": pid}, {"_id": 0})
    return updated


@api.delete("/patients/{pid}")
async def delete_patient(pid: str, user: dict = Depends(get_current_user)):
    await db.patients.delete_one({"id": pid})
    return {"ok": True}


# ---------------- Analysis helpers ----------------
def analyse_patient(parameters, threshold):
    out = []
    for key, val in parameters.items():
        if key not in catalog.PARAMETERS:
            continue
        ok, side = catalog.in_range(key, float(val), threshold)
        p = catalog.PARAMETERS[key]
        lo, hi = p.get(threshold, p["standard"])
        out.append({
            "key": key, "label": p["label"], "unit": p["unit"], "organ": p["organ"],
            "value": float(val), "in_range": ok, "side": side, "low": lo, "high": hi,
        })
    return out


@api.post("/analyse")
async def analyse(body: Dict[str, Any], user: dict = Depends(get_current_user)):
    return {"analysis": analyse_patient(body.get("parameters", {}),
                                        body.get("threshold", "standard"))}


# ---------------- Disease scan ----------------
@api.post("/disease-scan")
async def disease_scan(body: Dict[str, Any], user: dict = Depends(get_current_user)):
    pid = body.get("patient_id")
    threshold = body.get("threshold", "standard")
    patient = await db.patients.find_one({"id": pid}, {"_id": 0})
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    flags = catalog.rule_based_disease_scan(patient["parameters"], threshold)
    summary = await llm_service.disease_scan_summary(patient["name"], flags, f"scan-{pid}")
    return {"flags": flags, "summary": summary}


# ---------------- Simulation (drug test on twin) ----------------
def build_trajectory(patient, drug, dose, threshold, meal_carbs, secondary=None, sdose=0):
    twin = catalog.derive_twin_params(patient["parameters"], patient.get("weight_kg", 70))
    params = patient["parameters"]
    target = drug["target_param"]
    p = catalog.PARAMETERS[target]
    band = p.get(threshold, p["standard"])

    if drug["system"] == "metabolic":
        base = twin_engine.simulate_glucose(
            weight_kg=twin["weight_kg"], basal_glucose=twin["basal_glucose"],
            basal_insulin=twin["basal_insulin"], si_factor=twin["si_factor"],
            beta_factor=twin["beta_factor"], meal_carbs_g=meal_carbs)
        if drug["id"] == "metformin":
            offset, si_boost = catalog.metformin_metabolic_effect(dose)
        else:  # empagliflozin
            offset, si_boost = catalog.empagliflozin_effect(dose), 1.0
        if secondary:  # combination adds the second agent's offset
            offset += (catalog.empagliflozin_effect(sdose) if secondary["id"] == "empagliflozin"
                       else catalog.metformin_metabolic_effect(sdose)[0])
        treated = twin_engine.simulate_glucose(
            weight_kg=twin["weight_kg"], basal_glucose=twin["basal_glucose"],
            basal_insulin=twin["basal_insulin"], si_factor=twin["si_factor"],
            beta_factor=twin["beta_factor"], meal_carbs_g=meal_carbs,
            glucose_offset=offset, si_boost=si_boost)
        series = [{"t": base["times"][i], "baseline": base["glucose"][i],
                   "treated": treated["glucose"][i]}
                  for i in range(len(base["times"]))]
        return {
            "system": "metabolic", "target": target, "target_label": p["label"],
            "unit": p["unit"], "band": band, "x_label": "minutes", "x_unit": "min",
            "series": series, "baseline_value": round(twin["basal_glucose"], 1),
            "predicted_value": round(twin["basal_glucose"] + offset, 1),
            "peak_baseline": base["peak_glucose"], "peak_treated": treated["peak_glucose"],
        }

    if drug["system"] == "cardiovascular":
        sys0 = float(params.get("systolic_bp", 150))
        dia0 = float(params.get("diastolic_bp", 92))
        agents = [{"ec50": drug["ec50"], "dose": dose, "imax": drug["imax"]}]
        if secondary:
            agents.append({"ec50": secondary["ec50"], "dose": sdose, "imax": secondary["imax"]})
        cv = twin_engine.simulate_cardiovascular(systolic0=sys0, diastolic0=dia0, agents=agents)
        step = max(1, len(cv["times"]) // 60)
        series = [{"t": cv["times"][i], "baseline": sys0, "treated": cv["systolic"][i],
                   "diastolic": cv["diastolic"][i]}
                  for i in range(0, len(cv["times"]), step)]
        return {
            "system": "cardiovascular", "target": target, "target_label": p["label"],
            "unit": p["unit"], "band": band, "x_label": "days", "x_unit": "d",
            "series": series, "baseline_value": round(sys0, 1),
            "predicted_value": cv["final_systolic"], "final_diastolic": cv["final_diastolic"],
        }

    if drug["system"] == "respiratory":
        rp = twin_engine.simulate_respiratory(
            spo2_0=float(params.get("spo2", 92)),
            heart_rate0=float(params.get("heart_rate", 80)),
            drug_ic50=drug["ic50"], dose=dose)
        step = max(1, len(rp["times"]) // 60)
        series = [{"t": rp["times"][i], "baseline": params.get("spo2", 92),
                   "treated": rp["spo2"][i], "heart_rate": rp["heart_rate"][i]}
                  for i in range(0, len(rp["times"]), step)]
        return {
            "system": "respiratory", "target": target, "target_label": p["label"],
            "unit": p["unit"], "band": band, "x_label": "minutes", "x_unit": "min",
            "series": series, "baseline_value": round(float(params.get("spo2", 92)), 1),
            "predicted_value": rp["peak_spo2"], "peak_heart_rate": rp["peak_heart_rate"],
        }

    if drug["system"] in ("hematologic", "endocrine"):
        if drug["id"] == "ferrous_sulfate":
            r = twin_engine.simulate_hematologic(
                hb0=float(params.get("hemoglobin", 11)), dose=dose)
            key = "hemoglobin"
        else:
            r = twin_engine.simulate_endocrine(
                tsh0=float(params.get("tsh", 6)), dose=dose)
            key = "tsh"
        base_val = float(params.get(target, band[0]))
        step = max(1, len(r["times"]) // 60)
        series = [{"t": r["times"][i], "baseline": round(base_val, 2),
                   "treated": r[key][i]} for i in range(0, len(r["times"]), step)]
        return {
            "system": drug["system"], "target": target, "target_label": p["label"],
            "unit": p["unit"], "band": band, "x_label": "days", "x_unit": "d",
            "series": series, "baseline_value": round(base_val, 2),
            "predicted_value": r[f"final_{key}"],
        }

    # delta model fallback
    current = float(params.get(target, band[0]))
    predicted = catalog.predict_param_after_drug(params, drug, dose)
    days = drug.get("response_days") or 14
    tau = days / 3.0
    n = 40
    series = []
    for i in range(n + 1):
        t = days * i / n
        val = current + (predicted - current) * (1 - pow(2.718281828, -t / tau))
        series.append({"t": round(t, 1), "baseline": round(current, 2),
                       "treated": round(val, 2)})
    return {
        "system": drug["system"], "target": target, "target_label": p["label"],
        "unit": p["unit"], "band": band, "x_label": "days", "x_unit": "d",
        "series": series, "baseline_value": round(current, 2),
        "predicted_value": round(predicted, 2),
    }


@api.post("/simulate")
async def simulate(body: SimulateInput, user: dict = Depends(get_current_user)):
    patient = await db.patients.find_one({"id": body.patient_id}, {"_id": 0})
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    drug = catalog.DRUG_BY_ID.get(body.drug_id)
    if not drug:
        raise HTTPException(status_code=404, detail="Drug not found")
    result = build_trajectory(patient, drug, body.dose, body.threshold, body.meal_carbs_g)
    result["drug"] = {"id": drug["id"], "name": drug["name"], "unit": drug["unit"],
                      "dose": body.dose, "side_effects": drug["side_effects"]}
    return result


# ---------------- Dose optimisation ----------------
@api.post("/optimise")
async def optimise(body: OptimiseInput, user: dict = Depends(get_current_user)):
    patient = await db.patients.find_one({"id": body.patient_id}, {"_id": 0})
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    drug = catalog.DRUG_BY_ID.get(body.drug_id)
    if not drug:
        raise HTTPException(status_code=404, detail="Drug not found")

    target = drug["target_param"]
    p = catalog.PARAMETERS[target]
    band = p.get(body.threshold, p["standard"])
    lo, hi = band
    params = patient["parameters"]
    current = float(params.get(target, hi))

    # search dose space for smallest dose bringing predicted value into band
    doses, best = [], None
    d = drug["min_dose"]
    while d <= drug["max_dose"] + 1e-6:
        doses.append(round(d, 3))
        d += drug["step"]
    for dose in doses:
        predicted = catalog.predict_param_after_drug(params, drug, dose)
        if lo <= predicted <= hi and best is None:
            best = {"dose": dose, "predicted": round(predicted, 2)}
    exceeds_max = False
    if best is None:
        predicted = catalog.predict_param_after_drug(params, drug, drug["max_dose"])
        best = {"dose": drug["max_dose"], "predicted": round(predicted, 2)}
        exceeds_max = not (lo <= predicted <= hi)

    # combination therapy: single agent can't reach target -> add second-line drug
    combination = None
    if exceeds_max and drug.get("combine_with"):
        secondary = catalog.DRUG_BY_ID.get(drug["combine_with"])
        sdoses = []
        sd = secondary["min_dose"]
        while sd <= secondary["max_dose"] + 1e-6:
            sdoses.append(round(sd, 3))
            sd += secondary["step"]
        combo_best = None
        for sdose in sdoses:
            pred = catalog.predict_combination(params, drug, drug["max_dose"], secondary, sdose)
            if lo <= pred <= hi and combo_best is None:
                combo_best = {"sdose": sdose, "predicted": round(pred, 2)}
        if combo_best is None:
            pred = catalog.predict_combination(params, drug, drug["max_dose"],
                                               secondary, secondary["max_dose"])
            combo_best = {"sdose": secondary["max_dose"], "predicted": round(pred, 2)}
        combo_reaches = lo <= combo_best["predicted"] <= hi
        combination = {
            "primary": {"id": drug["id"], "name": drug["name"], "unit": drug["unit"],
                        "dose": drug["max_dose"]},
            "secondary": {"id": secondary["id"], "name": secondary["name"],
                          "unit": secondary["unit"], "dose": combo_best["sdose"],
                          "side_effects": secondary["side_effects"]},
            "predicted_value": combo_best["predicted"], "achieves_target": combo_reaches,
        }

    # confidence
    ref_pred = combination["predicted_value"] if combination else best["predicted"]
    margin = 0.0
    if hi > lo:
        centred = 1.0 - abs((ref_pred - (lo + hi) / 2) / ((hi - lo) / 2))
        margin = max(0.0, min(1.0, centred))
    dose_penalty = 0.15 if best["dose"] >= drug["max_dose"] and not combination else 0.0
    achieves = (combination["achieves_target"] if combination else not exceeds_max)
    confidence = round(max(0.35, min(0.95, 0.55 + 0.4 * margin - dose_penalty)), 2)
    if not achieves:
        confidence = round(min(confidence, 0.45), 2)

    # trajectory: combination if present, else single
    if combination:
        secondary = catalog.DRUG_BY_ID[drug["combine_with"]]
        trajectory = build_trajectory(patient, drug, drug["max_dose"], body.threshold, 60,
                                      secondary=secondary, sdose=combination["secondary"]["dose"])
    else:
        trajectory = build_trajectory(patient, drug, best["dose"], body.threshold, 60)

    rationale = await llm_service.dose_rationale(
        patient["name"], drug, best["dose"], p["label"], round(current, 2),
        best["predicted"], f"[{lo}–{hi}] {p['unit']}", confidence, f"opt-{body.patient_id}",
        combination=combination)

    return {
        "drug": {"id": drug["id"], "name": drug["name"], "unit": drug["unit"],
                 "max_safe": drug["max_safe"], "side_effects": drug["side_effects"],
                 "contraindications": drug["contraindications"]},
        "target": target, "target_label": p["label"], "unit": p["unit"], "band": band,
        "baseline_value": round(current, 2), "recommended_dose": best["dose"],
        "predicted_value": best["predicted"], "achieves_target": achieves,
        "combination": combination,
        "confidence": confidence, "rationale": rationale, "trajectory": trajectory,
    }


# ---------------- Case summary ----------------
@api.post("/case-summary")
async def case_summary(body: Dict[str, Any], user: dict = Depends(get_current_user)):
    patient = await db.patients.find_one({"id": body.get("patient_id")}, {"_id": 0})
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    threshold = body.get("threshold", "standard")
    analysis = analyse_patient(patient["parameters"], threshold)
    oor = [f"{a['label']} {a['value']}{a['unit']} ({a['side']})" for a in analysis if not a["in_range"]]
    tried = body.get("tried", [])
    summary = await llm_service.case_summary(patient, oor, tried, f"sum-{patient['id']}")
    return {"summary": summary, "out_of_range": oor, "analysis": analysis}


# ---------------- Save case ----------------
@api.post("/save-case")
async def save_case(body: SaveCaseInput, user: dict = Depends(get_current_user)):
    doc = {"id": str(uuid.uuid4()), "patient_id": body.patient_id,
           "doctor_id": user["id"], "payload": body.payload,
           "created_at": datetime.now(timezone.utc).isoformat()}
    await db.cases.insert_one({**doc})
    doc.pop("_id", None)
    return doc


@api.get("/patients/{pid}/cases")
async def patient_cases(pid: str, user: dict = Depends(get_current_user)):
    docs = await db.cases.find({"patient_id": pid}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return docs


# ---------------- Virtual clinical trial (cohort of synthetic twins) ----------------
@api.post("/trial/run")
async def trial_run(body: TrialInput, user: dict = Depends(get_current_user)):
    drug = catalog.DRUG_BY_ID.get(body.drug_id)
    if not drug:
        raise HTTPException(status_code=404, detail="Drug not found")
    p = catalog.PARAMETERS[drug["target_param"]]
    band = p.get(body.threshold, p["standard"])
    lo, hi = band
    size = max(10, min(500, body.cohort_size))
    cohort = catalog.generate_cohort(drug, size, seed=body.seed)

    # dose sweep
    doses = []
    d = drug["min_dose"]
    while d <= drug["max_dose"] + 1e-6:
        doses.append(round(d, 3))
        d += drug["step"]

    def dist(v):
        return max(0.0, v - hi) + max(0.0, lo - v)

    dose_summary = []
    for dose in doses:
        in_range = 0
        side_fx = 0
        responders = 0
        preds = []
        for tw in cohort:
            base_val = tw["parameters"][drug["target_param"]]
            pred = catalog.predict_param_after_drug(tw["parameters"], drug, dose)
            preds.append(pred)
            if lo <= pred <= hi:
                in_range += 1
            d0 = dist(base_val)
            if d0 > 0 and (d0 - dist(pred)) / d0 >= 0.25:
                responders += 1
            if catalog.side_effect_flag(drug, dose, pred, tw["susceptibility"]):
                side_fx += 1
        dose_summary.append({
            "dose": dose,
            "pct_in_range": round(100 * in_range / size, 1),
            "pct_responder": round(100 * responders / size, 1),
            "pct_side_effect": round(100 * side_fx / size, 1),
            "mean_predicted": round(sum(preds) / size, 1),
        })

    # best population dose = balance efficacy (in-range + partial response) vs side-effects
    best = max(dose_summary,
               key=lambda x: x["pct_in_range"] + 0.5 * x["pct_responder"] - 0.7 * x["pct_side_effect"])

    # per-twin breakdown at best dose
    breakdown = {"improved": 0, "in_range": 0, "side_effect": 0, "no_change": 0}
    twins = []
    for tw in cohort:
        base_val = tw["parameters"][drug["target_param"]]
        pred = catalog.predict_param_after_drug(tw["parameters"], drug, best["dose"])
        inr = lo <= pred <= hi
        sfx = catalog.side_effect_flag(drug, best["dose"], pred, tw["susceptibility"])
        moved = abs(pred - base_val) > 0.02 * max(1, abs(base_val))
        if inr:
            breakdown["in_range"] += 1
        if sfx:
            breakdown["side_effect"] += 1
        if moved and not inr:
            breakdown["improved"] += 1
        if not moved:
            breakdown["no_change"] += 1
        twins.append({"id": tw["id"], "baseline": round(base_val, 1),
                      "predicted": round(pred, 1), "in_range": inr, "side_effect": sfx})

    summary_text = await llm_service.trial_summary(
        drug["name"], size, best, band, p["unit"], breakdown, f"trial-{body.drug_id}")

    result = {
        "id": str(uuid.uuid4()),
        "drug": {"id": drug["id"], "name": drug["name"], "unit": drug["unit"]},
        "target_label": p["label"], "unit": p["unit"], "band": band, "cohort_size": size,
        "threshold": body.threshold, "dose_summary": dose_summary, "best_dose": best,
        "breakdown": breakdown, "twins": twins, "summary": summary_text,
        "doctor_id": user["id"], "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.trials.insert_one({**result})
    result.pop("_id", None)
    return result


@api.get("/trials")
async def list_trials(user: dict = Depends(get_current_user)):
    docs = await db.trials.find(
        {}, {"_id": 0, "twins": 0, "dose_summary": 0}
    ).sort("created_at", -1).to_list(100)
    return docs


@api.get("/trials/{tid}")
async def get_trial(tid: str, user: dict = Depends(get_current_user)):
    doc = await db.trials.find_one({"id": tid}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Trial not found")
    return doc


# ---------------- Live sensor stream (SSE) ----------------
@api.get("/sensor/stream/{pid}")
async def sensor_stream(pid: str, seconds: int = 40):
    """Simulated wearable/sweat-sensor feed. Sweat glucose is NOT read directly;
    sensor signals (lactate, cortisol, HR) update the model which predicts glucose."""
    patient = await db.patients.find_one({"id": pid}, {"_id": 0})
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    twin = catalog.derive_twin_params(patient["parameters"], patient.get("weight_kg", 70))

    async def gen():
        import math as _m
        base_g = twin["basal_glucose"]
        hr0 = float(patient["parameters"].get("heart_rate", 74))
        spo20 = float(patient["parameters"].get("spo2", 98))
        for t in range(int(seconds) * 2):  # 0.5s cadence
            phase = t / 6.0
            lactate = round(1.2 + 0.4 * _m.sin(phase) + random.uniform(-0.1, 0.1), 2)
            cortisol = round(12 + 3 * _m.sin(phase / 3) + random.uniform(-0.6, 0.6), 1)
            sodium = round(38 + 2 * _m.sin(phase / 2) + random.uniform(-0.5, 0.5), 1)
            hr = round(hr0 + 6 * _m.sin(phase / 2) + random.uniform(-2, 2), 0)
            spo2 = round(min(100, spo20 + random.uniform(-0.6, 0.4)), 1)
            # model updates its glucose PREDICTION from sensor-driven parameters
            stress = (cortisol - 12) / 12.0
            pred_glucose = round(base_g + 18 * stress + 3 * (lactate - 1.2)
                                 + random.uniform(-2, 2), 1)
            payload = {
                "t": t * 0.5,
                "sensor": {"lactate": lactate, "cortisol": cortisol, "sodium": sodium,
                           "heart_rate": hr, "spo2": spo2},
                "model_glucose": pred_glucose,
            }
            yield f"data: {json.dumps(payload)}\n\n"
            await asyncio.sleep(0.5)
        yield f"data: {json.dumps({'done': True})}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=".*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    await db.users.create_index("email", unique=True)
    await db.patients.create_index("id", unique=True)
    # seed admin doctor
    admin_email = os.environ.get("ADMIN_EMAIL", "doctor@twinmed.app").lower()
    admin_password = os.environ.get("ADMIN_PASSWORD", "twinmed123")
    existing = await db.users.find_one({"email": admin_email})
    if existing is None:
        await db.users.insert_one({
            "id": str(uuid.uuid4()), "email": admin_email, "name": "Dr. Demo",
            "role": "doctor", "password_hash": hash_password(admin_password),
            "created_at": datetime.now(timezone.utc).isoformat()})
        logger.info(f"Seeded admin {admin_email}")
    elif not verify_password(admin_password, existing["password_hash"]):
        await db.users.update_one({"email": admin_email},
                                  {"$set": {"password_hash": hash_password(admin_password)}})
    # seed synthetic patients (per-name upsert so accidental deletions self-heal)
    for pt in catalog.seed_patients():
        if await db.patients.find_one({"name": pt["name"], "seed": True}):
            continue
        pt["twin"] = catalog.derive_twin_params(pt["parameters"], pt.get("weight_kg", 70))
        pt["created_at"] = datetime.now(timezone.utc).isoformat()
        await db.patients.insert_one({**pt})
        logger.info(f"Seeded synthetic patient {pt['name']}")


@app.on_event("shutdown")
async def shutdown():
    client.close()
