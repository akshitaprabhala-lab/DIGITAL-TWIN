import React from "react";

export default function Banner() {
  return (
    <div
      data-testid="research-banner"
      className="w-full bg-twin-amber text-black text-[11px] font-semibold uppercase tracking-widest px-4 py-1 text-center shrink-0"
    >
      Research prototype — not for clinical use. Simulations are illustrative.
    </div>
  );
}
