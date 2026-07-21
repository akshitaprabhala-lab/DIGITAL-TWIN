"""
TwinMed physiological simulation engine.

Tier 1: parameter-delta model (disease/drug directional shifts).
Tier 2: mechanistic glucose/insulin via the Bergman minimal model.

Model constants are FIXED. Only patient-specific parameters vary
(insulin sensitivity `si_factor`, beta-cell response `beta_factor`,
basal glucose/insulin set-points).
"""
import math


# ---------------------------------------------------------------------------
# Bergman minimal model (metabolic system)
#   dG/dt = -(p1 + X)*G + p1*Gb + Ra(t)
#   dX/dt = -p2*X + p3*(I - Ib)
#   dI/dt = -n*(I - Ib) + beta*(G - h)+
# ---------------------------------------------------------------------------

# Validated fixed constants (Bergman 1979 minimal model, typical adult scaling)
P1 = 0.025       # 1/min  glucose effectiveness
P2 = 0.025       # 1/min  remote insulin decay
P3 = 6.0e-6      # min^-2 per (mU/L) insulin action on glucose
N = 0.09         # 1/min  insulin clearance
BETA0 = 0.70     # (mU/L)/(mg/dL)/min pancreatic responsivity (healthy)
KABS = 0.02      # 1/min meal glucose absorption rate
VG_DL_PER_KG = 1.6   # dL/kg glucose distribution volume
CARB_BIOAVAIL = 0.85  # net fraction of meal carbs appearing in plasma


def _meal_ra(t, total_rise):
    """Gamma-shaped rate of glucose appearance (mg/dL/min). Integrates to total_rise."""
    return total_rise * (KABS ** 2) * t * math.exp(-KABS * t)


def simulate_glucose(
    *,
    weight_kg=70.0,
    basal_glucose=90.0,
    basal_insulin=11.0,
    si_factor=1.0,
    beta_factor=1.0,
    target_glucose=None,
    meal_carbs_g=60.0,
    duration_min=240,
    dt=1.0,
    insulin_bonus=0.0,
    glucose_offset=0.0,
    si_boost=1.0,
):
    """Integrate the Bergman minimal model after a meal.

    insulin_bonus / si_boost / glucose_offset let drug/disease deltas feed the
    mechanistic model (e.g. metformin lowers basal glucose + boosts sensitivity).
    Returns dict with time series and summary metrics.
    """
    Gb = basal_glucose + glucose_offset
    Ib = basal_insulin
    h = target_glucose if target_glucose is not None else Gb
    p3 = P3 * si_factor * si_boost
    beta = BETA0 * beta_factor

    vg = VG_DL_PER_KG * weight_kg
    total_rise = (meal_carbs_g * 1000.0 * CARB_BIOAVAIL) / vg  # mg/dL

    G = Gb
    X = 0.0
    I = Ib + insulin_bonus

    times, glucose, insulin = [], [], []
    steps = int(duration_min / dt)
    for i in range(steps + 1):
        t = i * dt
        times.append(round(t, 1))
        glucose.append(round(G, 1))
        insulin.append(round(I, 1))

        Ra = _meal_ra(t, total_rise)
        dG = -(P1 + X) * G + P1 * Gb + Ra
        dX = -P2 * X + p3 * (I - Ib)
        secretion = beta * max(G - h, 0.0)
        dI = -N * (I - Ib) + secretion

        G += dG * dt
        X += dX * dt
        I += dI * dt
        G = max(G, 20.0)
        I = max(I, 0.0)

    peak = max(glucose)
    peak_time = times[glucose.index(peak)]
    # time back within 140 mg/dL after peak
    settle_time = None
    peak_idx = glucose.index(peak)
    for j in range(peak_idx, len(glucose)):
        if glucose[j] <= 140:
            settle_time = times[j]
            break
    fasting = glucose[0]
    return {
        "times": times,
        "glucose": glucose,
        "insulin": insulin,
        "peak_glucose": round(peak, 1),
        "peak_time_min": peak_time,
        "settle_time_min": settle_time,
        "fasting_glucose": round(fasting, 1),
        "two_hour_glucose": glucose[min(120, len(glucose) - 1)],
    }


if __name__ == "__main__":
    healthy = simulate_glucose(si_factor=1.0, beta_factor=1.0, basal_glucose=90)
    t2d = simulate_glucose(si_factor=0.35, beta_factor=0.45, basal_glucose=135)
    t2d_metformin = simulate_glucose(
        si_factor=0.35, beta_factor=0.45, basal_glucose=135,
        si_boost=1.5, glucose_offset=-25,
    )
    print("HEALTHY  peak=%.0f @%.0fmin  settle=%s  2h=%.0f" % (
        healthy["peak_glucose"], healthy["peak_time_min"],
        healthy["settle_time_min"], healthy["two_hour_glucose"]))
    print("T2D      peak=%.0f @%.0fmin  settle=%s  2h=%.0f" % (
        t2d["peak_glucose"], t2d["peak_time_min"],
        t2d["settle_time_min"], t2d["two_hour_glucose"]))
    print("T2D+MET  peak=%.0f @%.0fmin  settle=%s  2h=%.0f" % (
        t2d_metformin["peak_glucose"], t2d_metformin["peak_time_min"],
        t2d_metformin["settle_time_min"], t2d_metformin["two_hour_glucose"]))
