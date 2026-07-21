"""LLM reasoning layer (Claude Sonnet 4.6 via Emergent Universal Key).

The LLM NEVER invents a vital sign or a dose. It only ranks, reasons and
explains numbers produced by the mechanistic twin engine.
"""
import os
import json
import logging

logger = logging.getLogger(__name__)

MODEL_PROVIDER = "anthropic"
MODEL_NAME = "claude-sonnet-4-6"

SYSTEM_MSG = (
    "You are TwinMed's clinical decision-support assistant embedded in a research "
    "prototype (NOT for clinical use). You explain simulation results from a "
    "mechanistic physiological twin. You must NEVER invent numbers, vitals or doses; "
    "only reason about the values given to you. Keep language precise, calm and "
    "clinician-facing. Always frame output as decision support the doctor confirms. "
    "Respond in 2-4 short sentences unless asked for a structured summary."
)


async def _ask(prompt: str, session_id: str) -> str:
    api_key = os.environ.get("EMERGENT_LLM_KEY")
    if not api_key:
        raise RuntimeError("EMERGENT_LLM_KEY missing")
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    chat = LlmChat(api_key=api_key, session_id=session_id, system_message=SYSTEM_MSG).with_model(
        MODEL_PROVIDER, MODEL_NAME
    )
    resp = await chat.send_message(UserMessage(text=prompt))
    if isinstance(resp, str):
        return resp.strip()
    return str(resp).strip()


async def dose_rationale(patient_name, drug, dose, target_label, baseline, predicted,
                         target_band, confidence, session_id):
    prompt = (
        f"Patient: {patient_name}. The mechanistic twin searched the dose space for "
        f"{drug['name']} to bring {target_label} into its reference band {target_band}.\n"
        f"Baseline {target_label}: {baseline}. Recommended dose: {dose} {drug['unit']}. "
        f"Predicted {target_label} after treatment: {predicted}. "
        f"Model confidence: {int(confidence * 100)}%.\n"
        f"Known side-effects: {drug['side_effects']} Contraindications: {drug['contraindications']}.\n"
        "Write a concise clinical rationale (2-3 sentences) for why this dose is proposed, "
        "note the key safety caveat, and remind that the doctor confirms. Do not invent any numbers."
    )
    try:
        return await _ask(prompt, session_id)
    except Exception as e:
        logger.warning(f"LLM dose_rationale fallback: {e}")
        return (
            f"The twin predicts {dose} {drug['unit']} of {drug['name']} moves {target_label} "
            f"from {baseline} toward {predicted}, within the target band {target_band}. "
            f"Watch for: {drug['side_effects']} This is decision support — confirm before prescribing."
        )


async def disease_scan_summary(patient_name, flags, session_id):
    if not flags:
        return "No parameters fall outside their reference bands; no conditions flagged by the rule engine."
    items = "; ".join(f"{f['name']} ({int(f['confidence']*100)}%): {', '.join(f['evidence'])}" for f in flags)
    prompt = (
        f"Patient: {patient_name}. The rule engine flagged these candidate conditions from "
        f"out-of-range parameters: {items}. Summarise in 2-3 sentences which condition is most "
        "likely and what to corroborate. Do not invent numbers or add conditions not listed."
    )
    try:
        return await _ask(prompt, session_id)
    except Exception as e:
        logger.warning(f"LLM disease_scan fallback: {e}")
        top = flags[0]
        return (f"Most likely: {top['name']} ({int(top['confidence']*100)}%), supported by "
                f"{', '.join(top['evidence'])}. Corroborate with confirmatory testing. Decision support only.")


async def case_summary(patient, out_of_range, tried, session_id):
    tried_txt = "; ".join(tried) if tried else "no simulations yet"
    oor = "; ".join(out_of_range) if out_of_range else "all parameters in range"
    prompt = (
        f"Patient {patient['name']}, {patient['age']}y {patient['sex']}. "
        f"Out-of-range parameters: {oor}. Conditions: {', '.join(patient.get('conditions', [])) or 'none'}. "
        f"Simulations tried: {tried_txt}. Write a 3-4 sentence natural-language case summary of the "
        "twin's current state and what was tried. Decision support only; do not invent numbers."
    )
    try:
        return await _ask(prompt, session_id)
    except Exception as e:
        logger.warning(f"LLM case_summary fallback: {e}")
        return (f"{patient['name']} ({patient['age']}y {patient['sex']}) currently shows: {oor}. "
                f"Simulations attempted: {tried_txt}. Findings are illustrative decision support only.")
