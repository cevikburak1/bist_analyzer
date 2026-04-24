/**
 * Vade Skor Kartı.
 * Tek bir vade icin: total skor, karar badge, tek-cumle reason,
 * kategori dokumu (her bir kategoride hangi faktor kac puan getirdi).
 */

import { ArrowRight, CheckCircle2 } from "lucide-react";
import type { HorizonScore } from "@/lib/types/report";

const DECISION_COLOR: Record<string, string> = {
  AL: "bg-emerald-500/15 text-emerald-200 border-emerald-500/30",
  SAT: "bg-rose-500/15 text-rose-200 border-rose-500/30",
  BEKLE: "bg-amber-500/15 text-amber-200 border-amber-500/30",
};

const SCORE_COLOR = (total: number): string => {
  if (total >= 65) return "text-emerald-300";
  if (total <= 35) return "text-rose-300";
  return "text-amber-200";
};

const CATEGORY_LABELS: Record<string, string> = {
  trend: "Trend",
  momentum: "Momentum",
  volume: "Hacim",
  price_position: "Fiyat Pozisyonu",
  regime: "Piyasa Rejimi",
};

type Props = {
  score: HorizonScore;
};

export function HorizonScoreCard({ score }: Props) {
  const decisionClass =
    DECISION_COLOR[score.decision] ?? "bg-slate-500/15 text-slate-200 border-slate-500/30";

  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5">
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div>
          <div className="text-xs uppercase tracking-wide text-slate-500">
            {score.label} Vade
          </div>
          <div className="mt-1 flex items-baseline gap-3">
            <span className={`text-3xl font-bold ${SCORE_COLOR(score.total)}`}>
              {score.total.toFixed(1)}
            </span>
            <span className="text-xs text-slate-500">/ 100</span>
            <span
              className={`inline-flex items-center rounded-full border px-3 py-1 text-xs font-semibold ${decisionClass}`}
            >
              {score.decision}
            </span>
          </div>
        </div>
      </div>

      <p className="mt-3 rounded-lg border border-slate-800 bg-slate-950/70 px-3 py-2 text-sm text-slate-200">
        {score.reason}
      </p>

      {score.targets ? (
        <div className="mt-3 rounded-lg border border-slate-800 bg-slate-950/40 p-3">
          <div className="flex items-center justify-between text-[11px] uppercase tracking-wide text-slate-500">
            <span>Vade Hedefleri</span>
            <span className={score.targets.direction === "LONG" ? "text-emerald-400" : score.targets.direction === "SHORT" ? "text-rose-400" : "text-slate-500"}>
              {score.targets.direction}
            </span>
          </div>
          <div className="mt-2 grid grid-cols-2 gap-3 text-xs md:grid-cols-4">
            <div>
              <div className="text-slate-500">Giris</div>
              <div className="text-slate-100">
                {score.targets.entry > 0 ? score.targets.entry.toFixed(2) : "-"}
              </div>
            </div>
            <div>
              <div className="text-slate-500">Stop</div>
              <div className="text-rose-300">
                {score.targets.stop_loss > 0 ? score.targets.stop_loss.toFixed(2) : "-"}
              </div>
              <div className="text-[10px] text-slate-500">
                Risk %{score.targets.risk_pct.toFixed(2)}
              </div>
            </div>
            <div>
              <div className="text-slate-500">Hedef</div>
              <div className="text-emerald-300">
                {score.targets.target_price > 0 ? score.targets.target_price.toFixed(2) : "-"}
              </div>
              <div className="text-[10px] text-slate-500">
                Getiri %{score.targets.reward_pct.toFixed(2)}
              </div>
            </div>
            <div>
              <div className="text-slate-500">R/O</div>
              <div className={score.targets.rr >= 1.5 ? "text-emerald-300" : "text-amber-300"}>
                {score.targets.rr.toFixed(2)}
              </div>
            </div>
          </div>
          {score.targets.note ? (
            <p className="mt-2 text-[11px] italic text-amber-300/80">
              {score.targets.note}
            </p>
          ) : null}
        </div>
      ) : null}

      {score.reason_factors && score.reason_factors.length > 0 ? (
        <div className="mt-3 space-y-1">
          <div className="text-[11px] uppercase tracking-wide text-slate-500">
            Karari Tetikleyen Faktorler
          </div>
          <ul className="space-y-1 text-xs text-slate-300">
            {score.reason_factors.map((f) => (
              <li key={f} className="flex items-start gap-1 rounded-lg bg-slate-950/50 px-2 py-1">
                <ArrowRight className="mt-0.5 h-3 w-3 shrink-0 text-slate-500" />
                <span>{f}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {Object.keys(score.categories ?? {}).length > 0 ? (
        <div className="mt-4 space-y-3">
          <div className="text-[11px] uppercase tracking-wide text-slate-500">
            Kategori Dokumu (Toplam {score.total.toFixed(1)} puan)
          </div>
          <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
            {Object.entries(score.categories).map(([key, cat]) => {
              const pct = cat.possible > 0 ? (cat.earned / cat.possible) * 100 : 0;
              return (
                <div
                  key={key}
                  className="rounded-lg border border-slate-800 bg-slate-950/40 p-3"
                >
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-medium text-slate-200">
                      {CATEGORY_LABELS[key] ?? key}
                    </span>
                    <span className="text-slate-300">
                      {cat.earned.toFixed(1)} / {cat.possible.toFixed(0)}
                    </span>
                  </div>
                  <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-slate-800">
                    <div
                      className="h-full rounded-full bg-cyan-500/60"
                      style={{ width: `${Math.min(100, Math.max(0, pct))}%` }}
                    />
                  </div>
                  {cat.factors && cat.factors.length > 0 ? (
                    <ul className="mt-2 space-y-1 text-[11px] text-slate-400">
                      {cat.factors.map((f) => (
                        <li key={f} className="flex items-start gap-1">
                          <CheckCircle2 className="mt-0.5 h-3 w-3 shrink-0 text-slate-600" />
                          <span>{f}</span>
                        </li>
                      ))}
                    </ul>
                  ) : null}
                </div>
              );
            })}
          </div>
        </div>
      ) : null}
    </div>
  );
}
