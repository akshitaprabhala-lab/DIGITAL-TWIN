import React from "react";
import { CircleCheck, TriangleAlert } from "lucide-react";

export default function AnalysisStrip({ analysis, scanSummary }) {
  const oor = (analysis || []).filter((a) => !a.in_range);
  const clean = oor.length === 0;
  return (
    <div
      data-testid="analysis-strip"
      className="bg-twin-stage/90 border border-twin-darkline rounded-lg px-3 py-2 backdrop-blur"
    >
      <div className="flex items-center gap-2">
        {clean ? (
          <CircleCheck className="h-4 w-4 text-twin-teal shrink-0" />
        ) : (
          <TriangleAlert className="h-4 w-4 text-twin-amber shrink-0" />
        )}
        <span className={`font-mono text-xs ${clean ? "text-twin-teal" : "text-twin-amber"}`}>
          {clean
            ? "All parameters in range"
            : `${oor.length} parameter${oor.length > 1 ? "s" : ""} out of range`}
        </span>
        <div className="flex flex-wrap gap-1.5 ml-1">
          {oor.map((a) => (
            <span key={a.key} className="text-[10px] font-mono text-zinc-400">
              {a.label} <span className="text-twin-amber">{a.side === "high" ? "↑" : "↓"}</span>
            </span>
          ))}
        </div>
      </div>
      {scanSummary && (
        <p className="text-[11px] text-zinc-400 mt-1.5 leading-relaxed">{scanSummary}</p>
      )}
    </div>
  );
}
