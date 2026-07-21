from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import os
import uuid
import logging
from datetime import datetime, timezone, timedelta

import jwt
import bcrypt
from fastapi import FastAPI, APIRouter, HTTPException, Request, Response, Depends
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
def build_trajectory(patient, drug, dose, threshold, meal_carbs):
    twin = catalog.derive_twin_params(patient["parameters"], patient.get("weight_kg", 70))
    target = drug["target_param"]
    p = catalog.PARAMETERS[target]
    band = p.get(threshold, p["standard"])

    if drug["system"] == "metabolic":
        base = twin_engine.simulate_glucose(
            weight_kg=twin["weight_kg"], basal_glucose=twin["basal_glucose"],
            basal_insulin=twin["basal_insulin"], si_factor=twin["si_factor"],
            beta_factor=twin["beta_factor"], meal_carbs_g=meal_carbs)
        offset, si_boost = catalog.metformin_metabolic_effect(dose)
        treated = twin_engine.simulate_glucose(
            weight_kg=twin["weight_kg"], basal_glucose=twin["basal_glucose"],
            basal_insulin=twin["basal_insulin"], si_factor=twin["si_factor"],
            beta_factor=twin["beta_factor"], meal_carbs_g=meal_carbs,
            glucose_offset=offset, si_boost=si_boost)
        series = [{"t": base["times"][i], "baseline": base["glucose"][i],
                   "treated": treated["glucose"][i],
                   "insulin_base": base["insulin"][i], "insulin_treated": treated["insulin"][i]}
                  for i in range(len(base["times"]))]
        predicted = round(twin["basal_glucose"] + offset, 1)
        return {
            "system": "metabolic", "target": target, "target_label": p["label"],
            "unit": p["unit"], "band": band, "x_label": "minutes", "x_unit": "min",
            "series": series, "baseline_value": twin["basal_glucose"],
            "predicted_value": predicted, "peak_baseline": base["peak_glucose"],
            "peak_treated": treated["peak_glucose"], "two_hour_treated": treated["two_hour_glucose"],
        }

    # delta model: approach new steady state
    current = float(patient["parameters"].get(target, band[0]))
    predicted = catalog.predict_param_after_drug(current, drug, dose)
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
    current = float(patient["parameters"].get(target, hi))

    # search dose space for smallest dose bringing predicted value into band
    doses, best = [], None
    d = drug["min_dose"]
    while d <= drug["max_dose"] + 1e-6:
        doses.append(round(d, 3))
        d += drug["step"]
    for dose in doses:
        predicted = catalog.predict_param_after_drug(current, drug, dose)
        in_band = lo <= predicted <= hi
        if in_band and best is None:
            best = {"dose": dose, "predicted": round(predicted, 2)}
    exceeds_max = False
    if best is None:
        # not achievable within max_dose -> report best effort at max_dose
        predicted = catalog.predict_param_after_drug(current, drug, drug["max_dose"])
        best = {"dose": drug["max_dose"], "predicted": round(predicted, 2)}
        exceeds_max = not (lo <= predicted <= hi)

    # confidence: how far into band + within recommended range
    margin = 0.0
    if hi > lo:
        centred = 1.0 - abs((best["predicted"] - (lo + hi) / 2) / ((hi - lo) / 2))
        margin = max(0.0, min(1.0, centred))
    dose_penalty = 0.15 if best["dose"] >= drug["max_dose"] else 0.0
    confidence = round(max(0.35, min(0.95, 0.55 + 0.4 * margin - dose_penalty)), 2)
    if exceeds_max:
        confidence = round(min(confidence, 0.45), 2)

    trajectory = build_trajectory(patient, drug, best["dose"], body.threshold, 60)
    rationale = await llm_service.dose_rationale(
        patient["name"], drug, best["dose"], p["label"], round(current, 2),
        best["predicted"], f"[{lo}–{hi}] {p['unit']}", confidence, f"opt-{body.patient_id}")

    return {
        "drug": {"id": drug["id"], "name": drug["name"], "unit": drug["unit"],
                 "max_safe": drug["max_safe"], "side_effects": drug["side_effects"],
                 "contraindications": drug["contraindications"]},
        "target": target, "target_label": p["label"], "unit": p["unit"], "band": band,
        "baseline_value": round(current, 2), "recommended_dose": best["dose"],
        "predicted_value": best["predicted"], "achieves_target": not exceeds_max,
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
    # seed synthetic patients
    if await db.patients.count_documents({}) == 0:
        for pt in catalog.seed_patients():
            pt["twin"] = catalog.derive_twin_params(pt["parameters"], pt.get("weight_kg", 70))
            pt["created_at"] = datetime.now(timezone.utc).isoformat()
            await db.patients.insert_one({**pt})
        logger.info("Seeded synthetic patients")


@app.on_event("shutdown")
async def shutdown():
    client.close()
