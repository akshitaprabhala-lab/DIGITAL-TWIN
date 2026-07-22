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


# ---------------------------------------------------------------------------
# Cardiovascular mechanistic model (PK/PD) — blood pressure response
#   Daily oral dosing -> depot -> central plasma -> effect compartment ->
#   saturable (Emax) reduction of MAP -> systolic/diastolic tracking MAP.
# ---------------------------------------------------------------------------
CV_KA = 6.0        # 1/day  absorption
CV_KE = 1.2        # 1/day  plasma elimination
CV_KEO = 0.22      # 1/day  effect-site equilibration (slow -> weeks to full effect)
CV_IMAX = 0.20     # max fractional MAP reduction (ACE-inhibitor class ceiling)
CV_F = 0.25        # oral bioavailability
CV_KMAP = 3.0      # 1/day  MAP tracks its target


def simulate_cardiovascular(*, systolic0, diastolic0, agents,
                            duration_days=28, dt=0.02):
    """Integrate a PK/PD blood-pressure model for one or more once-daily agents.
    `agents` is a list of dicts: {ec50, dose, imax, keo?}. Effects sum (capped)
    so combination therapy produces additive MAP reduction.
    Returns systolic & diastolic time series (days) plus steady-state values.
    """
    st = [{"depot": 0.0, "Cp": 0.0, "Ce": 0.0,
           "ec50": a["ec50"], "dose": a["dose"], "imax": a.get("imax", CV_IMAX),
           "keo": a.get("keo", CV_KEO)} for a in agents if a["dose"] > 0]
    sys, dia = systolic0, diastolic0
    map0 = diastolic0 + (systolic0 - diastolic0) / 3.0
    pp = (systolic0 - diastolic0)
    times, syslist, dialist = [], [], []
    steps = int(duration_days / dt)
    last_day = -1
    for i in range(steps + 1):
        t = i * dt
        day = int(t)
        if day != last_day:
            for a in st:
                a["depot"] += a["dose"] * CV_F
            last_day = day
        times.append(round(t, 2))
        syslist.append(round(sys, 1))
        dialist.append(round(dia, 1))
        E = 0.0
        for a in st:
            a["depot"] += (-CV_KA * a["depot"]) * dt
            a["Cp"] += (CV_KA * a["depot"] - CV_KE * a["Cp"]) * dt
            a["Ce"] += (a["keo"] * (a["Cp"] - a["Ce"])) * dt
            E += a["imax"] * a["Ce"] / (a["ec50"] + a["Ce"])
        E = min(E, 0.36)                              # physiologic ceiling
        map_target = map0 * (1 - E)
        cur_map = dia + pp / 3.0
        cur_map += CV_KMAP * (map_target - cur_map) * dt
        dia = cur_map - pp / 3.0
        sys = dia + pp * (1 - 0.15 * E)
    return {
        "times": times, "systolic": syslist, "diastolic": dialist,
        "final_systolic": round(sys, 1), "final_diastolic": round(dia, 1),
    }


# ---------------------------------------------------------------------------
# Respiratory mechanistic model — SpO2 response to an inhaled bronchodilator
#   inhaled dose -> plasma -> effect site -> bronchodilation (Emax) ->
#   improved alveolar ventilation -> PaO2 -> SaO2 via O2-Hb dissociation (Hill).
# ---------------------------------------------------------------------------
RESP_KE = 0.0029   # 1/min  plasma decay (t1/2 ~ 4h)
RESP_KEO = 0.06    # 1/min  effect onset (~15-25 min)
RESP_IMAX = 1.0    # max bronchodilation fraction
RESP_HILL_N = 2.7  # O2-Hb dissociation Hill coefficient
RESP_P50 = 26.0    # mmHg  PaO2 at 50% SaO2
RESP_HR_MAX = 16   # bpm  max tachycardia side-effect at full effect


