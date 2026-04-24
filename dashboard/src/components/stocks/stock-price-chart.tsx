"use client";

import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { formatCompactNumber, formatPrice } from "@/lib/formatters";
import type { StockDetailData } from "@/lib/types/report";

type StockPriceChartProps = {
  detail: StockDetailData;
};

export function StockPriceChart({ detail }: StockPriceChartProps) {
  const data = detail.series.map((point) => ({
    ...point,
    label: point.date.slice(5),
  }));

  return (
    <div className="grid gap-4">
      <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-4">
        <div className="mb-3">
          <h3 className="text-sm font-semibold text-slate-100">Fiyat ve Teknik Seviyeler</h3>
          <p className="text-xs text-slate-400">Son {data.length} bar uzerinden fiyat, ortalamalar, Bollinger ve hedef seviyeleri</p>
        </div>
        <div className="h-[360px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={data}>
              <CartesianGrid stroke="#1e293b" strokeDasharray="4 4" />
              <XAxis dataKey="label" tick={{ fill: "#94a3b8", fontSize: 12 }} />
              <YAxis tick={{ fill: "#94a3b8", fontSize: 12 }} tickFormatter={(value) => formatPrice(value)} />
              <Tooltip
                formatter={(value) => formatPrice(typeof value === "number" ? value : Number(value ?? 0))}
                contentStyle={{ backgroundColor: "#020617", borderColor: "#334155", borderRadius: 12 }}
                labelStyle={{ color: "#e2e8f0" }}
              />
              <Legend />
              <Bar dataKey="volume" name="Hacim" yAxisId={1} fill="#334155" opacity={0.25} />
              <YAxis yAxisId={1} hide />
              <Line type="monotone" dataKey="close" name="Kapanis" stroke="#22d3ee" dot={false} strokeWidth={2} />
              <Line type="monotone" dataKey="sma_short" name="SMA50" stroke="#f97316" dot={false} strokeWidth={1.5} />
              <Line type="monotone" dataKey="sma_long" name="SMA200" stroke="#eab308" dot={false} strokeWidth={1.5} />
              <Line type="monotone" dataKey="bb_upper" name="BB Ust" stroke="#64748b" dot={false} strokeWidth={1} />
              <Line type="monotone" dataKey="bb_lower" name="BB Alt" stroke="#64748b" dot={false} strokeWidth={1} />
              {detail.signal.targets.stop_loss > 0 ? (
                <ReferenceLine y={detail.signal.targets.stop_loss} stroke="#fb7185" strokeDasharray="6 6" label="Stop" />
              ) : null}
              {detail.signal.targets.short_target > 0 ? (
                <ReferenceLine y={detail.signal.targets.short_target} stroke="#34d399" strokeDasharray="4 4" label="Kisa" />
              ) : null}
              {detail.signal.targets.medium_target > 0 ? (
                <ReferenceLine y={detail.signal.targets.medium_target} stroke="#10b981" strokeDasharray="4 4" label="Orta" />
              ) : null}
              {detail.signal.targets.long_target > 0 ? (
                <ReferenceLine y={detail.signal.targets.long_target} stroke="#059669" strokeDasharray="4 4" label="Uzun" />
              ) : null}
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-4">
        <div className="mb-3">
          <h3 className="text-sm font-semibold text-slate-100">RSI ve Hacim</h3>
          <p className="text-xs text-slate-400">Momentum ve katilim degerlerini ayni pencerede izle</p>
        </div>
        <div className="h-[280px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={data}>
              <CartesianGrid stroke="#1e293b" strokeDasharray="4 4" />
              <XAxis dataKey="label" tick={{ fill: "#94a3b8", fontSize: 12 }} />
              <YAxis yAxisId="left" domain={[0, 100]} tick={{ fill: "#94a3b8", fontSize: 12 }} />
              <YAxis yAxisId="right" orientation="right" tick={{ fill: "#94a3b8", fontSize: 12 }} tickFormatter={(value) => formatCompactNumber(value)} />
              <Tooltip
                formatter={(value, name) =>
                  name === "RSI"
                    ? Number(value ?? 0).toFixed(2)
                    : formatCompactNumber(typeof value === "number" ? value : Number(value ?? 0))
                }
                contentStyle={{ backgroundColor: "#020617", borderColor: "#334155", borderRadius: 12 }}
                labelStyle={{ color: "#e2e8f0" }}
              />
              <Legend />
              <ReferenceLine yAxisId="left" y={70} stroke="#fb7185" strokeDasharray="4 4" />
              <ReferenceLine yAxisId="left" y={30} stroke="#34d399" strokeDasharray="4 4" />
              <Bar yAxisId="right" dataKey="volume" name="Hacim" fill="#475569" opacity={0.5} />
              <Line yAxisId="left" type="monotone" dataKey="rsi" name="RSI" stroke="#a855f7" dot={false} strokeWidth={2} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
