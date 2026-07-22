"""Validated reference tables, disease/drug catalogs and synthetic seed patients.

These tables GATE what the twin can map: a parameter is only simulated if it
appears in PARAMETERS with a cited-style reference band.
"""
import math
import random
import uuid

import twin_engine

# ---------------------------------------------------------------------------
# Reference ranges (standard adult + South-Asian tighter metabolic thresholds)
# ---------------------------------------------------------------------------
PARAMETERS = {
    "fasting_glucose": {"label": "Fasting Glucose", "unit": "mg/dL", "organ": "pancreas",
                        "standard": [70, 99], "south_asian": [70, 90], "decimals": 0},
    "hba1c": {"label": "HbA1c", "unit": "%", "organ": "pancreas",
              "standard": [4.0, 5.6], "south_asian": [4.0, 5.4], "decimals": 1},
    "systolic_bp": {"label": "Systolic BP", "unit": "mmHg", "organ": "heart",
                    "standard": [90, 120], "south_asian": [90, 120], "decimals": 0},
    "diastolic_bp": {"label": "Diastolic BP", "unit": "mmHg", "organ": "heart",
                     "standard": [60, 80], "south_asian": [60, 80], "decimals": 0},
    "heart_rate": {"label": "Heart Rate", "unit": "bpm", "organ": "heart",
                   "standard": [60, 100], "south_asian": [60, 100], "decimals": 0},
    "spo2": {"label": "SpO₂", "unit": "%", "organ": "lungs",
             "standard": [95, 100], "south_asian": [95, 100], "decimals": 0},
    "hemoglobin": {"label": "Hemoglobin", "unit": "g/dL", "organ": "blood",
                   "standard": [12.0, 16.0], "south_asian": [12.0, 16.0], "decimals": 1},
    "tsh": {"label": "TSH", "unit": "mIU/L", "organ": "thyroid",
            "standard": [0.4, 4.0], "south_asian": [0.4, 4.0], "decimals": 2},
    "ldl": {"label": "LDL Cholesterol", "unit": "mg/dL", "organ": "liver",
            "standard": [0, 100], "south_asian": [0, 100], "decimals": 0},
}

# Organ -> body region mapping for the 3D twin
ORGANS = {
    "pancreas": {"label": "Pancreas", "region": "abdomen"},
    "heart": {"label": "Heart", "region": "thorax"},
    "lungs": {"label": "Lungs", "region": "thorax"},
    "liver": {"label": "Liver", "region": "abdomen"},
    "kidneys": {"label": "Kidneys", "region": "abdomen"},
    "thyroid": {"label": "Thyroid", "region": "head"},
    "brain": {"label": "Brain", "region": "head"},
    "blood": {"label": "Bone Marrow / Blood", "region": "pelvis"},
}

# ---------------------------------------------------------------------------
# Disease catalog (organ region + directional parameter effects)
# ---------------------------------------------------------------------------
DISEASES = [
    {"id": "t2dm", "name": "Type 2 Diabetes", "organ": "pancreas", "region": "abdomen",
     "system": "metabolic",
     "effects": {"fasting_glucose": "up", "hba1c": "up"},
     "twin": {"si_factor": 0.35, "beta_factor": 0.45},
     "note": "Reduced insulin sensitivity and blunted β-cell response."},
    {"id": "htn", "name": "Hypertension", "organ": "heart", "region": "thorax",
     "system": "cardiovascular",
     "effects": {"systolic_bp": "up", "diastolic_bp": "up"},
     "note": "Elevated arterial pressure; cardiovascular strain."},
    {"id": "ida", "name": "Iron-deficiency Anaemia", "organ": "blood", "region": "pelvis",
     "system": "hematologic",
     "effects": {"hemoglobin": "down"},
     "note": "Low hemoglobin from depleted iron stores."},
    {"id": "hypothyroid", "name": "Hypothyroidism", "organ": "thyroid", "region": "head",
     "system": "endocrine",
     "effects": {"tsh": "up", "heart_rate": "down"},
     "note": "Under-active thyroid; elevated TSH, bradycardia."},
    {"id": "copd", "name": "COPD", "organ": "lungs", "region": "thorax",
     "system": "respiratory",
     "effects": {"spo2": "down", "heart_rate": "up"},
     "note": "Chronic airflow limitation; hypoxaemia."},
]
DISEASE_BY_ID = {d["id"]: d for d in DISEASES}

