import React, { useMemo, useState } from "react";

// Curated pathway graphs per organ. Nodes carry a grid position (col,row).
// type: organ | mediator | param (param.id must match a PARAMETERS key).
const GRAPHS = {
  pancreas: {
    nodes: [
      { id: "pancreas", label: "Pancreas", type: "organ", col: 0, row: 1 },
      { id: "insulin", label: "Insulin", type: "mediator", col: 1, row: 0 },
      { id: "hepatic", label: "Hepatic glucose output", type: "mediator", col: 1, row: 2 },
      { id: "uptake", label: "Peripheral glucose uptake", type: "mediator", col: 2, row: 0 },
      { id: "fasting_glucose", label: "Fasting glucose", type: "param", col: 3, row: 1 },
      { id: "hba1c", label: "HbA1c", type: "param", col: 4, row: 1 },
    ],
    edges: [["pancreas", "insulin"], ["pancreas", "hepatic"], ["insulin", "uptake"],
      ["uptake", "fasting_glucose"], ["hepatic", "fasting_glucose"], ["fasting_glucose", "hba1c"]],
  },
  heart: {
    nodes: [
      { id: "heart", label: "Heart", type: "organ", col: 0, row: 0 },
      { id: "co", label: "Cardiac output", type: "mediator", col: 1, row: 0 },
      { id: "raas", label: "RAAS / SVR", type: "mediator", col: 1, row: 2 },
      { id: "map", label: "Mean arterial pressure", type: "mediator", col: 2, row: 1 },
      { id: "systolic_bp", label: "Systolic BP", type: "param", col: 3, row: 0 },
      { id: "diastolic_bp", label: "Diastolic BP", type: "param", col: 3, row: 2 },
    ],
    edges: [["heart", "co"], ["co", "map"], ["raas", "map"],
      ["map", "systolic_bp"], ["map", "diastolic_bp"]],
  },
  lungs: {
    nodes: [
      { id: "lungs", label: "Lungs", type: "organ", col: 0, row: 1 },
      { id: "exch", label: "Alveolar gas exchange", type: "mediator", col: 1, row: 1 },
      { id: "o2", label: "Arterial O₂", type: "mediator", col: 2, row: 1 },
      { id: "spo2", label: "SpO₂", type: "param", col: 3, row: 0 },
      { id: "chemo", label: "Chemoreceptor drive", type: "mediator", col: 3, row: 2 },
      { id: "heart_rate", label: "Heart rate", type: "param", col: 4, row: 2 },
    ],
    edges: [["lungs", "exch"], ["exch", "o2"], ["o2", "spo2"], ["o2", "chemo"], ["chemo", "heart_rate"]],
  },
  thyroid: {
    nodes: [
      { id: "pituitary", label: "Pituitary", type: "organ", col: 0, row: 0 },
      { id: "tsh", label: "TSH", type: "param", col: 1, row: 0 },
      { id: "thyroid", label: "Thyroid", type: "organ", col: 2, row: 0 },
      { id: "t4", label: "Free T4", type: "mediator", col: 3, row: 0 },
      { id: "bmr", label: "Basal metabolic rate", type: "mediator", col: 4, row: 0 },
      { id: "heart_rate", label: "Heart rate", type: "param", col: 5, row: 0 },
    ],
    edges: [["pituitary", "tsh"], ["tsh", "thyroid"], ["thyroid", "t4"],
      ["t4", "bmr"], ["bmr", "heart_rate"], ["t4", "tsh"]],
  },
  brain: {
    nodes: [
      { id: "brain", label: "Brain (autonomic)", type: "organ", col: 0, row: 1 },
      { id: "sns", label: "Sympathetic drive", type: "mediator", col: 1, row: 0 },
      { id: "tone", label: "Vascular tone", type: "mediator", col: 1, row: 2 },
      { id: "heart_rate", label: "Heart rate", type: "param", col: 2, row: 0 },
      { id: "systolic_bp", label: "Systolic BP", type: "param", col: 2, row: 2 },
    ],
    edges: [["brain", "sns"], ["brain", "tone"], ["sns", "heart_rate"], ["tone", "systolic_bp"]],
  },
  blood: {
    nodes: [
      { id: "iron", label: "Iron stores", type: "mediator", col: 0, row: 0 },
      { id: "marrow", label: "Bone marrow", type: "organ", col: 0, row: 2 },
      { id: "epo", label: "Erythropoiesis", type: "mediator", col: 1, row: 1 },
      { id: "hemoglobin", label: "Hemoglobin", type: "param", col: 2, row: 1 },
      { id: "o2cap", label: "O₂ carrying capacity", type: "mediator", col: 3, row: 1 },
    ],
    edges: [["iron", "epo"], ["marrow", "epo"], ["epo", "hemoglobin"], ["hemoglobin", "o2cap"]],
  },
  liver: {
    nodes: [
      { id: "liver", label: "Liver", type: "organ", col: 0, row: 0 },
      { id: "lp", label: "Lipoprotein metabolism", type: "mediator", col: 1, row: 0 },
      { id: "ldl", label: "LDL cholesterol", type: "param", col: 2, row: 0 },
    ],
    edges: [["liver", "lp"], ["lp", "ldl"]],
  },
  kidneys: {
    nodes: [
      { id: "kidneys", label: "Kidneys", type: "organ", col: 0, row: 0 },
      { id: "raas", label: "RAAS activity", type: "mediator", col: 1, row: 0 },
      { id: "na", label: "Na⁺ / water handling", type: "mediator", col: 2, row: 0 },
      { id: "systolic_bp", label: "Systolic BP", type: "param", col: 3, row: 0 },
    ],
    edges: [["kidneys", "raas"], ["raas", "na"], ["na", "systolic_bp"]],
  },
};

