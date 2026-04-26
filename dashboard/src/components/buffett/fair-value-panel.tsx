"use client";

import type { FairValueBlock } from "@/lib/types/buffett";
import { formatCompactNumber, formatPrice } from "@/lib/formatters";

type Props = {
  fairValue: FairValueBlock;
};

function pct(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  return `${value >= 0 ? "+" : ""}${value.toFixed(1)}%`;
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-3 border-b border-slate-800 py-1.5 last:border-b-0">
      <span className="text-[10px] uppercase tracking-wide text-slate-500">{label}</span>
      <span className="text-right text-sm font-bold text-slate-100">{value}</span>
    </div>
  );
}

export function FairValuePanel({ fairValue }: Props) {
  const methods = Object.entries(fairValue.methods);
  const margin = fairValue.margin_pct ?? 0;
  const bandTop = (fairValue.fair_value ?? 0) * 1.2;
  const bandBottom = (fairValue.fair_value ?? 0) * 0.8;

  return (
    <div className="space-y-4">
      <div className="rounded-[10px] border border-blue-500/30 bg-slate-950 p-4">
        <div className="mb-3 rounded bg-blue-600 px-3 py-1 text-center text-xs font-black uppercase tracking-wide text-white">
          Adil Değer v3.7.1 · Analysis Panel
        </div>
        <div className="grid grid-cols-3 gap-2">
          <div className="rounded border border-slate-800 bg-black/60 p-3">
            <div className="text-[10px] text-slate-500">Fair Value</div>
            <div className="mt-1 text-2xl font-black text-blue-100">{formatPrice(fairValue.fair_value)}</div>
          </div>
          <div className="rounded border border-slate-800 bg-black/60 p-3">
            <div className="text-[10px] text-slate-500">Price</div>
            <div className="mt-1 text-2xl font-black text-slate-100">{formatPrice(fairValue.current_price)}</div>
          </div>
          <div className="rounded border border-slate-800 bg-black/60 p-3">
            <div className="text-[10px] text-slate-500">MoS</div>
            <div className={`mt-1 text-2xl font-black ${margin >= 20 ? "text-emerald-300" : margin <= -20 ? "text-rose-300" : "text-yellow-200"}`}>{pct(margin)}</div>
          </div>
        </div>
        <div className="mt-3">
          <Row label="Market" value={`${fairValue.market} · ${fairValue.currency}`} />
          <Row label="Rate / Inflation" value={`${fairValue.bond_benchmark} · ${fairValue.inflation_region}`} />
          <Row label="Sector" value={fairValue.sector_label} />
          <Row label="Method" value={fairValue.aggregation_method} />
          <Row label="Forward EPS" value={fairValue.forward_eps_source} />
          <Row label="Confidence" value={`${fairValue.confidence_label}${fairValue.confidence_cv ? ` (${fairValue.confidence_cv.toFixed(1)}%)` : ""}`} />
        </div>
      </div>

      <div className="rounded-[10px] border border-slate-800 bg-black p-4">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-bold text-slate-100">Discount / Premium Bands</h2>
          <span className="text-xs text-slate-500">±20%</span>
        </div>
        <div className="relative h-28 rounded border border-slate-800 bg-slate-950">
          <div className="absolute left-0 right-0 top-0 h-1/3 bg-rose-500/10" />
          <div className="absolute left-0 right-0 bottom-0 h-1/3 bg-emerald-500/10" />
          <div className="absolute left-3 right-3 top-1/2 border-t border-blue-400" />
          <div className="absolute right-3 top-2 text-xs text-rose-200">Premium {formatPrice(bandTop)}</div>
          <div className="absolute right-3 top-1/2 -translate-y-5 text-xs text-blue-200">Fair {formatPrice(fairValue.fair_value)}</div>
          <div className="absolute right-3 bottom-2 text-xs text-emerald-200">Discount {formatPrice(bandBottom)}</div>
        </div>
      </div>

      <div className="rounded-[10px] border border-slate-800 bg-slate-950 p-4">
        <h2 className="mb-3 text-sm font-bold text-slate-100">10 Valuation Methods</h2>
        <div className="grid gap-2 md:grid-cols-2">
          {methods.map(([key, method]) => (
            <div key={key} className="rounded border border-slate-800 bg-black/60 p-3">
              <div className="flex justify-between gap-3">
                <span className="text-xs text-slate-400">{method.label}</span>
                <span className="text-sm font-bold text-slate-100">{formatPrice(method.value)}</span>
              </div>
              <div className="mt-1 flex justify-between text-[10px] text-slate-500">
                <span>{method.source}</span>
                <span>w {method.weight.toFixed(2)}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="rounded-[10px] border border-slate-800 bg-slate-950 p-4">
        <h2 className="mb-3 text-sm font-bold text-slate-100">8 Quarter Financials</h2>
        <div className="overflow-auto">
          <table className="w-full text-xs">
            <thead className="bg-black text-slate-500">
              <tr>
                <th className="px-2 py-2 text-left">Period</th>
                <th className="px-2 py-2 text-right">Net</th>
                <th className="px-2 py-2 text-right">Revenue</th>
                <th className="px-2 py-2 text-right">EBIT</th>
                <th className="px-2 py-2 text-right">FCF</th>
                <th className="px-2 py-2 text-right">ROE</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {fairValue.financials_table.map((row, index) => (
                <tr key={`${row.period ?? "period"}-${index}`} className="bg-black/40">
                  <td className="px-2 py-2 text-slate-300">{row.period ?? "-"}</td>
                  <td className="px-2 py-2 text-right text-slate-300">{formatCompactNumber(row.net_earnings)}</td>
                  <td className="px-2 py-2 text-right text-slate-300">{formatCompactNumber(row.revenue)}</td>
                  <td className="px-2 py-2 text-right text-slate-300">{formatCompactNumber(row.ebit)}</td>
                  <td className="px-2 py-2 text-right text-slate-300">{formatCompactNumber(row.fcf)}</td>
                  <td className="px-2 py-2 text-right text-slate-300">{row.roe === null ? "-" : `${(row.roe * 100).toFixed(1)}%`}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
