"use client";

import { useEffect, useState } from "react";
import { HorizonScoreCard } from "@/components/shared/horizon-score-card";
import { HORIZON_OPTIONS, useHorizon } from "@/lib/horizon-context";
import type { HorizonKey, HorizonScoreSet } from "@/lib/types/report";

type Props = {
  scores: HorizonScoreSet;
};

const DECISION_BADGE: Record<string, string> = {
  AL: "bg-emerald-500/15 text-emerald-200 border-emerald-500/30",
  SAT: "bg-rose-500/15 text-rose-200 border-rose-500/30",
  BEKLE: "bg-amber-500/15 text-amber-200 border-amber-500/30",
};

export function HorizonScoresPanel({ scores }: Props) {
  const { horizon, setHorizon } = useHorizon();
  const [activeTab, setActiveTab] = useState<HorizonKey>(horizon);

  useEffect(() => {
    setActiveTab(horizon);
  }, [horizon]);

  const handleSelect = (h: HorizonKey) => {
    setActiveTab(h);
    setHorizon(h);
  };

  const active = scores[activeTab];

  return (
    <div className="space-y-4">
      <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-slate-100">
              Vade Bazli Skor ve Karar
            </h2>
            <p className="text-xs text-slate-500">
              Her vade icin ayri puanlama, ayri AL/SAT/BEKLE karari ve neden listesi.
            </p>
          </div>
        </div>

        <div className="mt-3 grid grid-cols-2 gap-2 md:grid-cols-4">
          {HORIZON_OPTIONS.map((opt) => {
            const s = scores[opt.value];
            const isActive = opt.value === activeTab;
            const badge =
              DECISION_BADGE[s.decision] ?? "bg-slate-500/15 text-slate-200 border-slate-500/30";
            return (
              <button
                key={opt.value}
                type="button"
                onClick={() => handleSelect(opt.value)}
                className={`rounded-xl border px-3 py-3 text-left transition ${
                  isActive
                    ? "border-cyan-500/50 bg-cyan-500/10"
                    : "border-slate-800 bg-slate-950/40 hover:border-slate-700"
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs uppercase tracking-wide text-slate-400">
                    {opt.label}
                  </span>
                  <span
                    className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-semibold ${badge}`}
                  >
                    {s.decision}
                  </span>
                </div>
                <div className="mt-1 text-2xl font-bold text-slate-100">
                  {s.total.toFixed(1)}
                </div>
                <div className="text-[10px] text-slate-500">{opt.subtitle}</div>
              </button>
            );
          })}
        </div>
      </div>

      <HorizonScoreCard score={active} />
    </div>
  );
}