# ---------------------------------------------------------------------------
# Drug catalog (directional effects, dose space, safety constraints)
# ---------------------------------------------------------------------------
DRUGS = [
    {"id": "metformin", "name": "Metformin", "treats": "t2dm", "system": "metabolic",
     "target_param": "fasting_glucose", "unit": "mg/day", "line": "first",
     "combine_with": "empagliflozin",
     "min_dose": 500, "max_dose": 2000, "step": 250, "max_safe": 2550,
     "response_days": None,
     "side_effects": "GI upset & lactic-acidosis risk rise above 2000 mg/day.",
     "contraindications": "eGFR < 30 mL/min."},
    {"id": "empagliflozin", "name": "Empagliflozin", "treats": "t2dm", "system": "metabolic",
     "target_param": "fasting_glucose", "unit": "mg/day", "line": "second",
     "min_dose": 10, "max_dose": 25, "step": 5, "max_safe": 25,
     "response_days": None, "glucose_drop_max": 38,
     "side_effects": "Genital mycotic infections; volume depletion; euglycaemic DKA (rare).",
     "contraindications": "eGFR < 30 mL/min; type 1 diabetes."},
    {"id": "lisinopril", "name": "Lisinopril", "treats": "htn", "system": "cardiovascular",
     "target_param": "systolic_bp", "unit": "mg/day", "line": "first",
     "combine_with": "amlodipine", "ec50": 2.5, "imax": 0.20,
     "min_dose": 5, "max_dose": 40, "step": 5, "max_safe": 80,
     "response_days": 28,
     "side_effects": "Dry cough; hyperkalaemia and hypotension at high dose.",
     "contraindications": "Pregnancy; bilateral renal artery stenosis."},
    {"id": "amlodipine", "name": "Amlodipine", "treats": "htn", "system": "cardiovascular",
     "target_param": "systolic_bp", "unit": "mg/day", "line": "second",
     "ec50": 1.2, "imax": 0.16,
     "min_dose": 2.5, "max_dose": 10, "step": 2.5, "max_safe": 10,
     "response_days": 28,
     "side_effects": "Peripheral oedema; flushing; reflex tachycardia.",
     "contraindications": "Severe aortic stenosis; cardiogenic shock."},
    {"id": "ferrous_sulfate", "name": "Ferrous Sulfate", "treats": "ida", "system": "hematologic",
     "target_param": "hemoglobin", "unit": "mg/day", "line": "first",
     "min_dose": 65, "max_dose": 195, "step": 65, "max_safe": 260,
     "response_days": 56,
     "side_effects": "Constipation and nausea at higher elemental-iron doses.",
     "contraindications": "Haemochromatosis; active GI bleed."},
    {"id": "levothyroxine", "name": "Levothyroxine", "treats": "hypothyroid", "system": "endocrine",
     "target_param": "tsh", "unit": "mcg/day", "line": "first",
     "min_dose": 25, "max_dose": 150, "step": 25, "max_safe": 200,
     "response_days": 42,
     "side_effects": "Over-replacement causes palpitations, tremor, bone loss.",
     "contraindications": "Untreated adrenal insufficiency; acute MI."},
    {"id": "salbutamol", "name": "Salbutamol", "treats": "copd", "system": "respiratory",
     "target_param": "spo2", "unit": "mcg", "line": "first", "ic50": 90,
     "min_dose": 100, "max_dose": 400, "step": 100, "max_safe": 800,
     "response_days": 1,
     "side_effects": "Tachycardia and tremor with cumulative dosing.",
     "contraindications": "Severe tachyarrhythmia."},
]
DRUG_BY_ID = {d["id"]: d for d in DRUGS}


def drug_dose_fraction(drug, dose):
    return max(0.0, min(1.0, dose / drug["max_dose"]))


def metformin_metabolic_effect(dose):
    """Return (glucose_offset mg/dL, si_boost x) for a metformin dose."""
    frac = drug_dose_fraction(DRUG_BY_ID["metformin"], dose)
    return (-32.0 * frac, 1.0 + 0.65 * frac)


def empagliflozin_effect(dose):
    """SGLT2 inhibitor: insulin-independent fasting-glucose offset (renal excretion)."""
    frac = drug_dose_fraction(DRUG_BY_ID["empagliflozin"], dose)
    return -DRUG_BY_ID["empagliflozin"]["glucose_drop_max"] * frac


