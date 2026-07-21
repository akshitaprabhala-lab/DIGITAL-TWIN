import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Slider } from "@/components/ui/slider";
import { Sparkles, FlaskConical, ShieldCheck, TriangleAlert, Check, Layers2 } from "lucide-react";
import { toast } from "sonner";

export default function DoseOptimiser({ patientId, drug, threshold, onSim, onRec, rec }) {
  const [dose, setDose] = useState(drug ? drug.min_dose : 0);
  const [busy, setBusy] = useState(false);
  const [optBusy, setOptBusy] = useState(false);

  useEffect(() => { if (drug) setDose(drug.min_dose); }, [drug]);

  if (!drug) {
    return (
      <div className="bg-white border border-twin-line rounded-xl p-5 text-center">
        <FlaskConical className="h-6 w-6 text-twin-muted mx-auto mb-2" />
        <div className="text-sm font-medium">Dose optimiser</div>
        <p className="text-xs text-twin-muted mt-1">
          Pick a drug from the <b>Drugs</b> search mode to test it on the twin.
        </p>
      </div>
    );
  }

  const simulate = async () => {
    setBusy(true);
    try {
      const { data } = await api.post("/simulate", {
        patient_id: patientId, drug_id: drug.id, dose, threshold,
      });
      onSim(data);
      toast.success(`Simulated ${drug.name} ${dose} ${drug.unit}`);
    } catch (e) { toast.error("Simulation failed"); }
    finally { setBusy(false); }
  };

  const optimise = async () => {
    setOptBusy(true);
    try {
      const { data } = await api.post("/optimise", {
        patient_id: patientId, drug_id: drug.id, threshold,
      });
      onRec(data);
      setDose(data.recommended_dose);
      if (data.trajectory) onSim({ ...data.trajectory, drug: { ...drug, dose: data.recommended_dose } });
      toast.success("AI dose recommendation ready");
    } catch (e) { toast.error("Optimisation failed"); }
    finally { setOptBusy(false); }
  };

  const conf = rec ? Math.round(rec.confidence * 100) : 0;

  return (
    <div className="bg-white border border-twin-line rounded-xl p-4 space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-sm font-semibold tracking-tight">{drug.name}</div>
          <div className="text-[10px] font-mono text-twin-muted uppercase tracking-wide">
            treats {drug.treats} · target {drug.target_param}
          </div>
        </div>
        <FlaskConical className="h-4 w-4 text-twin-teal" />
      </div>

      {/* dose slider */}
      <div>
        <div className="flex items-center justify-between mb-1.5">
          <span className="text-xs text-twin-muted">Dose</span>
          <span className="font-mono text-sm font-semibold">{dose} {drug.unit}</span>
        </div>
        <Slider
          data-testid="dose-slider"
          min={drug.min_dose} max={drug.max_dose} step={drug.step}
          value={[dose]} onValueChange={(v) => setDose(v[0])}
        />
        <div className="flex justify-between text-[10px] font-mono text-twin-muted mt-1">
          <span>{drug.min_dose}</span>
          <span className="text-twin-amber">max safe {drug.max_safe}</span>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-2">
        <Button data-testid="simulate-btn" onClick={simulate} disabled={busy}
          variant="outline" className="border-twin-line">
          <FlaskConical className="h-4 w-4" /> {busy ? "…" : "Simulate"}
        </Button>
        <Button data-testid="optimise-btn" onClick={optimise} disabled={optBusy}
          className="bg-twin-teal hover:bg-teal-700 text-white">
          <Sparkles className="h-4 w-4" /> {optBusy ? "Thinking…" : "AI optimise"}
        </Button>
      </div>

      {/* recommendation */}
      {rec && (
        <div data-testid="recommendation-card" className="rise border-t border-twin-line pt-3 space-y-2">
          <div className="flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-widest text-twin-teal">
            <Sparkles className="h-3 w-3" /> Decision support
          </div>
          <div className="bg-twin-teal/5 border border-twin-teal/20 rounded-lg p-3">
            <div className="flex items-baseline justify-between">
              <span className="text-xs text-twin-muted">Recommended dose</span>
              <span data-testid="rec-dose" className="font-mono text-lg font-semibold text-twin-teal">
                {rec.recommended_dose} {rec.drug.unit}
              </span>
            </div>
            <div className="flex items-baseline justify-between mt-1 font-mono text-xs">
              <span className="text-twin-muted">{rec.target_label}</span>
              <span>
                {rec.baseline_value} <span className="text-twin-muted">→</span>{" "}
                <span className="text-twin-teal font-semibold">{rec.predicted_value}</span>
                <span className="text-twin-muted"> (band {rec.band[0]}–{rec.band[1]})</span>
              </span>
            </div>
          </div>

          {/* confidence */}
          <div>
            <div className="flex items-center justify-between text-[11px] mb-1">
              <span className="text-twin-muted">Model confidence</span>
              <span className="font-mono font-semibold">{conf}%</span>
            </div>
            <div className="h-1.5 rounded-full bg-twin-line overflow-hidden">
              <div className="h-full bg-twin-teal transition-all" style={{ width: `${conf}%` }} />
            </div>
          </div>

          {!rec.achieves_target && (
            <div className="flex items-start gap-1.5 text-[11px] text-twin-amber bg-twin-amber/10 border border-twin-amber/30 rounded-md px-2 py-1.5">
              <TriangleAlert className="h-3.5 w-3.5 mt-0.5 shrink-0" />
              Target not fully reachable within max dose — combination therapy may be needed.
            </div>
          )}

          <p className="text-xs leading-relaxed text-twin-ink whitespace-pre-wrap">{rec.rationale}</p>

          {rec.combination && (
            <div data-testid="combination-card" className="rise bg-twin-amber/5 border border-twin-amber/30 rounded-lg p-3 space-y-1.5">
              <div className="flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-widest text-twin-amber">
                <Layers2 className="h-3 w-3" /> Combination therapy suggested
              </div>
              <p className="text-[11px] text-twin-muted leading-relaxed">
                Single-agent {rec.drug.name} plateaus outside the band — add a second-line agent:
              </p>
              <div className="font-mono text-xs space-y-0.5">
                <div className="flex justify-between">
                  <span>{rec.combination.primary.name}</span>
                  <span className="font-semibold">{rec.combination.primary.dose} {rec.drug.unit}</span>
                </div>
                <div className="flex justify-between text-twin-amber">
                  <span>+ {rec.combination.secondary.name}</span>
                  <span className="font-semibold">{rec.combination.secondary.dose} {rec.combination.secondary.unit}</span>
                </div>
                <div className="flex justify-between border-t border-twin-amber/20 pt-1 mt-1">
                  <span className="text-twin-muted">combined {rec.target_label}</span>
                  <span className="font-semibold text-twin-teal">
                    {rec.baseline_value} → {rec.combination.predicted_value}
                  </span>
                </div>
              </div>
            </div>
          )}

          <div className="flex items-start gap-1.5 text-[11px] text-twin-muted">
            <ShieldCheck className="h-3.5 w-3.5 mt-0.5 shrink-0" /> {rec.drug.side_effects}
          </div>

          <Button data-testid="confirm-btn" size="sm" variant="outline"
            className="w-full border-twin-teal text-twin-teal hover:bg-twin-teal hover:text-white"
            onClick={() => toast.success("Noted — doctor confirms decision (prototype)")}>
            <Check className="h-4 w-4" /> Doctor confirms
          </Button>
        </div>
      )}
    </div>
  );
}
