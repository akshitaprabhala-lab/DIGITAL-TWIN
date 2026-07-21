import React from "react";
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ReferenceArea, Legend,
} from "recharts";

export default function SimChart({ sim, playIndex }) {
  if (!sim) return null;
  const data = sim.series.map((s) => ({ ...s }));
  const [lo, hi] = sim.band;
  return (
    <div className="w-full h-full bg-twin-stage rounded-lg border border-twin-darkline p-3 flex flex-col">
      <div className="flex items-center justify-between mb-1">
        <div className="text-[11px] font-mono uppercase tracking-widest text-zinc-400">
          {sim.target_label} response · {sim.system}
        </div>
        <div className="text-[11px] font-mono text-zinc-500">
          x = {sim.x_label}
        </div>
      </div>
      <div className="flex-1 min-h-0">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 6, right: 10, left: -10, bottom: 0 }}>
            <CartesianGrid stroke="#1e1e22" vertical={false} />
            <XAxis dataKey="t" stroke="#52525b" tick={{ fontSize: 10, fontFamily: "IBM Plex Mono" }} />
            <YAxis stroke="#52525b" tick={{ fontSize: 10, fontFamily: "IBM Plex Mono" }} domain={["auto", "auto"]} />
            <ReferenceArea y1={lo} y2={hi} fill="#0D9488" fillOpacity={0.12} stroke="#0D9488" strokeOpacity={0.3} />
            <Tooltip
              contentStyle={{ background: "#111114", border: "1px solid #27272a", borderRadius: 8, fontFamily: "IBM Plex Mono", fontSize: 11 }}
              labelStyle={{ color: "#a1a1aa" }}
            />
            <Legend wrapperStyle={{ fontSize: 10, fontFamily: "IBM Plex Mono" }} />
            <Line type="monotone" dataKey="baseline" name="Baseline" stroke="#71717a" strokeWidth={1.5} dot={false} strokeDasharray="4 3" isAnimationActive={false} />
            <Line type="monotone" dataKey="treated" name="Treated" stroke="#0D9488" strokeWidth={2.4} dot={false} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