def predict_param_after_drug(params, drug, dose):
    """Predicted new steady-state / peak of the drug's target parameter.

    Numbers come from the mechanistic engine where one exists (glucose,
    blood pressure, SpO2); delta model otherwise.
    """
    did = drug["id"]
    if did == "metformin":
        offset, _ = metformin_metabolic_effect(dose)
        return float(params.get("fasting_glucose", 100)) + offset
    if did == "empagliflozin":
        return float(params.get("fasting_glucose", 100)) + empagliflozin_effect(dose)
    if drug["system"] == "cardiovascular":
        sys0 = float(params.get("systolic_bp", 150))
        dia0 = float(params.get("diastolic_bp", 92))
        cv = twin_engine.simulate_cardiovascular(
            systolic0=sys0, diastolic0=dia0,
            agents=[{"ec50": drug["ec50"], "dose": dose, "imax": drug["imax"]}])
        return cv["final_systolic"]
    if drug["system"] == "respiratory":
        rp = twin_engine.simulate_respiratory(
            spo2_0=float(params.get("spo2", 92)),
            heart_rate0=float(params.get("heart_rate", 80)),
            drug_ic50=drug["ic50"], dose=dose)
        return rp["peak_spo2"]
    # mechanistic hematologic / endocrine
    if did == "ferrous_sulfate":
        return twin_engine.simulate_hematologic(
            hb0=float(params.get("hemoglobin", 11)), dose=dose)["final_hemoglobin"]
    if did == "levothyroxine":
        return twin_engine.simulate_endocrine(
            tsh0=float(params.get("tsh", 6)), dose=dose)["final_tsh"]
    return float(params.get(drug["target_param"], 0))


def predict_combination(params, primary, pdose, secondary, sdose):
    """Predicted target value when a second agent is added to the primary."""
    if primary["system"] == "metabolic":
        base = float(params.get("fasting_glucose", 100))
        off_p, _ = metformin_metabolic_effect(pdose)
        off_s = empagliflozin_effect(sdose)
        return base + off_p + off_s
    if primary["system"] == "cardiovascular":
        sys0 = float(params.get("systolic_bp", 150))
        dia0 = float(params.get("diastolic_bp", 92))
        cv = twin_engine.simulate_cardiovascular(
            systolic0=sys0, diastolic0=dia0,
            agents=[{"ec50": primary["ec50"], "dose": pdose, "imax": primary["imax"]},
                    {"ec50": secondary["ec50"], "dose": sdose, "imax": secondary["imax"]}])
        return cv["final_systolic"]
    return predict_param_after_drug(params, primary, pdose)


# ---------------------------------------------------------------------------
# Virtual-trial cohort generation + response classification
# ---------------------------------------------------------------------------
def generate_cohort(drug, size, seed=None):
    """Generate `size` synthetic twins with an out-of-range baseline for the
    drug's target parameter, varied physiology and per-twin drug susceptibility."""
    rng = random.Random(seed)
    tgt = drug["target_param"]
    cohort = []
    for i in range(size):
        base = {
            "fasting_glucose": 90, "hba1c": 5.2, "systolic_bp": 118, "diastolic_bp": 76,
            "heart_rate": 74, "spo2": 98, "hemoglobin": 13.5, "tsh": 2.0, "ldl": 95,
        }
        if tgt == "fasting_glucose":
            fg = max(105, min(230, rng.gauss(158, 26)))
            base["fasting_glucose"] = round(fg, 0)
            base["hba1c"] = round(5.5 + (fg - 100) / 30.0, 1)
        elif tgt == "systolic_bp":
            base["systolic_bp"] = round(max(135, min(185, rng.gauss(156, 11))), 0)
            base["diastolic_bp"] = round(max(85, min(110, rng.gauss(95, 7))), 0)
        elif tgt == "spo2":
            base["spo2"] = round(max(85, min(93, rng.gauss(90, 2.0))), 0)
            base["heart_rate"] = round(max(75, min(105, rng.gauss(90, 6))), 0)
        elif tgt == "hemoglobin":
            base["hemoglobin"] = round(max(7.0, min(11.5, rng.gauss(9.6, 1.0))), 1)
        elif tgt == "tsh":
            base["tsh"] = round(max(5.5, min(15, rng.gauss(8.5, 2.0))), 1)
        cohort.append({
            "id": i + 1,
            "parameters": base,
            "susceptibility": round(rng.gauss(1.0, 0.18), 3),  # side-effect tolerance
            "weight_kg": round(max(48, min(105, rng.gauss(72, 12))), 0),
        })
    return cohort


def side_effect_flag(drug, dose, predicted, susceptibility):
    """Per-twin side-effect flag from dose intensity + overshoot, scaled by tolerance."""
    frac = drug_dose_fraction(drug, dose)
    thresh = 0.72 * susceptibility          # high-dose intolerance threshold
    if frac > thresh:
        return True
    if drug["target_param"] == "systolic_bp" and predicted < 108 - (susceptibility - 1) * 6:
        return True                          # hypotension overshoot
    if drug["target_param"] == "spo2" and frac > 0.6 * susceptibility:
        return True                          # tachycardia at cumulative dosing
    return False