const COLW = 168;
const ROWH = 96;
const NW = 132;
const NH = 52;

function downstream(edges, start) {
  const set = new Set([start]);
  let frontier = [start];
  while (frontier.length) {
    const next = [];
    for (const n of frontier) {
      for (const [a, b] of edges) {
        if (a === n && !set.has(b)) { set.add(b); next.push(b); }
      }
    }
    frontier = next;
  }
  return set;
}

export default function PhysiologyMap({ organKeys = [], organs = {}, analysis = [] }) {
  const available = organKeys.filter((o) => GRAPHS[o]);
  const [organ, setOrgan] = useState(available[0] || "pancreas");
  const [active, setActive] = useState(null);
  const graph = GRAPHS[organ] || GRAPHS.pancreas;
  const byKey = useMemo(() => Object.fromEntries(analysis.map((a) => [a.key, a])), [analysis]);

  const activeSet = active ? downstream(graph.edges, active) : null;
  const maxCol = Math.max(...graph.nodes.map((n) => n.col));
  const maxRow = Math.max(...graph.nodes.map((n) => n.row));
  const W = (maxCol + 1) * COLW;
  const H = (maxRow + 1) * ROWH;
  const pos = (n) => ({ x: n.col * COLW + (COLW - NW) / 2, y: n.row * ROWH + (ROWH - NH) / 2 });
  const center = (n) => { const p = pos(n); return { x: p.x + NW / 2, y: p.y + NH / 2 }; };
  const nodeById = Object.fromEntries(graph.nodes.map((n) => [n.id, n]));

  const nodeFill = (n) => {
    if (n.type === "organ") return "#0D9488";
    if (n.type === "param") {
      const a = byKey[n.id];
      return a && !a.in_range ? "#D97706" : "#0f766e";
    }
    return "#3f3f46";
  };

  return (
    <div>
      {available.length > 1 && (
        <div className="flex gap-1.5 mb-3">
          {available.map((o) => (
            <button
              key={o}
              data-testid={`physmap-organ-${o}`}
              onClick={() => { setOrgan(o); setActive(null); }}
              className={`text-xs font-mono px-2.5 py-1 rounded-full border transition-colors ${
                organ === o ? "bg-twin-teal text-white border-twin-teal"
                            : "bg-white text-twin-muted border-twin-line hover:border-twin-teal"
              }`}
            >
              {organs[o]?.label || o}
            </button>
          ))}
        </div>
      )}

      <div className="bg-twin-stage rounded-lg border border-twin-darkline p-3 overflow-x-auto">
        <svg viewBox={`0 0 ${W} ${H}`} width="100%" height={H} data-testid="physmap-svg"
          style={{ minWidth: W }}>
          <defs>
            <marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
              <path d="M0,0 L8,4 L0,8 Z" fill="#52525b" />
            </marker>
            <marker id="arrow-on" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
              <path d="M0,0 L8,4 L0,8 Z" fill="#0D9488" />
            </marker>
          </defs>
          {graph.edges.map(([a, b], i) => {
            const na = nodeById[a], nb = nodeById[b];
            if (!na || !nb) return null;
            const ca = center(na), cb = center(nb);
            const on = activeSet && activeSet.has(a) && activeSet.has(b);
            const dim = activeSet && !on;
            const x1 = ca.x + (cb.x > ca.x ? NW / 2 : -NW / 2);
            const x2 = cb.x + (cb.x > ca.x ? -NW / 2 : NW / 2);
            return (
              <path key={i} d={`M${x1},${ca.y} C${(x1 + x2) / 2},${ca.y} ${(x1 + x2) / 2},${cb.y} ${x2},${cb.y}`}
                fill="none" stroke={on ? "#0D9488" : "#3f3f46"} strokeWidth={on ? 2 : 1.3}
                opacity={dim ? 0.2 : 1} markerEnd={`url(#${on ? "arrow-on" : "arrow"})`} />
            );
          })}
          {graph.nodes.map((n) => {
            const p = pos(n);
            const a = byKey[n.id];
            const dim = activeSet && !activeSet.has(n.id);
            const isActive = active === n.id;
            return (
              <g key={n.id} data-testid={`physmap-node-${n.id}`}
                onClick={() => setActive(isActive ? null : n.id)}
                style={{ cursor: "pointer", opacity: dim ? 0.3 : 1 }}>
                <rect x={p.x} y={p.y} width={NW} height={NH} rx={9}
                  fill={nodeFill(n)} stroke={isActive ? "#fff" : "transparent"} strokeWidth={1.5} />
                <text x={p.x + NW / 2} y={p.y + (n.type === "param" && a ? 20 : NH / 2 + 4)}
                  textAnchor="middle" fontSize="11" fill="#fff" fontFamily="IBM Plex Sans"
                  style={{ fontWeight: 500 }}>
                  {n.label.length > 20 ? n.label.slice(0, 19) + "…" : n.label}
                </text>
                {n.type === "param" && a && (
                  <text x={p.x + NW / 2} y={p.y + 38} textAnchor="middle" fontSize="12"
                    fill="#fff" fontFamily="IBM Plex Mono" style={{ fontWeight: 600 }}>
                    {a.value} {a.unit}
                  </text>
                )}
              </g>
            );
          })}
        </svg>
      </div>
      <p className="text-[11px] text-twin-muted mt-2 font-mono">
        {active ? "Highlighting the downstream pathway. Click again to reset." : "Click any node to trace its downstream pathway."}
        {"  ·  "}<span className="text-twin-teal">teal</span> in-range param ·{" "}
        <span className="text-twin-amber">amber</span> out-of-range param
      </p>
    </div>
  );
}
