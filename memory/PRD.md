# TwinMed — Product Requirements & Progress

## Original problem statement
Doctor-facing precision-medicine web app. A real patient's data drives a personalised
virtual physiological twin. The doctor tests drugs/doses on the twin before prescribing;
an AI assistant recommends the drug + dose most likely to bring parameters into range with
least risk. Long-term: virtual clinical trials across synthetic-twin cohorts.

## Core loop (the spine)
Intake → twin baseline → disease scan/select → drug & dose simulation → AI dose
optimisation (rationale + confidence) → save & report.

## Architecture
- **Frontend**: React 19 + Tailwind, react-three-fiber@9 + drei@10 (interactive 3D twin),
  recharts (Bergman curves), framer-motion, lucide-react. `@` alias → `src`.
- **Backend**: FastAPI + MongoDB (motor). JWT auth (uuid user ids, httpOnly cookie + Bearer).
- **Simulation engine** (`twin_engine.py`): Bergman minimal model (fixed validated constants;
  only patient params vary — si_factor, beta_factor, set-points). Tier-1 delta model for
  non-metabolic systems.
- **Catalog** (`catalog.py`): validated reference ranges (standard + South-Asian), 5 diseases,
  5 drugs, twin-init mapping, rule-based disease scan.
- **AI** (`llm_service.py`): Claude Sonnet 4.6 via Emergent key — reasoning/explanation ONLY.
  Numbers always come from the mechanistic model. Deterministic fallbacks if LLM fails.

## User personas
- Doctor / clinician (primary operator; confirms all AI output as decision support).
- Patient (subject of the twin; no login in prototype).

## Core requirements (static)
- Every AI output is decision support; doctor confirms. Never a prescription.
- No real PHI — synthetic patients only. Persistent "not for clinical use" banner.
- Show model assumptions + confidence; never a bare authoritative number.

## Implemented (2026-07-21)
- Auth: register/login/logout/me; seeded doctor `doctor@twinmed.app / twinmed123`.
- Home patient list (cards + search) + New patient + Virtual trials nav; 3 synthetic patients seeded.
- Intake form → twin baseline. Twin Workspace: 3D imaging stage (layer switch, clickable
  regions, amber-glow organs, breathing/heartbeat), reference panel + South-Asian toggle,
  live stats, four-mode search bar, analysis strip, AI dose optimiser, disease scan, case report.
- Bergman glucose engine validated (healthy ~132 & settles, T2D ~204 slow, metformin lowers).
- Testing iteration_1: backend 17/17, frontend flows pass. Fixed rec-dose unit + dialog a11y.

## Implemented — Phase 3 & 4 (2026-07-21, second iteration)
- **Virtual Trials** (`/trials`): generate a cohort of synthetic twins, run a drug across a
  dose sweep, show dose–response (in-range / responders / side-effects), per-twin scatter,
  population breakdown, optimal population dose, and AI trial summary. `POST /api/trial/run`.
- **Live Sensor Feed**: SSE `GET /api/sensor/stream/{pid}` (unauth, EventSource) streaming
  synthetic sweat/wearable signals (lactate, cortisol, Na⁺, HR, SpO₂). Sweat glucose is NOT
  read directly — sensor signals update model parameters and the twin predicts glucose.
  Workspace `live-feed-btn` → LiveMonitor overlay + right-column live vitals update.
- **Deeper Heart & Lung mechanistic models**: `simulate_cardiovascular` (PK/PD multi-agent
  BP ODE) and `simulate_respiratory` (O2-Hb dissociation SpO₂ ODE) replace the delta model
  for lisinopril/amlodipine and salbutamol.
- **Combination Therapy**: added second-line drugs (empagliflozin, amlodipine); `/api/optimise`
  proposes a two-drug regimen when a single agent can't reach the band (e.g. lisinopril+
  amlodipine 137→125; metformin+empagliflozin). Combination-card in the optimiser UI.
- Testing iteration_2: backend 27/27, frontend flows 100%, no critical issues.

## Implemented — iteration 3 (2026-07-21)
- **Mechanistic iron & thyroid models**: `simulate_hematologic` (oral iron → stores →
  iron-limited erythropoiesis vs RBC turnover; delayed Hb-correction curve, dose-sensitive)
  and `simulate_endocrine` (HPT-axis; baseline T4 inferred from TSH for self-consistency,
  sigmoid negative feedback). Ferrous & levothyroxine now use full ODE curves like the others.
- **Trial History**: every `/api/trial/run` is persisted; `GET /api/trials` (lightweight list)
  and `GET /api/trials/{id}` (full). `/trials` page shows a history table, opens past trials,
  and compares 2–4 runs side by side in a grouped bar chart.
- **Physiology Map**: `PhysiologyMap` interactive SVG pathway graph per organ (organ/mediator/
  param nodes); clicking a node highlights its downstream pathway and param nodes show the
  patient's live value/status. Opened from the Physiology-links search mode.
- Fixed non-idempotent patient seed → now per-name upsert (deleted seeds self-heal on restart).
- Testing iteration_3: backend 35/35, frontend flows 100%, no bugs.

## Backlog
- **P2**: Multi-tenant scoping of trials/patients by doctor id; server.py → routes/ package split.
- **P2**: Triple/N-agent combination search; persist & compare individual optimisation cases.
- **P3**: Real MQTT broker ingestion + signed short-lived token to authenticate the SSE feed.

## Next tasks
- Route package refactor, N-agent combinations, real sensor ingestion.