# ---------------------------------------------------------------------------
# Twin initialisation: derive patient-specific metabolic parameters from labs
# ---------------------------------------------------------------------------
def derive_twin_params(parameters, weight_kg=70.0):
    fg = float(parameters.get("fasting_glucose", 90))
    a1c = float(parameters.get("hba1c", 5.2))
    si = max(0.25, min(1.1, 1.35 - (fg - 85.0) / 120.0))
    beta = max(0.35, min(1.1, 1.25 - (a1c - 5.0) / 6.0))
    return {
        "si_factor": round(si, 3),
        "beta_factor": round(beta, 3),
        "basal_glucose": fg,
        "basal_insulin": round(9.0 + max(0.0, (a1c - 5.0)) * 2.0, 1),
        "weight_kg": weight_kg,
    }


def in_range(param_key, value, threshold="standard"):
    p = PARAMETERS.get(param_key)
    if not p:
        return True, None
    lo, hi = p.get(threshold, p["standard"])
    if value < lo:
        return False, "low"
    if value > hi:
        return False, "high"
    return True, None


def rule_based_disease_scan(parameters, threshold="standard"):
    """Flag likely conditions when the patient's directional deviations match a disease."""
    flags = []
    for dis in DISEASES:
        evidence, matched = [], 0
        for pkey, direction in dis["effects"].items():
            if pkey not in parameters:
                continue
            ok, side = in_range(pkey, float(parameters[pkey]), threshold)
            want = "high" if direction == "up" else "low"
            if not ok and side == want:
                matched += 1
                p = PARAMETERS[pkey]
                evidence.append(f"{p['label']} {parameters[pkey]}{p['unit']} is {side}")
        if matched:
            confidence = round(min(0.95, 0.45 + 0.25 * matched), 2)
            flags.append({
                "disease_id": dis["id"], "name": dis["name"], "organ": dis["organ"],
                "region": dis["region"], "confidence": confidence, "evidence": evidence,
            })
    flags.sort(key=lambda f: f["confidence"], reverse=True)
    return flags


# ---------------------------------------------------------------------------
# Synthetic seed patients (NO real PHI)
# ---------------------------------------------------------------------------
def seed_patients():
    return [
        {
            "id": str(uuid.uuid4()),
            "name": "Anaya Sharma", "age": 52, "sex": "female",
            "ethnicity": "south_asian", "weight_kg": 74, "height_cm": 160,
            "history": "10-year history of impaired glucose tolerance. Family history of T2DM. Sedentary.",
            "medications": ["None"],
            "conditions": ["t2dm"],
            "parameters": {
                "fasting_glucose": 158, "hba1c": 8.1, "systolic_bp": 138,
                "diastolic_bp": 86, "heart_rate": 78, "spo2": 98,
                "hemoglobin": 12.6, "tsh": 2.1, "ldl": 128,
            },
            "seed": True,
        },
        {
            "id": str(uuid.uuid4()),
            "name": "Marcus Bell", "age": 61, "sex": "male",
            "ethnicity": "other", "weight_kg": 92, "height_cm": 178,
            "history": "Long-standing hypertension. Ex-smoker (30 pack-years). Exertional breathlessness.",
            "medications": ["Amlodipine 5mg"],
            "conditions": ["htn", "copd"],
            "parameters": {
                "fasting_glucose": 104, "hba1c": 5.9, "systolic_bp": 156,
                "diastolic_bp": 96, "heart_rate": 92, "spo2": 91,
                "hemoglobin": 14.8, "tsh": 1.8, "ldl": 142,
            },
            "seed": True,
        },
        {
            "id": str(uuid.uuid4()),
            "name": "Priya Nair", "age": 34, "sex": "female",
            "ethnicity": "south_asian", "weight_kg": 58, "height_cm": 158,
            "history": "Fatigue and menorrhagia. Recent weight gain and cold intolerance.",
            "medications": ["None"],
            "conditions": ["ida", "hypothyroid"],
            "parameters": {
                "fasting_glucose": 88, "hba1c": 5.1, "systolic_bp": 112,
                "diastolic_bp": 72, "heart_rate": 58, "spo2": 99,
                "hemoglobin": 9.4, "tsh": 8.7, "ldl": 96,
            },
            "seed": True,
        },
    ]