def _sao2_from_pao2(pao2):
    return 100.0 * (pao2 ** RESP_HILL_N) / (RESP_P50 ** RESP_HILL_N + pao2 ** RESP_HILL_N)


def simulate_respiratory(*, spo2_0, heart_rate0, drug_ic50, dose,
                         duration_min=360, dt=0.5, pao2_gain=22.0):
    """Integrate an inhaled-bronchodilator SpO2 model.
    Recovers baseline PaO2 from the patient's SpO2 via the dissociation curve,
    then raises ventilation/PaO2 with bronchodilation and re-derives SaO2.
    Returns SpO2 & heart-rate series (minutes) + peak SpO2.
    """
    # invert Hill to get baseline PaO2 from measured SpO2
    s = min(max(spo2_0, 50.0), 99.5) / 100.0
    pao2_base = RESP_P50 * (s / (1 - s)) ** (1.0 / RESP_HILL_N)
    Cp = float(dose)          # inhaled bolus (arbitrary units ~ mcg)
    Ce = 0.0
    spo2 = spo2_0
    hr = heart_rate0
    times, spo2list, hrlist = [], [], []
    steps = int(duration_min / dt)
    for i in range(steps + 1):
        t = i * dt
        times.append(round(t, 1))
        spo2list.append(round(spo2, 1))
        hrlist.append(round(hr, 1))
        Cp += (-RESP_KE * Cp) * dt
        Ce += (RESP_KEO * (Cp - Ce)) * dt
        B = RESP_IMAX * Ce / (drug_ic50 + Ce)
        pao2 = pao2_base + pao2_gain * B
        spo2_target = min(_sao2_from_pao2(pao2), 99.0)
        spo2 += 0.15 * (spo2_target - spo2)
        hr_target = heart_rate0 + RESP_HR_MAX * B
        hr += 0.12 * (hr_target - hr)
    peak = max(spo2list)
    return {
        "times": times, "spo2": spo2list, "heart_rate": hrlist,
        "peak_spo2": round(peak, 1), "final_spo2": round(spo2list[-1], 1),
        "peak_heart_rate": round(max(hrlist), 1),
    }


HEM_ABS = 0.11         # fraction of oral elemental iron absorbed (net)
HEM_KSYN = 0.20        # g/dL/day max marrow Hb synthesis capacity
HEM_KDEG = 1.0 / 120   # 1/day RBC turnover (120-day lifespan)
HEM_IRON_PER_G = 150   # mg body iron per g/dL Hb synthesised (dose-limiting)
HEM_HB_NORMAL = 14.0   # marrow set-point


def simulate_hematologic(*, hb0, dose, duration_days=56, dt=0.25):
    """Mechanistic erythropoiesis: oral iron -> stores -> iron-limited Hb
    synthesis under EPO drive vs RBC turnover. Produces the characteristic
    delayed (latent then rising) Hb correction curve."""
    store = 0.0                       # relative iron store (starts depleted)
    hb = hb0
    times, hblist = [], []
    steps = int(duration_days / dt)
    for i in range(steps + 1):
        t = i * dt
        times.append(round(t, 1))
        hblist.append(round(hb, 2))
        absorbed = HEM_ABS * dose                      # mg/day into circulation
        drive = max(0.0, min(1.0, (HEM_HB_NORMAL - hb) / HEM_HB_NORMAL))
        cap = HEM_KSYN * (0.25 + 0.75 * drive)         # g/dL/day marrow capacity
        iron_need = cap * HEM_IRON_PER_G
        iron_avail = min(iron_need, absorbed + store)
        synth = cap * (iron_avail / iron_need if iron_need > 0 else 0)
        store += (absorbed - iron_avail) * dt
        store = max(0.0, store)
        hb += (synth - HEM_KDEG * (hb - 8.0) - HEM_KDEG * 0.0) * dt
        hb = max(6.0, hb)
    return {"times": times, "hemoglobin": hblist, "final_hemoglobin": round(hb, 2)}


