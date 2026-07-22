import React from "react";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import {
  Stethoscope, Share2, Sliders, Pill, Waypoints,
} from "lucide-react";

const MODES = [
  { id: "diseases", label: "Diseases", icon: Stethoscope },
  { id: "physiology", label: "Physiology links", icon: Share2 },
  { id: "parameters", label: "Parameters", icon: Sliders },
  { id: "drugs", label: "Drugs", icon: Pill },
];

export default function TopSearchBar({
  mode, setMode, catalog, conditions, onToggleDisease,
  activeDrug, onSelectDrug, onEditParams, onOpenPhysMap, selectedRegion, organs,
}) {
  return (
    <div className="flex items-center gap-3">
      {/* segmented mode control */}
      <div className="flex items-center bg-twin-panel border border-twin-line rounded-lg p-0.5">
        {MODES.map((m) => {
          const Icon = m.icon;
          const on = mode === m.id;
          return (
            <button
              key={m.id}
              data-testid={`mode-${m.id}`}
              onClick={() => setMode(m.id)}
              className={`flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-md transition-colors ${
                on ? "bg-twin-teal text-white" : "text-twin-muted hover:text-twin-ink"
              }`}
            >
              <Icon className="h-3.5 w-3.5" /> {m.label}
            </button>
          );
        })}
      </div>

      {/* contextual control */}
      <div className="flex-1 min-w-[220px]">
        {mode === "diseases" && (
          <Select onValueChange={onToggleDisease}>
            <SelectTrigger data-testid="disease-select" className="bg-white border-twin-line h-9">
              <SelectValue placeholder="Add / remove a condition…" />
            </SelectTrigger>
            <SelectContent>
              {(catalog?.diseases || []).map((d) => (
                <SelectItem key={d.id} value={d.id}>
                  {conditions.includes(d.id) ? "✓ " : ""}{d.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}

        {mode === "drugs" && (
          <Select value={activeDrug?.id || ""} onValueChange={onSelectDrug}>
            <SelectTrigger data-testid="drug-select" className="bg-white border-twin-line h-9">
              <SelectValue placeholder="Pick a drug to test on the twin…" />
            </SelectTrigger>
            <SelectContent>
              {(catalog?.drugs || []).map((d) => (
                <SelectItem key={d.id} value={d.id}>{d.name} · {d.unit}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}

        {mode === "parameters" && (
          <Button data-testid="edit-params-btn" variant="outline" onClick={onEditParams}
            className="h-9 border-twin-line">
            <Sliders className="h-4 w-4" /> Edit this patient's parameters
          </Button>
        )}

        {mode === "physiology" && (
          <Button data-testid="physiology-btn" variant="outline" onClick={onOpenPhysMap}
            className="h-9 border-twin-line">
            <Waypoints className="h-4 w-4" />
            {selectedRegion ? `Open physiology map · ${selectedRegion}` : "Select a body region, then open the map"}
          </Button>
        )}
      </div>
    </div>
  );
}
