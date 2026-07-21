import React, { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "@/lib/api";
import Banner from "@/components/Banner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { ArrowLeft, ClipboardList, Save } from "lucide-react";
import { toast } from "sonner";

const DEFAULT_PARAMS = {
  fasting_glucose: 90, hba1c: 5.2, systolic_bp: 118, diastolic_bp: 76,
  heart_rate: 72, spo2: 98, hemoglobin: 13.5, tsh: 2.0, ldl: 95,
};

export default function Intake() {
  const nav = useNavigate();
  const { patientId } = useParams();
  const [catalog, setCatalog] = useState(null);
  const [form, setForm] = useState({
    name: "", age: 45, sex: "female", ethnicity: "south_asian",
    weight_kg: 70, height_cm: 165, history: "", medications: "",
    conditions: [], parameters: { ...DEFAULT_PARAMS },
  });
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.get("/catalog").then((r) => setCatalog(r.data));
    if (patientId) {
      api.get(`/patients/${patientId}`).then((r) => {
        const p = r.data;
        setForm({
          name: p.name, age: p.age, sex: p.sex, ethnicity: p.ethnicity,
          weight_kg: p.weight_kg, height_cm: p.height_cm, history: p.history || "",
          medications: (p.medications || []).join(", "),
          conditions: p.conditions || [], parameters: { ...DEFAULT_PARAMS, ...p.parameters },
        });
      });
    }
  }, [patientId]);

  const setField = (k, v) => setForm((f) => ({ ...f, [k]: v }));
  const setParam = (k, v) =>
    setForm((f) => ({ ...f, parameters: { ...f.parameters, [k]: v } }));
  const toggleCond = (id) =>
    setForm((f) => ({
      ...f,
      conditions: f.conditions.includes(id)
        ? f.conditions.filter((c) => c !== id)
        : [...f.conditions, id],
    }));

  const save = async () => {
    if (!form.name.trim()) { toast.error("Patient name required"); return; }
    setBusy(true);
    const payload = {
      ...form,
      age: Number(form.age), weight_kg: Number(form.weight_kg), height_cm: Number(form.height_cm),
      medications: form.medications.split(",").map((m) => m.trim()).filter(Boolean),
      parameters: Object.fromEntries(
        Object.entries(form.parameters).map(([k, v]) => [k, Number(v)])
      ),
    };
    try {
      const res = patientId
        ? await api.put(`/patients/${patientId}`, payload)
        : await api.post("/patients", payload);
      toast.success("Twin baseline built");
      nav(`/workspace/${res.data.id}`);
    } catch (e) {
      toast.error("Could not save patient");
    } finally {
      setBusy(false);
    }
  };

  const params = catalog?.parameters || {};

  return (
    <div className="h-screen w-screen flex flex-col bg-twin-panel overflow-hidden">
      <Banner />
      <header className="h-16 border-b border-twin-line flex items-center px-6 gap-3 shrink-0">
        <Button variant="ghost" size="sm" onClick={() => nav("/")} data-testid="intake-back">
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <ClipboardList className="h-5 w-5 text-twin-teal" />
        <div>
          <div className="font-semibold tracking-tight leading-none">
            {patientId ? "Edit patient" : "New patient intake"}
          </div>
          <div className="text-[11px] text-twin-muted font-mono">
            demographics · vitals · labs · history → twin baseline
          </div>
        </div>
        <div className="ml-auto">
          <Button data-testid="intake-save" onClick={save} disabled={busy}
            className="bg-twin-teal hover:bg-teal-700 text-white">
            <Save className="h-4 w-4" /> {busy ? "Building twin…" : "Build twin"}
          </Button>
        </div>
      </header>

      <div className="flex-1 overflow-y-auto thin-scroll px-6 py-8">
        <div className="max-w-4xl mx-auto grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* demographics */}
          <section className="bg-white border border-twin-line rounded-xl p-5">
            <h2 className="text-sm font-semibold uppercase tracking-widest text-twin-muted mb-4">Demographics</h2>
            <div className="space-y-3">
              <div>
                <Label className="text-xs">Full name</Label>
                <Input data-testid="intake-name" value={form.name} onChange={(e) => setField("name", e.target.value)} placeholder="Synthetic patient name" />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label className="text-xs">Age</Label>
                  <Input data-testid="intake-age" type="number" className="font-mono" value={form.age} onChange={(e) => setField("age", e.target.value)} />
                </div>
                <div>
                  <Label className="text-xs">Sex</Label>
                  <Select value={form.sex} onValueChange={(v) => setField("sex", v)}>
                    <SelectTrigger data-testid="intake-sex"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="female">Female</SelectItem>
                      <SelectItem value="male">Male</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <div>
                <Label className="text-xs">Ethnicity (metabolic threshold)</Label>
                <Select value={form.ethnicity} onValueChange={(v) => setField("ethnicity", v)}>
                  <SelectTrigger data-testid="intake-ethnicity"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="south_asian">South-Asian (tighter cut-offs)</SelectItem>
                    <SelectItem value="other">Other / standard</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label className="text-xs">Weight (kg)</Label>
                  <Input type="number" className="font-mono" value={form.weight_kg} onChange={(e) => setField("weight_kg", e.target.value)} />
                </div>
                <div>
                  <Label className="text-xs">Height (cm)</Label>
                  <Input type="number" className="font-mono" value={form.height_cm} onChange={(e) => setField("height_cm", e.target.value)} />
                </div>
              </div>
            </div>
          </section>

          {/* vitals + labs */}
          <section className="bg-white border border-twin-line rounded-xl p-5">
            <h2 className="text-sm font-semibold uppercase tracking-widest text-twin-muted mb-4">Vitals & Labs</h2>
            <div className="grid grid-cols-2 gap-3">
              {Object.entries(params).map(([key, p]) => (
                <div key={key}>
                  <Label className="text-xs">{p.label} <span className="text-twin-muted">({p.unit})</span></Label>
                  <Input
                    data-testid={`intake-param-${key}`}
                    type="number" step="0.1" className="font-mono"
                    value={form.parameters[key] ?? ""}
                    onChange={(e) => setParam(key, e.target.value)}
                  />
                </div>
              ))}
            </div>
          </section>

          {/* history + meds */}
          <section className="bg-white border border-twin-line rounded-xl p-5">
            <h2 className="text-sm font-semibold uppercase tracking-widest text-twin-muted mb-4">History & Medications</h2>
            <div className="space-y-3">
              <div>
                <Label className="text-xs">Clinical history</Label>
                <Textarea data-testid="intake-history" rows={4} value={form.history} onChange={(e) => setField("history", e.target.value)} placeholder="Relevant history, symptoms, family history…" />
              </div>
              <div>
                <Label className="text-xs">Current medications (comma-separated)</Label>
                <Input data-testid="intake-meds" value={form.medications} onChange={(e) => setField("medications", e.target.value)} placeholder="e.g. Amlodipine 5mg" />
              </div>
            </div>
          </section>

          {/* known conditions */}
          <section className="bg-white border border-twin-line rounded-xl p-5">
            <h2 className="text-sm font-semibold uppercase tracking-widest text-twin-muted mb-4">Known conditions (optional)</h2>
            <div className="flex flex-wrap gap-2">
              {(catalog?.diseases || []).map((d) => {
                const on = form.conditions.includes(d.id);
                return (
                  <button
                    key={d.id}
                    data-testid={`intake-cond-${d.id}`}
                    onClick={() => toggleCond(d.id)}
                    className={`text-xs font-mono px-3 py-1.5 rounded-full border transition-colors ${
                      on ? "bg-twin-teal text-white border-twin-teal"
                         : "bg-twin-panel text-twin-muted border-twin-line hover:border-twin-teal"
                    }`}
                  >
                    {d.name}
                  </button>
                );
              })}
            </div>
            <p className="text-[11px] text-twin-muted mt-4">
              If the diagnosis is unknown, leave blank — run the disease scan inside the twin workspace.
            </p>
          </section>
        </div>
      </div>
    </div>
  );
}
