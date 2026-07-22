import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import Banner from "@/components/Banner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Activity, Plus, Search, LogOut, ChevronRight, HeartPulse, Trash2, FlaskConical,
} from "lucide-react";
import { toast } from "sonner";

const ETHN = { south_asian: "South-Asian", other: "Other" };

export default function Home() {
  const nav = useNavigate();
  const { user, logout } = useAuth();
  const [patients, setPatients] = useState([]);
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(true);

  const load = () => {
    api.get("/patients").then((r) => setPatients(r.data)).finally(() => setLoading(false));
  };
  useEffect(load, []);

  const remove = async (e, id) => {
    e.stopPropagation();
    await api.delete(`/patients/${id}`);
    toast.success("Patient removed");
    load();
  };

  const filtered = patients.filter((p) =>
    p.name.toLowerCase().includes(q.toLowerCase())
  );

  return (
    <div className="h-screen w-screen flex flex-col bg-twin-panel overflow-hidden">
      <Banner />
      {/* top bar */}
      <header className="h-16 border-b border-twin-line flex items-center px-6 justify-between shrink-0 bg-twin-panel">
        <div className="flex items-center gap-2.5">
          <div className="h-8 w-8 rounded-md bg-twin-teal flex items-center justify-center">
            <Activity className="h-4 w-4 text-white" />
          </div>
          <div>
            <div className="font-semibold tracking-tight leading-none">TwinMed</div>
            <div className="text-[11px] text-twin-muted font-mono">precision-medicine console</div>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs text-twin-muted font-mono">{user?.name} · {user?.email}</span>
          <Button data-testid="logout-btn" variant="ghost" size="sm" onClick={() => { logout(); nav("/login"); }}>
            <LogOut className="h-4 w-4" />
          </Button>
        </div>
      </header>

      <div className="flex-1 overflow-y-auto thin-scroll px-6 py-8">
        <div className="max-w-5xl mx-auto">
          <div className="flex items-end justify-between mb-6 gap-4 flex-wrap">
            <div>
              <h1 className="text-3xl font-semibold tracking-tight">Patients</h1>
              <p className="text-sm text-twin-muted mt-1">Open a twin or intake a new patient.</p>
            </div>
            <div className="flex gap-2">
              <Button data-testid="new-patient-btn" onClick={() => nav("/intake")}
                className="bg-twin-teal hover:bg-teal-700 text-white">
                <Plus className="h-4 w-4" /> New patient
              </Button>
              <Button data-testid="trials-nav-btn" variant="outline" onClick={() => nav("/trials")}
                className="border-twin-line">
                <FlaskConical className="h-4 w-4" /> Virtual trials
              </Button>
            </div>
          </div>

          <div className="relative mb-6 max-w-md">
            <Search className="h-4 w-4 absolute left-3 top-1/2 -translate-y-1/2 text-twin-muted" />
            <Input data-testid="patient-search" value={q} onChange={(e) => setQ(e.target.value)}
              placeholder="Search patients…" className="pl-9 bg-white border-twin-line" />
          </div>

          {loading ? (
            <div className="font-mono text-sm text-twin-muted">Loading…</div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {filtered.map((p) => (
                <div
                  key={p.id}
                  data-testid={`patient-card-${p.id}`}
                  onClick={() => nav(`/workspace/${p.id}`)}
                  className="group bg-white border border-twin-line rounded-xl p-5 cursor-pointer hover:border-twin-teal transition-colors rise"
                >
                  <div className="flex items-start justify-between">
                    <div className="h-10 w-10 rounded-lg bg-twin-teal/10 flex items-center justify-center">
                      <HeartPulse className="h-5 w-5 text-twin-teal" />
                    </div>
                    <button onClick={(e) => remove(e, p.id)} data-testid={`delete-patient-${p.id}`}
                      className="text-twin-muted/50 hover:text-twin-red transition-colors">
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                  <div className="mt-4 font-semibold text-lg tracking-tight">{p.name}</div>
                  <div className="text-xs text-twin-muted font-mono">
                    {p.age}y · {p.sex} · {ETHN[p.ethnicity] || p.ethnicity}
                  </div>
                  <div className="mt-4 flex flex-wrap gap-1.5">
                    {(p.conditions || []).length === 0 && (
                      <span className="text-[11px] text-twin-muted font-mono">no conditions</span>
                    )}
                    {(p.conditions || []).map((c) => (
                      <span key={c} className="text-[10px] font-mono uppercase tracking-wide px-2 py-0.5 rounded-full bg-twin-amber/10 text-twin-amber border border-twin-amber/20">
                        {c}
                      </span>
                    ))}
                  </div>
                  <div className="mt-4 flex items-center justify-between border-t border-twin-line pt-3">
                    <span className="font-mono text-xs text-twin-muted">
                      FG {p.parameters?.fasting_glucose} · A1c {p.parameters?.hba1c}
                    </span>
                    <ChevronRight className="h-4 w-4 text-twin-muted group-hover:text-twin-teal group-hover:translate-x-0.5 transition-transform" />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
