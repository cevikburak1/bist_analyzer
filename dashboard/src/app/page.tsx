"use client";

import { Minus, TrendingDown, TrendingUp } from "lucide-react";
import { AnalysisStatusBanner } from "@/components/dashboard/analysis-status-banner";
import { MetricCard } from "@/components/dashboard/metric-card";
import { StockTable } from "@/components/stocks/stock-table";
import { useAnalysisData } from "@/hooks/use-analysis-data";
import { useBuffettData } from "@/hooks/use-buffett-data";
import { formatDateTime } from "@/lib/formatters";
import type { BuffettListResponse } from "@/lib/types/buffett";
import type { ReportData } from "@/lib/types/report";

export default function Dashboard() {
  const { data, status, error, isLoading, reload } = useAnalysisData<ReportData>();
  const { data: fairData } = useBuffettData<BuffettListResponse>();

  if (isLoading) {
    return <div className="flex min-h-screen items-center justify-center bg-slate-950 text-slate-100">Yukleniyor...</div>;
  }

  if (!data) {
    return <div className="flex min-h-screen items-center justify-center bg-slate-950 text-rose-300">{error || "Veri bulunamadi."}</div>;
  }

  const regimeIcon =
    data.market_regime.regime === "YUKSELIS" ? (
      <TrendingUp className="h-4 w-4 text-emerald-300" />
    ) : data.market_regime.regime === "DUSUS" ? (
      <TrendingDown className="h-4 w-4 text-rose-300" />
    ) : (
      <Minus className="h-4 w-4 text-amber-200" />
    );

  const refreshNow = async () => {
    await fetch("/api/analysis/refresh", { method: "POST" });
    await reload();
  };

  const fairValueBySymbol = Object.fromEntries(
    (fairData?.items ?? []).map((item) => [
      item.symbol,
      {
        fairValue: item.fair_value,
        marginPct: item.fair_value_margin_pct,
        confidence: item.fair_value_confidence,
      },
    ]),
  );

  return (
    <div className="min-h-screen bg-slate-950 px-6 py-8 text-slate-50">
      <div className="mx-auto max-w-[1600px] space-y-6">
        <div className="flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">BIST Analiz Dashboard</h1>
            <p className="mt-1 text-sm text-slate-400">
              Son snapshot: {formatDateTime(data.generated_at)}
            </p>
          </div>
          <div className="text-sm text-slate-500">
            Basarili / istenen sembol: {data.meta.successful_symbols} / {data.meta.requested_symbols}
          </div>
        </div>

        <AnalysisStatusBanner status={status} generatedAt={data.generated_at} onRefresh={refreshNow} />

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
          <MetricCard
            title="Piyasa Rejimi"
            value={data.market_regime.label}
            description={`XU100 ${data.market_regime.index_price.toFixed(2)} | 20G ${data.market_regime.performance_20d.toFixed(2)}%`}
            icon={regimeIcon}
          />
          <MetricCard title="Toplam Hisse" value={data.summary.total} description="Guncel snapshot kapsamindaki toplam hisse" />
          <MetricCard title="AL Sinyali" value={<span className="text-emerald-300">{data.summary.buy}</span>} description="Gunluk AL sinyali ureten hisseler" />
          <MetricCard title="SAT Sinyali" value={<span className="text-rose-300">{data.summary.sell}</span>} description="Gunluk SAT sinyali ureten hisseler" />
        </div>

        <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5">
          <div className="mb-4">
            <h2 className="text-xl font-semibold text-slate-100">Tum Hisseler</h2>
            <p className="text-sm text-slate-400">
              Siralama, filtreleme, sayfalama ve detay sayfasina gecis buradan yonetilir.
            </p>
          </div>
          <StockTable signals={data.signals} fairValueBySymbol={fairValueBySymbol} />
        </div>
      </div>
    </div>
  );
}
