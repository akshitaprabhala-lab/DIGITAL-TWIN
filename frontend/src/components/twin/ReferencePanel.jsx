import React from "react";
import { Switch } from "@/components/ui/switch";

export default function ReferencePanel({ parameters, analysis, threshold, onToggleThreshold }) {
  const byKey = Object.fromEntries((analysis || []).map((a) => [a.key, a]));
  const fmt = (v, key) => {
    const dec = parameters[key]?.decimals ?? 0;
    return Number(v).toFixed(dec);
  };
  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-[11px] font-semibold uppercase tracking-widest text-twin-muted">
          Reference ranges
        </h2>
      </div>

      <div className="flex items-center justify-between bg-white border border-twin-line rounded-lg px-3 py-2 mb-3">
        <div>
          <div className="text-xs font-medium">South-Asian thresholds</div>
          <div className="text-[10px] text-twin-muted font-mono">tighter glucose / HbA1c</div>
        </div>
        <Switch
          data-testid="south-asian-toggle"
          checked={threshold === "south_asian"}
          onCheckedChange={onToggleThreshold}
        />
      </div>

      <div className="space-y-1.5 overflow-y-auto thin-scroll pr-1">
        {Object.entries(parameters).map(([key, p]) => {
          const band = threshold === "south_asian" ? p.south_asian : p.standard;
          const a = byKey[key];
          const tightened =
            p.south_asian[1] !== p.standard[1] && threshold === "south_asian";
          return (
            <div key={key} className="bg-white border border-twin-line rounded-lg px-3 py-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium">{p.label}</span>
                {tightened && (
                  <span className="text-[9px] font-mono text-twin-teal uppercase tracking-wide">SA</span>
                )}
              </div>
              <div className="flex items-center justify-between mt-0.5">
                <span className="font-mono text-[11px] text-twin-muted">
                  {fmt(band[0], key)}–{fmt(band[1], key)} {p.unit}
                </span>
                {a && (
                  <span
                    className={`font-mono text-xs font-semibold ${
                      a.in_range ? "text-twin-teal" : "text-twin-amber"
                    }`}
                  >
                    {fmt(a.value, key)}
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
