import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "@/lib/api";
import Banner from "@/components/Banner";
import TwinBody3D from "@/components/twin/TwinBody3D";
import ReferencePanel from "@/components/twin/ReferencePanel";
import StatsPanel from "@/components/twin/StatsPanel";
import DoseOptimiser from "@/components/twin/DoseOptimiser";
import SimChart from "@/components/twin/SimChart";
import TopSearchBar from "@/components/twin/TopSearchBar";
import AnalysisStrip from "@/components/twin/AnalysisStrip";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import {
  Home as HomeIcon, Plus, FileText, ScanSearch, Layers, Save, Loader2,
} from "lucide-react";
import { toast } from "sonner";

const LAYERS = [
  { id: "skin", label: "Skin & organs", dot: "#E5C8B8" },
  { id: "muscle", label: "Muscular", dot: "#A63D31" },
  { id: "skeletal", label: "Skeletal", dot: "#F3F2EE" },
  { id: "nervous", label: "Nervous", dot: "#6B4C9A" },
];

export default function Workspace() {
  const { patientId } = useParams();
  const nav = useNavigate();
  const [patient, setPatient] = useState(null);
  const [catalog, setCatalog] = useState(null);
  const [threshold, setThreshold] = useState("standard");
  const [analysis, setAnalysis] = useState([]);
  const [layer, setLayer] = useState("skin");
  const [selectedRegion, setSelectedRegion] = useState(null);
  const [mode, setMode] = useState("drugs");
  const [activeDrug, setActiveDrug] = useState(null);
  const [sim, setSim] = useState(null);
  const [rec, setRec] = useState(null);
  const [scanSummary, setScanSummary] = useState("");
  const [scanBusy, setScanBusy] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [editParams, setEditParams] = useState({});
  const [liveVital, setLiveVital] = useState(null);
  const liveTimer = useRef(null);

  const params = catalog?.parameters || {};

  const runAnalysis = useCallback(async (ps, th) => {
    const { data } = await api.post("/analyse", { parameters: ps, threshold: th });
    setAnalysis(data.analysis);
  }, []);

  useEffect(() => {
    Promise.all([
      api.get(`/patients/${patientId}`),
      api.get("/catalog"),
    ]).then(([p, c]) => {
      setPatient(p.data);
      setCatalog(c.data);
      const th = p.data.ethnicity === "south_asian" ? "south_asian" : "standard";
      setThreshold(th);
      runAnalysis(p.data.parameters, th);
    });
  }, [patientId, runAnalysis]);

  // organ status: out if any of its params out of range OR belongs to a selected condition
  const organStatus = useMemo(() => {
    const st = {};
    analysis.forEach((a) => { if (!a.in_range) st[a.organ] = "out"; });
    (patient?.conditions || []).forEach((cid) => {
      const dis = (catalog?.diseases || []).find((d) => d.id === cid);
      if (dis) st[dis.organ] = "out";
    });
    return st;
  }, [analysis, patient, catalog]);

  const toggleThreshold = (checked) => {
    const th = checked ? "south_asian" : "standard";
    setThreshold(th);
    runAnalysis(patient.parameters, th);
  };

  const toggleDisease = async (id) => {
    const has = (patient.conditions || []).includes(id);
    const conditions = has
      ? patient.conditions.filter((c) => c !== id)
      : [...(patient.conditions || []), id];
    const body = { ...patient, medications: patient.medications || [], conditions };
    const { data } = await api.put(`/patients/${patientId}`, body);
    setPatient(data);
    const dis = catalog.diseases.find((d) => d.id === id);
    if (dis) setSelectedRegion(dis.region);
    toast.success(has ? `Removed ${dis?.name}` : `Added ${dis?.name} — ${dis?.organ} highlighted`);
  };

  const selectDrug = (id) => {
    setActiveDrug(catalog.drugs.find((d) => d.id === id));
    setRec(null); setSim(null);
    const drug = catalog.drugs.find((d) => d.id === id);
    const org = params[drug.target_param]?.organ;
    const orgRegion = catalog.organs[org]?.region;
    if (orgRegion) setSelectedRegion(orgRegion);
  };

  const runScan = async () => {
    setScanBusy(true);
    try {
      const { data } = await api.post("/disease-scan", { patient_id: patientId, threshold });
      setScanSummary(data.summary);
      if (data.flags?.[0]) setSelectedRegion(data.flags[0].region);
      toast.success(`Scan complete · ${data.flags.length} flag(s)`);
    } catch (e) { toast.error("Disease scan failed"); }
    finally { setScanBusy(false); }
  };

  // animate live vital along metabolic treated curve
  useEffect(() => {
    clearInterval(liveTimer.current);
    if (sim && sim.system === "metabolic" && sim.series?.length) {
      let i = 0;
      const step = 3;
      liveTimer.current = setInterval(() => {
        const pt = sim.series[i];
        if (!pt) { clearInterval(liveTimer.current); setLiveVital(null); return; }
        setLiveVital({ key: "fasting_glucose", value: pt.treated });
        i += step;
      }, 90);
    } else {
      setLiveVital(null);
    }
    return () => clearInterval(liveTimer.current);
  }, [sim]);

  const openEdit = () => {
    setEditParams({ ...patient.parameters });
    setEditOpen(true);
  };
  const saveEdit = async () => {
    const body = {
      ...patient, medications: patient.medications || [],
      parameters: Object.fromEntries(Object.entries(editParams).map(([k, v]) => [k, Number(v)])),
    };
    const { data } = await api.put(`/patients/${patientId}`, body);
    setPatient(data);
    runAnalysis(data.parameters, threshold);
    setEditOpen(false);
    toast.success("Parameters updated — twin re-baselined");
  };

  const saveCase = async () => {
    await api.post("/save-case", {
      patient_id: patientId,
      payload: {
        threshold, analysis,
        drug: activeDrug ? { id: activeDrug.id, name: activeDrug.name } : null,
        recommendation: rec, simulation_summary: sim
          ? { target: sim.target_label, predicted: sim.predicted_value, baseline: sim.baseline_value }
          : null,
      },
    });
    toast.success("Case saved");
  };

  if (!patient || !catalog) {
    return (
      <div className="h-screen w-screen flex items-center justify-center bg-twin-panel">
        <Loader2 className="h-5 w-5 animate-spin text-twin-teal" />
      </div>
    );
  }

  return (
    <div className="h-screen w-screen flex flex-col bg-twin-panel overflow-hidden">
      <Banner />

      {/* top bar */}
      <header className="h-16 border-b border-twin-line flex items-center px-4 gap-4 shrink-0">
        <div className="flex items-center gap-2 shrink-0">
          <Button data-testid="home-btn" variant="ghost" size="sm" onClick={() => nav("/")}>
            <HomeIcon className="h-4 w-4" />
          </Button>
          <Button data-testid="ws-new-patient" variant="ghost" size="sm" onClick={() => nav("/intake")}>
            <Plus className="h-4 w-4" />
          </Button>
          <div className="border-l border-twin-line pl-3">
            <div className="font-semibold tracking-tight leading-none" data-testid="ws-patient-name">{patient.name}</div>
            <div className="text-[11px] text-twin-muted font-mono">
              {patient.age}y · {patient.sex} · {patient.ethnicity === "south_asian" ? "South-Asian" : "standard"}
            </div>
          </div>
        </div>

        <div className="flex-1 flex justify-center">
          <TopSearchBar
            mode={mode} setMode={setMode} catalog={catalog}
            conditions={patient.conditions || []} onToggleDisease={toggleDisease}
            activeDrug={activeDrug} onSelectDrug={selectDrug}
            onEditParams={openEdit} selectedRegion={selectedRegion} organs={catalog.organs}
          />
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <Button data-testid="save-case-btn" variant="ghost" size="sm" onClick={saveCase}>
            <Save className="h-4 w-4" />
          </Button>
          <Button data-testid="report-btn" variant="outline" size="sm" className="border-twin-line"
            onClick={() => nav(`/report/${patientId}`)}>
            <FileText className="h-4 w-4" /> Report
          </Button>
        </div>
      </header>

      {/* workspace grid */}
      <div className="flex-1 grid grid-cols-12 overflow-hidden">
        {/* LEFT: reference ranges */}
        <aside className="col-span-3 border-r border-twin-line bg-twin-panel p-4 overflow-hidden">
          <ReferencePanel parameters={params} analysis={analysis} threshold={threshold}
            onToggleThreshold={toggleThreshold} />
        </aside>

        {/* CENTER: dark imaging stage */}
        <main className="col-span-6 bg-twin-stage relative flex flex-col overflow-hidden">
          <div className="flex-1 relative min-h-0">
            {/* layer switcher */}
            <div className="absolute top-4 left-4 z-10 flex flex-col gap-1.5">
              <div className="flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-widest text-zinc-500 mb-0.5">
                <Layers className="h-3 w-3" /> Layers
              </div>
              {LAYERS.map((l) => (
                <button
                  key={l.id}
                  data-testid={`layer-${l.id}`}
                  onClick={() => setLayer(l.id)}
                  className={`flex items-center gap-2 text-xs px-2.5 py-1.5 rounded-md border transition-colors ${
                    layer === l.id
                      ? "bg-zinc-900 border-twin-teal text-zinc-100"
                      : "bg-zinc-950/60 border-twin-darkline text-zinc-400 hover:text-zinc-200"
                  }`}
                >
                  <span className="h-2.5 w-2.5 rounded-full" style={{ background: l.dot }} />
                  {l.label}
                </button>
              ))}
            </div>

            {/* region + scan */}
            <div className="absolute top-4 right-4 z-10 flex flex-col items-end gap-2">
              <div className="text-[10px] font-mono uppercase tracking-widest text-zinc-500">
                region: <span className="text-twin-teal">{selectedRegion || "none"}</span>
              </div>
              <Button data-testid="disease-scan-btn" size="sm" onClick={runScan} disabled={scanBusy}
                className="bg-zinc-900 border border-twin-darkline text-zinc-100 hover:bg-zinc-800">
                {scanBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : <ScanSearch className="h-4 w-4" />}
                AI disease scan
              </Button>
            </div>

            <TwinBody3D layer={layer} organStatus={organStatus}
              selectedRegion={selectedRegion} onSelectRegion={setSelectedRegion} />

            {/* analysis strip */}
            <div className="absolute bottom-3 left-4 right-4 z-10">
              <AnalysisStrip analysis={analysis} scanSummary={scanSummary} />
            </div>
          </div>

          {/* simulation chart */}
          {sim && (
            <div className="h-56 border-t border-twin-darkline p-3 shrink-0" data-testid="sim-chart-wrap">
              <SimChart sim={sim} />
            </div>
          )}
        </main>

        {/* RIGHT: stats + optimiser */}
        <aside className="col-span-3 border-l border-twin-line bg-twin-panel p-4 overflow-y-auto thin-scroll flex flex-col gap-4">
          <StatsPanel analysis={analysis} parameters={params} liveVital={liveVital} />
          <DoseOptimiser patientId={patientId} drug={activeDrug} threshold={threshold}
            onSim={setSim} onRec={setRec} rec={rec} />
        </aside>
      </div>

      {/* edit params dialog */}
      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader><DialogTitle>Edit patient parameters</DialogTitle>
            <DialogDescription>Adjust vitals & labs — the twin re-baselines on save.</DialogDescription>
          </DialogHeader>
          <div className="grid grid-cols-2 gap-3 max-h-[50vh] overflow-y-auto thin-scroll pr-1">
            {Object.entries(params).map(([key, p]) => (
              <div key={key}>
                <Label className="text-xs">{p.label} ({p.unit})</Label>
                <Input data-testid={`edit-param-${key}`} type="number" step="0.1" className="font-mono"
                  value={editParams[key] ?? ""}
                  onChange={(e) => setEditParams((s) => ({ ...s, [key]: e.target.value }))} />
              </div>
            ))}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditOpen(false)}>Cancel</Button>
            <Button data-testid="save-params-btn" className="bg-twin-teal text-white hover:bg-teal-700" onClick={saveEdit}>
              Save & re-baseline
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
