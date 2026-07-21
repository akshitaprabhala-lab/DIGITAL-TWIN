import React, { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "@/lib/api";
import Banner from "@/components/Banner";
import { Button } from "@/components/ui/button";
import { ArrowLeft, Printer, Loader2, Sparkles, FileText } from "lucide-react";

export default function Report() {
  const { patientId } = useParams();
  const nav = useNavigate();
  const [patient, setPatient] = useState(null);
  const [summary, setSummary] = useState("");
  const [oor, setOor] = useState([]);
  const [analysis, setAnalysis] = useState([]);
  const [cases, setCases] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      const p = await api.get(`/patients/${patientId}`);
      setPatient(p.data);
      const th = p.data.ethnicity === "south_asian" ? "south_asian" : "standard";
      const cs = await api.get(`/patients/${patientId}/cases`);
      setCases(cs.data);
      const tried = cs.data
        .map((c) => c.payload?.recommendation
          ? `${c.payload.recommendation.drug?.name} ${c.payload.recommendation.recommended_dose}${c.payload.recommendation.unit}`
          : c.payload?.drug?.name)
        .filter(Boolean);
      const s = await api.post("/case-summary", { patient_id: patientId, threshold: th, tried });
      setSummary(s.data.summary);
      setOor(s.data.out_of_range);
      setAnalysis(s.data.analysis);
      setLoading(false);
    })();
  }, [patientId]);

  if (loading || !patient) {
    return (
      <div className="h-screen w-screen flex items-center justify-center bg-twin-panel">
        <Loader2 className="h-5 w-5 animate-spin text-twin-teal" />
      </div>
    );
  }

  return (
    <div className="h-screen w-screen flex flex-col bg-twin-panel overflow-hidden">
      <Banner />
      <header className="h-16 border-b border-twin-line flex items-center px-6 gap-3 shrink-0 print:hidden">
        <Button variant="ghost" size="sm" onClick={() => nav(`/workspace/${patientId}`)} data-testid="report-back">
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <FileText className="h-5 w-5 text-twin-teal" />
        <div className="font-semibold tracking-tight">Case report · {patient.name}</div>
        <div className="ml-auto">
          <Button data-testid="print-btn" onClick={() => window.print()} className="bg-twin-teal text-white hover:bg-teal-700">
            <Printer className="h-4 w-4" /> Export / Print
          </Button>
        </div>
      </header>

      <div className="flex-1 overflow-y-auto thin-scroll px-6 py-8">
        <div className="max-w-3xl mx-auto space-y-6">
          <section className="bg-white border border-twin-line rounded-xl p-6">
            <div className="flex items-baseline justify-between">
              <h1 className="text-2xl font-semibold tracking-tight">{patient.name}</h1>
              <span className="font-mono text-xs text-twin-muted">
                {patient.age}y · {patient.sex} · {patient.ethnicity === "south_asian" ? "South-Asian" : "standard"}
              </span>
            </div>
            <p className="text-sm text-twin-muted mt-2">{patient.history || "No history recorded."}</p>
          </section>

          {/* AI summary */}
          <section className="bg-twin-teal/5 border border-twin-teal/20 rounded-xl p-6">
            <div className="flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-widest text-twin-teal mb-2">
              <Sparkles className="h-3 w-3" /> AI case summary · decision support
            </div>
            <p data-testid="report-summary" className="text-sm leading-relaxed whitespace-pre-wrap">{summary}</p>
          </section>

          {/* deviations */}
          <section className="bg-white border border-twin-line rounded-xl p-6">
            <h2 className="text-sm font-semibold uppercase tracking-widest text-twin-muted mb-3">Parameter deviations</h2>
            {oor.length === 0 ? (
              <p className="text-sm text-twin-teal font-mono">All parameters within reference band.</p>
            ) : (
              <div className="flex flex-wrap gap-2">
                {oor.map((o, i) => (
                  <span key={i} className="text-xs font-mono px-2.5 py-1 rounded-full bg-twin-amber/10 text-twin-amber border border-twin-amber/20">{o}</span>
                ))}
              </div>
            )}
            <table className="w-full mt-4 text-xs font-mono">
              <thead>
                <tr className="text-twin-muted text-left border-b border-twin-line">
                  <th className="py-1.5 font-medium">Parameter</th>
                  <th className="font-medium">Value</th>
                  <th className="font-medium">Band</th>
                  <th className="font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {analysis.map((a) => (
                  <tr key={a.key} className="border-b border-twin-line/60">
                    <td className="py-1.5">{a.label}</td>
                    <td className={a.in_range ? "" : "text-twin-amber font-semibold"}>{a.value} {a.unit}</td>
                    <td className="text-twin-muted">{a.low}–{a.high}</td>
                    <td className={a.in_range ? "text-twin-teal" : "text-twin-amber"}>
                      {a.in_range ? "in range" : a.side}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>

          {/* saved simulations */}
          <section className="bg-white border border-twin-line rounded-xl p-6">
            <h2 className="text-sm font-semibold uppercase tracking-widest text-twin-muted mb-3">What was tried</h2>
            {cases.length === 0 ? (
              <p className="text-sm text-twin-muted">No saved simulations yet. Run a dose optimisation and save the case from the workspace.</p>
            ) : (
              <div className="space-y-3">
                {cases.map((c) => {
                  const r = c.payload?.recommendation;
                  return (
                    <div key={c.id} className="border border-twin-line rounded-lg p-3">
                      <div className="flex items-center justify-between">
                        <span className="text-sm font-medium">{r?.drug?.name || c.payload?.drug?.name || "Simulation"}</span>
                        <span className="font-mono text-[11px] text-twin-muted">{new Date(c.created_at).toLocaleString()}</span>
                      </div>
                      {r && (
                        <div className="mt-1.5 font-mono text-xs">
                          <span className="text-twin-teal font-semibold">{r.recommended_dose} {r.unit}</span>
                          {" · "}{r.target_label} {r.baseline_value} → {r.predicted_value}
                          {" · conf "}{Math.round(r.confidence * 100)}%
                        </div>
                      )}
                      {r?.rationale && <p className="text-xs text-twin-muted mt-1.5 leading-relaxed">{r.rationale}</p>}
                    </div>
                  );
                })}
              </div>
            )}
          </section>

          <p className="text-[11px] text-twin-muted font-mono text-center pb-6">
            TwinMed research prototype · not for clinical use · synthetic data · all outputs are decision support the doctor confirms.
          </p>
        </div>
      </div>
    </div>
  );
}
