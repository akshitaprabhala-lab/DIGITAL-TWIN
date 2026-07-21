import React, { useEffect, useRef, useState } from "react";
import { ResponsiveContainer, LineChart, Line, YAxis, XAxis } from "recharts";
import { Radio, X, Droplets } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function LiveMonitor({ patientId, onClose, onReading }) {
  const [reading, setReading] = useState(null);
  const [history, setHistory] = useState([]);
  const [status, setStatus] = useState("connecting");
  const esRef = useRef(null);

  useEffect(() => {
    const es = new EventSource(`${API}/sensor/stream/${patientId}?seconds=120`);
    esRef.current = es;
    es.onopen = () => setStatus("live");
    es.onmessage = (e) => {
      const d = JSON.parse(e.data);
      if (d.done) { es.close(); setStatus("ended"); return; }
      setReading(d);
      setHistory((h) => [...h.slice(-59), { t: d.t, glucose: d.model_glucose, hr: d.sensor.heart_rate }]);
      onReading && onReading(d);
    };
    es.onerror = () => { setStatus("ended"); es.close(); };
    return () => es.close();
  }, [patientId, onReading]);

  const s = reading?.sensor;
  const tiles = s ? [
    { label: "Lactate", v: s.lactate, u: "mM" },
    { label: "Cortisol", v: s.cortisol, u: "ng/mL" },
    { label: "Na⁺ (sweat)", v: s.sodium, u: "mM" },
    { label: "Heart rate", v: s.heart_rate, u: "bpm" },
    { label: "SpO₂", v: s.spo2, u: "%" },
  ] : [];

  return (
    <div data-testid="live-monitor" className="bg-twin-stage/95 border border-twin-teal/40 rounded-lg p-3 backdrop-blur w-[340px]">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-1.5 text-[11px] font-mono uppercase tracking-widest text-twin-teal">
          <Radio className={`h-3.5 w-3.5 ${status === "live" ? "pulse-amber" : ""}`} />
          Live sensor feed · {status}
        </div>
        <button data-testid="close-live-monitor" onClick={onClose} className="text-zinc-500 hover:text-zinc-200">
          <X className="h-4 w-4" />
        </button>
      </div>

      <div className="grid grid-cols-5 gap-1 mb-2">
        {tiles.map((t) => (
          <div key={t.label} className="bg-zinc-950/60 border border-twin-darkline rounded px-1.5 py-1 text-center">
            <div className="text-[8px] text-zinc-500 truncate">{t.label}</div>
            <div className="font-mono text-xs font-semibold text-zinc-100">{t.v}</div>
          </div>
        ))}
      </div>

      <div className="h-16 mb-2">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={history}>
            <XAxis dataKey="t" hide />
            <YAxis hide domain={["auto", "auto"]} />
            <Line type="monotone" dataKey="glucose" stroke="#0D9488" strokeWidth={2} dot={false} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="flex items-baseline justify-between">
        <span className="text-[10px] text-zinc-400 font-mono">MODEL-PREDICTED GLUCOSE</span>
        <span data-testid="model-glucose" className="font-mono text-lg font-semibold text-twin-teal">
          {reading?.model_glucose ?? "—"} <span className="text-[10px] text-zinc-500">mg/dL</span>
        </span>
      </div>
      <p className="flex items-start gap-1 text-[9px] text-zinc-500 mt-1 leading-tight">
        <Droplets className="h-3 w-3 mt-px shrink-0" />
        Sweat glucose correlates weakly with blood — the sensor updates model parameters; the twin predicts glucose.
      </p>
    </div>
  );
}
