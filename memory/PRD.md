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
- Home patient list (cards + search) + New patient; 3 synthetic patients auto-seeded.
- Intake form (demographics, vitals, labs, history, meds, known conditions) → twin baseline.
- Twin Workspace: dark 3D imaging stage (layer switch skin/muscle/skeletal/nervous,
  clickable regions, amber-glow out-of-range organs, breathing/heartbeat), left
  Reference-range panel with South-Asian toggle, right Current stats + live vitals,
  four-mode top search bar (Diseases / Physiology links / Parameters / Drugs), analysis strip.
- Drug simulation: Bergman glucose/insulin curves (baseline vs treated) for metformin;
  delta-model trajectories for lisinopril/ferrous/levothyroxine/salbutamol.
- AI Dose Optimiser: dose-space search → recommended dose, baseline→predicted, confidence
  bar, Claude rationale, safety caveats, doctor-confirm.
- AI disease scan + AI case summary. Case report screen (deviation table, what-was-tried,
  export/print). Save case.
- Bergman validated: healthy meal peak ~132 mg/dL & settles; T2D ~204 & slow; metformin lowers.
- Testing: backend 17/17 pass; frontend E2E flows pass. Fixed rec-dose unit bug + dialog a11y.

## Backlog
- **P1**: Sensor / MQTT live feed updating the twin in real time (Phase 3).
- **P1**: Virtual clinical trials — cohort of synthetic twins, run a drug, response distribution (Phase 4).
- **P2**: More mechanistic models (cardiovascular, renal, respiratory) replacing delta tiers.
- **P2**: Physiology-link graph visualisation (interactive node trace) beyond text popover.
- **P2**: Multi-drug combination optimisation; contraindication gating from patient context.

## Next tasks
- Phase 3 sensor ingestion, Phase 4 virtual trials, deeper mechanistic models.
