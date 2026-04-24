"use client";

/**
 * 5 yıllık temel veri grafikleri (fiyat değil!).
 * - ROE
 * - Net kâr & gelir
 * - Serbest nakit akışı
 * - Borç/Özsermaye
 *
 * recharts kullanır.
 */

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { BuffettHistory } from "@/lib/types/buffett";

type Props = { history: BuffettHistory };

const AXIS_PROPS = {
  stroke: "#475569",
  fontSize: 11,
};

const TOOLTIP_STYLE = {
  backgroundColor: "#0f172a",
  border: "1px solid #1e293b",
  color: "#e2e8f0",
  fontSize: 12,
};

function formatYear(period: string | null) {
  if (!period) return "-";
  return period.length >= 4 ? period.slice(0, 4) : period;
}

function formatBig(v: number) {
  if (Math.abs(v) >= 1e9) return `${(v / 1e9).toFixed(1)}B`;
  if (Math.abs(v) >= 1e6) return `${(v / 1e6).toFixed(1)}M`;
  if (Math.abs(v) >= 1e3) return `${(v / 1e3).toFixed(1)}K`;
  return v.toFixed(0);
}

function formatPct(v: number) {
  return `${(v * 100).toFixed(1)}%`;
}

function tooltipBig(v: unknown): string {
  return typeof v === "number" ? formatBig(v) : "-";
}

function tooltipPct(v: unknown): string {
  return typeof v === "number" ? formatPct(v) : "-";
}

function tooltipFixed2(v: unknown): string {
  return typeof v === "number" ? v.toFixed(2) : "-";
}

export function HistoryCharts({ history }: Props) {
  const roeData = history.roe
    .filter((p) => p.roe !== null && p.roe !== undefined)
    .map((p) => ({ year: formatYear(p.period), roe: p.roe! }));

  const incomeData = history.net_income.map((p, i) => ({
    year: formatYear(p.period),
    net_income: p.value ?? null,
    revenue: history.revenue[i]?.value ?? null,
  }));

  const fcfData = history.free_cash_flow
    .filter((p) => p.value !== null && p.value !== undefined)
    .map((p) => ({ year: formatYear(p.period), fcf: p.value! }));

  const deData = history.debt_to_equity
    .filter((p) => p.value !== null && p.value !== undefined)
    .map((p) => ({ year: formatYear(p.period), de: p.value! }));

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
      <ChartCard title="ROE (Özsermaye Karlılığı) - 5 Yıl" subtitle="Buffett: > %15 sürdürülebilir = harika">
        {roeData.length === 0 ? (
          <Empty />
        ) : (
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={roeData}>
              <CartesianGrid stroke="#1e293b" strokeDasharray="3 3" />
              <XAxis dataKey="year" {...AXIS_PROPS} />
              <YAxis tickFormatter={formatPct} {...AXIS_PROPS} />
              <Tooltip
                contentStyle={TOOLTIP_STYLE}
                formatter={tooltipPct}
              />
              <Bar dataKey="roe" radius={[4, 4, 0, 0]}>
                {roeData.map((d, i) => (
                  <Cell key={i} fill={d.roe >= 0.15 ? "#34d399" : d.roe >= 0 ? "#fbbf24" : "#fb7185"} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}
      </ChartCard>

      <ChartCard title="Gelir & Net Kâr - 5 Yıl" subtitle="Tutarlı büyüyen şirket Buffett'ın aradığıdır">
        {incomeData.length === 0 ? (
          <Empty />
        ) : (
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={incomeData}>
              <CartesianGrid stroke="#1e293b" strokeDasharray="3 3" />
              <XAxis dataKey="year" {...AXIS_PROPS} />
              <YAxis tickFormatter={formatBig} {...AXIS_PROPS} />
              <Tooltip
                contentStyle={TOOLTIP_STYLE}
                formatter={tooltipBig}
              />
              <Legend wrapperStyle={{ fontSize: 11, color: "#94a3b8" }} />
              <Line type="monotone" dataKey="revenue" stroke="#60a5fa" strokeWidth={2} name="Gelir" dot={false} />
              <Line type="monotone" dataKey="net_income" stroke="#34d399" strokeWidth={2} name="Net Kâr" dot={false} />
            </LineChart>
          </ResponsiveContainer>
        )}
      </ChartCard>

      <ChartCard title="Serbest Nakit Akışı - 5 Yıl" subtitle="Buffett'ın asıl bakacağı kalem; pozitif ve büyümeli">
        {fcfData.length === 0 ? (
          <Empty />
        ) : (
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={fcfData}>
              <CartesianGrid stroke="#1e293b" strokeDasharray="3 3" />
              <XAxis dataKey="year" {...AXIS_PROPS} />
              <YAxis tickFormatter={formatBig} {...AXIS_PROPS} />
              <Tooltip
                contentStyle={TOOLTIP_STYLE}
                formatter={tooltipBig}
              />
              <Bar dataKey="fcf" radius={[4, 4, 0, 0]}>
                {fcfData.map((d, i) => (
                  <Cell key={i} fill={d.fcf >= 0 ? "#34d399" : "#fb7185"} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}
      </ChartCard>

      <ChartCard title="Borç / Özsermaye - 5 Yıl" subtitle="Düşük ve istikrarlı = sağlam bilanço">
        {deData.length === 0 ? (
          <Empty />
        ) : (
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={deData}>
              <CartesianGrid stroke="#1e293b" strokeDasharray="3 3" />
              <XAxis dataKey="year" {...AXIS_PROPS} />
              <YAxis {...AXIS_PROPS} />
              <Tooltip
                contentStyle={TOOLTIP_STYLE}
                formatter={tooltipFixed2}
              />
              <Line type="monotone" dataKey="de" stroke="#f59e0b" strokeWidth={2} dot />
            </LineChart>
          </ResponsiveContainer>
        )}
      </ChartCard>
    </div>
  );
}

function ChartCard({ title, subtitle, children }: { title: string; subtitle: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
      <div className="mb-3">
        <h3 className="text-sm font-semibold text-slate-100">{title}</h3>
        <p className="text-xs text-slate-500">{subtitle}</p>
      </div>
      {children}
    </div>
  );
}

function Empty() {
  return (
    <div className="flex h-[220px] items-center justify-center text-xs text-slate-500">
      Veri yok
    </div>
  );
}