# ---------------------------------------------------------------------------
# Endocrine mechanistic model — hypothalamic-pituitary-thyroid (HPT) axis
#   levothyroxine dose -> free T4 -> sigmoid negative feedback on TSH.
# ---------------------------------------------------------------------------
ENDO_TSHMAX = 20.0     # mIU/L  max pituitary TSH output
ENDO_T4_50 = 0.9       # ng/dL  free-T4 at half-max TSH suppression
ENDO_N = 3.2           # feedback Hill coefficient
ENDO_SDOSE = 0.0072    # ng/dL free-T4 rise per mcg/day levothyroxine
ENDO_TAU_T4 = 7.0      # days  T4 equilibration (t1/2 ~ 7d)
ENDO_TAU_TSH = 9.0     # days  TSH lag behind T4


def _tsh_set(t4):
    return ENDO_TSHMAX / (1.0 + (t4 / ENDO_T4_50) ** ENDO_N)


def simulate_endocrine(*, tsh0, dose, duration_days=42, dt=0.25):
    """HPT-axis model. Baseline endogenous T4 is inferred from the patient's
    TSH so the twin is self-consistent, then levothyroxine raises T4 and TSH
    falls along the feedback curve (over-replacement over-suppresses TSH)."""
    ratio = max(1.001, ENDO_TSHMAX / max(0.05, tsh0))
    t4_endo = ENDO_T4_50 * (ratio - 1.0) ** (1.0 / ENDO_N)
    t4_ss = t4_endo + ENDO_SDOSE * dose
    t4 = t4_endo
    tsh = tsh0
    times, tshlist, t4list = [], [], []
    steps = int(duration_days / dt)
    for i in range(steps + 1):
        t = i * dt
        times.append(round(t, 1))
        tshlist.append(round(tsh, 2))
        t4list.append(round(t4, 3))
        t4 += (t4_ss - t4) / ENDO_TAU_T4 * dt
        tsh += (_tsh_set(t4) - tsh) / ENDO_TAU_TSH * dt
        tsh = max(0.02, tsh)
    return {"times": times, "tsh": tshlist, "t4": t4list,
            "final_tsh": round(tsh, 2), "final_t4": round(t4, 3)}


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

    for d in (0, 5, 20, 40):
        cv = simulate_cardiovascular(systolic0=156, diastolic0=96,
                                     agents=[{"ec50": 2.5, "dose": d}])
        print("LISINOPRIL %2dmg -> systolic %.0f  diastolic %.0f" % (
            d, cv["final_systolic"], cv["final_diastolic"]))
    combo = simulate_cardiovascular(systolic0=156, diastolic0=96,
                                    agents=[{"ec50": 2.5, "dose": 40},
                                            {"ec50": 1.2, "dose": 10, "imax": 0.16}])
    print("LIS40+AMLO10 -> systolic %.0f  diastolic %.0f" % (
        combo["final_systolic"], combo["final_diastolic"]))
    for d in (0, 65, 130, 195):
        h = simulate_hematologic(hb0=9.4, dose=d)
        print("FERROUS %3dmg -> Hb %.1f (from 9.4)" % (d, h["final_hemoglobin"]))
    for d in (0, 25, 75, 100, 150):
        e = simulate_endocrine(tsh0=8.7, dose=d)
        print("LEVO %3dmcg -> TSH %.2f  T4 %.2f (from 8.7)" % (
            d, e["final_tsh"], e["final_t4"]))
    for d in (0, 100, 200, 400):
        rp = simulate_respiratory(spo2_0=91, heart_rate0=92, drug_ic50=90, dose=d)
        print("SALBUTAMOL %3dmcg -> peak SpO2 %.1f  final %.1f  peak HR %.0f" % (
            d, rp["peak_spo2"], rp["final_spo2"], rp["peak_heart_rate"]))
