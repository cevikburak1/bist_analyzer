/**
 * 4 kategori puan kırılım çubukları + N/A göstergesi.
 */

import type { BuffettCategoryDetail, BuffettScoreBlock } from "@/lib/types/buffett";

type Props = { score: BuffettScoreBlock };

const CATEGORIES: { key: keyof Omit<BuffettScoreBlock, "total_score" | "data_quality_pct" | "has_minimum_data">; title: string; max: number }[] = [
  { key: "moat", title: "Moat / İş Kalitesi", max: 40 },
  { key: "financial_health", title: "Mali Sağlık", max: 25 },
  { key: "valuation", title: "Değerleme & MoS", max: 25 },
  { key: "shareholder_policy", title: "Hissedar Politikası", max: 10 },
];

function Bar({ cat, max }: { cat: BuffettCategoryDetail; max: number }) {
  if (cat.is_na) {
    return (
      <div className="flex h-2 w-full items-center rounded-full bg-slate-800">
        <span className="px-2 text-[10px] uppercase tracking-wider text-slate-500">N/A</span>
      </div>
    );
  }
  const possible = cat.possible || max;
  const pct = possible > 0 ? (cat.earned / possible) * 100 : 0;
  return (
    <div className="h-2 w-full overflow-hidden rounded-full bg-slate-800">
      <div
        className="h-full rounded-full bg-emerald-400/70"
        style={{ width: `${Math.min(100, pct)}%` }}
      />
    </div>
  );
}

export function ScoreBreakdown({ score }: Props) {
  return (
    <div className="space-y-4">
      {CATEGORIES.map((c) => {
        const cat = score[c.key] as BuffettCategoryDetail;
        const possible = cat.possible || c.max;
        return (
          <div key={c.key}>
            <div className="mb-1 flex items-center justify-between text-sm">
              <span className="text-slate-200">{c.title}</span>
              <span className="text-slate-400">
                {cat.is_na ? "N/A" : `${cat.earned.toFixed(1)} / ${possible.toFixed(0)}`}
              </span>
            </div>
            <Bar cat={cat} max={c.max} />
          </div>
        );
      })}
      <div className="border-t border-slate-800 pt-3 text-sm">
        <div className="flex items-center justify-between">
          <span className="text-slate-300">Veri Kalitesi</span>
          <span className="text-slate-400">{score.data_quality_pct.toFixed(0)}%</span>
        </div>
        <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-slate-800">
          <div
            className="h-full rounded-full bg-sky-400/60"
            style={{ width: `${Math.min(100, score.data_quality_pct)}%` }}
          />
        </div>
      </div>
    </div>
  );
}
