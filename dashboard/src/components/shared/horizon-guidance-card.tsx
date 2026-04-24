/**
 * Vade Bazlı Tutma Önerisi Kartı (Kısa / Orta / Uzun).
 *
 * Hem teknik (TechnicalHorizonGuidance) hem Buffett (BuffettHorizonGuidance)
 * çıktısını render eder. Her iki sistemde de iki shape benzer; bu nedenle
 * polimorfik tipi yerine düz bir adapter beklenir.
 */

import { ArrowRight } from "lucide-react";

const VERDICT_COLOR_MAP: Record<string, string> = {
  emerald: "bg-emerald-500/15 text-emerald-200 border-emerald-500/30",
  lime: "bg-lime-500/15 text-lime-200 border-lime-500/30",
  teal: "bg-teal-500/15 text-teal-200 border-teal-500/30",
  sky: "bg-sky-500/15 text-sky-200 border-sky-500/30",
  slate: "bg-slate-500/15 text-slate-200 border-slate-500/30",
  amber: "bg-amber-500/15 text-amber-200 border-amber-500/30",
  rose: "bg-rose-500/15 text-rose-200 border-rose-500/30",
  zinc: "bg-zinc-500/15 text-zinc-200 border-zinc-500/30",
};

export type HorizonRow = {
  label: string;
  verdict: string;
  color: string;
  reason: string;
  factors?: string[];
  rr?: number | null;
  targetPrice?: number | null;
  rewardPct?: number | null;
};

type Props = {
  title: string;
  description?: string;
  short: HorizonRow;
  medium: HorizonRow;
  long: HorizonRow;
  overall?: string;
};

export function HorizonGuidanceCard({
  title,
  description,
  short,
  medium,
  long,
  overall,
}: Props) {
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-slate-100">{title}</h2>
          {description ? (
            <p className="mt-1 text-xs text-slate-500">{description}</p>
          ) : null}
        </div>
      </div>

      {overall ? (
        <p className="mt-3 rounded-lg border border-slate-800 bg-slate-950/70 px-3 py-2 text-sm text-slate-300">
          {overall}
        </p>
      ) : null}

      <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-3">
        <HorizonBlock title="Kısa Vade" subtitle="1-4 hafta" row={short} />
        <HorizonBlock title="Orta Vade" subtitle="1-6 ay" row={medium} />
        <HorizonBlock title="Uzun Vade" subtitle="6 ay - 5+ yıl" row={long} />
      </div>
    </div>
  );
}

function HorizonBlock({
  title,
  subtitle,
  row,
}: {
  title: string;
  subtitle: string;
  row: HorizonRow;
}) {
  const colorClasses =
    VERDICT_COLOR_MAP[row.color] ?? VERDICT_COLOR_MAP.slate;

  return (
    <div className="flex flex-col gap-2 rounded-xl border border-slate-800 bg-slate-950/40 p-3">
      <div className="flex items-center justify-between text-xs uppercase tracking-wide text-slate-500">
        <span>{title}</span>
        <span className="text-[10px] text-slate-600">{subtitle}</span>
      </div>

      <div
        className={`inline-flex w-fit items-center rounded-full border px-2 py-0.5 text-xs font-semibold ${colorClasses}`}
      >
        {row.verdict}
      </div>

      <div className="text-sm font-medium text-slate-100">{row.label}</div>

      <p className="text-xs leading-5 text-slate-300">{row.reason}</p>

      {(row.rr !== null && row.rr !== undefined) ||
      (row.targetPrice !== null && row.targetPrice !== undefined) ? (
        <div className="mt-1 grid grid-cols-2 gap-2 rounded-lg bg-slate-900/60 p-2 text-[11px] text-slate-400">
          {row.targetPrice !== null && row.targetPrice !== undefined ? (
            <div>
              <div className="uppercase tracking-wide text-slate-500">Hedef</div>
              <div className="text-slate-200">{row.targetPrice.toFixed(2)}</div>
            </div>
          ) : null}
          {row.rr !== null && row.rr !== undefined ? (
            <div>
              <div className="uppercase tracking-wide text-slate-500">R/O</div>
              <div className="text-slate-200">{row.rr.toFixed(2)}</div>
            </div>
          ) : null}
          {row.rewardPct !== null && row.rewardPct !== undefined ? (
            <div className="col-span-2">
              <div className="uppercase tracking-wide text-slate-500">
                Beklenen Getiri
              </div>
              <div className="text-emerald-200">{row.rewardPct.toFixed(2)}%</div>
            </div>
          ) : null}
        </div>
      ) : null}

      {row.factors && row.factors.length > 0 ? (
        <ul className="mt-1 space-y-1 text-[11px] text-slate-400">
          {row.factors.map((f) => (
            <li key={f} className="flex items-start gap-1">
              <ArrowRight className="mt-0.5 h-3 w-3 shrink-0 text-slate-500" />
              <span>{f}</span>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
