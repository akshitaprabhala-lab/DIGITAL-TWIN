import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import Banner from "@/components/Banner";
import { Button } from "@/components/ui/button";
import { Slider } from "@/components/ui/slider";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ScatterChart, Scatter, ReferenceArea, ZAxis,
} from "recharts";
import {
  ArrowLeft, FlaskConical, Sparkles, Users, Loader2, TrendingUp, TriangleAlert,
} from "lucide-react";
import { toast } from "sonner";

export default function VirtualTrial() {
  const nav = useNavigate();
  const [catalog, setCatalog] = useState(null);
  const [drugId, setDrugId] = useState("metformin");
  const [size, setSize] = useState(60);
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => { api.get("/catalog").then((r) => setCatalog(r.data)); }, []);

  const run = async () => {
    setBusy(true);
    try {
      const { data } = await api.post("/trial/run", { drug_id: drugId, cohort_size: size });
      setResult(data);
      toast.success(`Trial complete · ${data.cohort_size} twins`);
    } catch (e) { toast.error("Trial failed"); }
    finally { setBusy(false); }
  };

  const drug = catalog?.drugs?.find((d) => d.id === drugId);
  const [lo, hi] = result?.band || [0, 0];
  const scatter = (result?.twins || []).map((t) => ({
    x: t.baseline, y: t.predicted, id: t.id,
    fill: t.side_effect ? "#D97706" : t.in_range ? "#0D9488" : "#71717a",
  }));
  const bd = result?.breakdown;

  return (
    <div className="h-screen w-screen flex flex-col bg-twin-panel overflow-hidden">
      <Banner />
      <header className="h-16 border-b border-twin-line flex items-center px-6 gap-3 shrink-0">
        <Button variant="ghost" size="sm" onClick={() => nav("/")} data-testid="trial-back">
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <FlaskConical className="h-5 w-5 text-twin-teal" />
        <div>
          <div className="font-semibold tracking-tight leading-none">Virtual clinical trial</div>
          <div className="text-[11px] text-twin-muted font-mono">run a drug across a cohort of synthetic twins</div>
        </div>
      </header>

      <div className="flex-1 overflow-y-auto thin-scroll px-6 py-6">
        <div className="max-w-5xl mx-auto space-y-6">
          {/* controls */}
          <section className="bg-white border border-twin-line rounded-xl p-5">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-5 items-end">
              <div>
                <label className="text-xs text-twin-muted">Drug</label>
                <Select value={drugId} onValueChange={(v) => { setDrugId(v); setResult(null); }}>
                  <SelectTrigger data-testid="trial-drug-select" className="border-twin-line"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {(catalog?.drugs || []).map((d) => (
                      <SelectItem key={d.id} value={d.id}>{d.name} · treats {d.treats}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <div className="flex justify-between text-xs mb-1">
                  <span className="text-twin-muted">Cohort size</span>
                  <span className="font-mono font-semibold flex items-center gap-1"><Users className="h-3 w-3" />{size}</span>
                </div>
                <Slider data-testid="trial-size-slider" min={20} max={200} step={20} value={[size]} onValueChange={(v) => setSize(v[0])} />
              </div>
              <Button data-testid="run-trial-btn" onClick={run} disabled={busy}
                className="bg-twin-teal hover:bg-teal-700 text-white">
                {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <FlaskConical className="h-4 w-4" />}
                Run trial
              </Button>
            </div>
          </section>

          {!result && (
            <div className="text-center py-20 text-twin-muted">
              <Users className="h-8 w-8 mx-auto mb-3 opacity-40" />
              <p className="text-sm">Pick a drug and run a virtual trial to see the distribution of responses across the cohort.</p>
            </div>
          )}

          {result && (
            <div className="space-y-6 rise">
              {/* best dose + AI summary */}
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                <div className="bg-twin-teal/5 border border-twin-teal/20 rounded-xl p-5" data-testid="best-dose-card">
                  <div className="text-[10px] font-mono uppercase tracking-widest text-twin-teal mb-1">Optimal population dose</div>
                  <div className="font-mono text-3xl font-semibold text-twin-teal">
                    {result.best_dose.dose} <span className="text-sm text-twin-muted">{result.drug.unit}</span>
                  </div>
                  <div className="mt-3 space-y-1 font-mono text-xs">
                    <div className="flex justify-between"><span className="text-twin-muted">in reference band</span><span className="font-semibold text-twin-teal">{result.best_dose.pct_in_range}%</span></div>
                    <div className="flex justify-between"><span className="text-twin-muted">responders</span><span className="font-semibold">{result.best_dose.pct_responder}%</span></div>
                    <div className="flex justify-between"><span className="text-twin-muted">side-effect risk</span><span className="font-semibold text-twin-amber">{result.best_dose.pct_side_effect}%</span></div>
                  </div>
                </div>
                <div className="lg:col-span-2 bg-white border border-twin-line rounded-xl p-5">
                  <div className="flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-widest text-twin-teal mb-2">
                    <Sparkles className="h-3 w-3" /> AI trial summary · decision support
                  </div>
                  <p data-testid="trial-summary" className="text-sm leading-relaxed whitespace-pre-wrap">{result.summary}</p>
                </div>
              </div>

              {/* dose-response */}
              <section className="bg-white border border-twin-line rounded-xl p-5">
                <h2 className="text-sm font-semibold uppercase tracking-widest text-twin-muted mb-3 flex items-center gap-2">
                  <TrendingUp className="h-4 w-4" /> Dose–response across cohort
                </h2>
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={result.dose_summary} margin={{ top: 6, right: 10, left: -12, bottom: 0 }}>
                      <CartesianGrid stroke="#eee" vertical={false} />
                      <XAxis dataKey="dose" tick={{ fontSize: 11, fontFamily: "IBM Plex Mono" }} />
                      <YAxis tick={{ fontSize: 11, fontFamily: "IBM Plex Mono" }} unit="%" />
                      <Tooltip contentStyle={{ fontFamily: "IBM Plex Mono", fontSize: 11, borderRadius: 8 }} />
                      <Legend wrapperStyle={{ fontSize: 11, fontFamily: "IBM Plex Mono" }} />
                      <Line type="monotone" dataKey="pct_in_range" name="In range" stroke="#0D9488" strokeWidth={2.4} dot={false} />
                      <Line type="monotone" dataKey="pct_responder" name="Responders" stroke="#2563eb" strokeWidth={1.8} dot={false} strokeDasharray="5 3" />
                      <Line type="monotone" dataKey="pct_side_effect" name="Side-effect" stroke="#D97706" strokeWidth={2} dot={false} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </section>

              {/* per-twin scatter + breakdown */}
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                <section className="lg:col-span-2 bg-white border border-twin-line rounded-xl p-5">
                  <h2 className="text-sm font-semibold uppercase tracking-widest text-twin-muted mb-3">
                    Per-twin response @ {result.best_dose.dose} {result.drug.unit}
                  </h2>
                  <div className="h-64">
                    <ResponsiveContainer width="100%" height="100%">
                      <ScatterChart margin={{ top: 6, right: 10, left: -12, bottom: 4 }}>
                        <CartesianGrid stroke="#eee" />
                        <XAxis type="number" dataKey="x" name="baseline" tick={{ fontSize: 10, fontFamily: "IBM Plex Mono" }}
                          label={{ value: `baseline ${result.unit}`, position: "insideBottom", offset: -2, fontSize: 10 }} domain={["auto", "auto"]} />
                        <YAxis type="number" dataKey="y" name="predicted" tick={{ fontSize: 10, fontFamily: "IBM Plex Mono" }} domain={["auto", "auto"]} />
                        <ZAxis range={[40, 40]} />
                        <ReferenceArea y1={lo} y2={hi} fill="#0D9488" fillOpacity={0.1} />
                        <Tooltip cursor={{ strokeDasharray: "3 3" }} contentStyle={{ fontFamily: "IBM Plex Mono", fontSize: 11, borderRadius: 8 }} />
                        <Scatter data={scatter} fill="#0D9488" shape="circle" />
                      </ScatterChart>
                    </ResponsiveContainer>
                  </div>
                  <div className="flex gap-4 mt-2 text-[11px] font-mono">
                    <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-twin-teal" /> in range</span>
                    <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-twin-amber" /> side-effect risk</span>
                    <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-zinc-400" /> improved / partial</span>
                  </div>
                </section>

                <section className="bg-white border border-twin-line rounded-xl p-5">
                  <h2 className="text-sm font-semibold uppercase tracking-widest text-twin-muted mb-3">Population breakdown</h2>
                  {bd && (
                    <div className="space-y-3">
                      {[
                        { k: "in_range", label: "Reached target", color: "#0D9488" },
                        { k: "improved", label: "Improved (not in range)", color: "#71717a" },
                        { k: "side_effect", label: "Side-effect risk", color: "#D97706" },
                        { k: "no_change", label: "No change", color: "#d4d4d8" },
                      ].map((row) => {
                        const pct = Math.round(100 * bd[row.k] / result.cohort_size);
                        return (
                          <div key={row.k}>
                            <div className="flex justify-between text-xs mb-1">
                              <span>{row.label}</span>
                              <span className="font-mono font-semibold">{bd[row.k]} ({pct}%)</span>
                            </div>
                            <div className="h-2 rounded-full bg-twin-line overflow-hidden">
                              <div className="h-full" style={{ width: `${pct}%`, background: row.color }} />
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                  {drug?.combine_with && result.best_dose.pct_in_range < 40 && (
                    <div className="mt-4 flex items-start gap-1.5 text-[11px] text-twin-amber bg-twin-amber/10 border border-twin-amber/30 rounded-md px-2 py-1.5">
                      <TriangleAlert className="h-3.5 w-3.5 mt-0.5 shrink-0" />
                      Low single-agent control — combination therapy likely needed for this cohort.
                    </div>
                  )}
                </section>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
