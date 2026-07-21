"""Validated reference tables, disease/drug catalogs and synthetic seed patients.

These tables GATE what the twin can map: a parameter is only simulated if it
appears in PARAMETERS with a cited-style reference band.
"""
import math
import uuid

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
     "target_param": "fasting_glucose", "unit": "mg/day",
     "min_dose": 500, "max_dose": 2000, "step": 250, "max_safe": 2550,
     "response_days": None,  # metabolic -> minute-scale meal response
     "side_effects": "GI upset & lactic-acidosis risk rise above 2000 mg/day.",
     "contraindications": "eGFR < 30 mL/min."},
    {"id": "lisinopril", "name": "Lisinopril", "treats": "htn", "system": "cardiovascular",
     "target_param": "systolic_bp", "unit": "mg/day",
     "min_dose": 5, "max_dose": 40, "step": 5, "max_safe": 80,
     "response_days": 14,
     "side_effects": "Dry cough; hyperkalaemia and hypotension at high dose.",
     "contraindications": "Pregnancy; bilateral renal artery stenosis."},
    {"id": "ferrous_sulfate", "name": "Ferrous Sulfate", "treats": "ida", "system": "hematologic",
     "target_param": "hemoglobin", "unit": "mg/day",
     "min_dose": 65, "max_dose": 195, "step": 65, "max_safe": 260,
     "response_days": 56,
     "side_effects": "Constipation and nausea at higher elemental-iron doses.",
     "contraindications": "Haemochromatosis; active GI bleed."},
    {"id": "levothyroxine", "name": "Levothyroxine", "treats": "hypothyroid", "system": "endocrine",
     "target_param": "tsh", "unit": "mcg/day",
     "min_dose": 25, "max_dose": 150, "step": 25, "max_safe": 200,
     "response_days": 42,
     "side_effects": "Over-replacement causes palpitations, tremor, bone loss.",
     "contraindications": "Untreated adrenal insufficiency; acute MI."},
    {"id": "salbutamol", "name": "Salbutamol", "treats": "copd", "system": "respiratory",
     "target_param": "spo2", "unit": "mcg",
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


def predict_param_after_drug(current_value, drug, dose):
    """Predicted new steady-state of the drug's target parameter (delta model)."""
    frac = drug_dose_fraction(drug, dose)
    did = drug["id"]
    if did == "metformin":
        offset, _ = metformin_metabolic_effect(dose)
        return current_value + offset
    if did == "lisinopril":
        return current_value - 28.0 * frac          # systolic drop up to ~28 mmHg
    if did == "ferrous_sulfate":
        return current_value + 4.5 * frac            # Hb rise up to ~4.5 g/dL
    if did == "levothyroxine":
        return max(0.2, current_value - (current_value - 1.5) * (0.85 * frac))
    if did == "salbutamol":
        return min(100.0, current_value + 7.0 * frac)  # SpO2 gain
    return current_value


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
