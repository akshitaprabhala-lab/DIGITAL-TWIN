import React from "react";
import { Activity } from "lucide-react";

export default function StatsPanel({ analysis, parameters, liveVitals }) {
  const fmt = (v, key) => Number(v).toFixed(parameters[key]?.decimals ?? 0);
  const live = liveVitals || {};
  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-[11px] font-semibold uppercase tracking-widest text-twin-muted">
          Current stats · live vitals
        </h2>
        <span className="flex items-center gap-1 text-[10px] font-mono text-twin-teal">
          <Activity className="h-3 w-3" /> LIVE
        </span>
      </div>
      <div className="grid grid-cols-2 gap-1.5">
        {(analysis || []).map((a) => {
          const isLive = a.key in live;
          const value = isLive ? live[a.key] : a.value;
          return (
            <div
              key={a.key}
              data-testid={`stat-${a.key}`}
              className={`bg-white border rounded-lg px-3 py-2 ${
                a.in_range ? "border-twin-line" : "border-twin-amber/40 bg-twin-amber/5"
              }`}
            >
              <div className="text-[10px] text-twin-muted truncate">{a.label}</div>
              <div className="flex items-baseline gap-1">
                <span
                  data-testid={`value-${a.key}`}
                  className={`font-mono text-lg font-semibold tabular-nums ${
                    a.in_range ? "text-twin-ink" : "text-twin-amber"
                  } ${isLive ? "text-twin-teal" : ""}`}
                >
                  {fmt(value, a.key)}
                </span>
                <span className="text-[10px] text-twin-muted font-mono">{a.unit}</span>
              </div>
              {!a.in_range && (
                <div className="text-[9px] font-mono uppercase tracking-wide text-twin-amber">
                  {a.side}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
