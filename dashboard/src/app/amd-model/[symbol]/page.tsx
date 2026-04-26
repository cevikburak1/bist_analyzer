"use client";

import Link from "next/link";
import { use } from "react";
import { ArrowLeft, Bell, Clock3, Crosshair, Gauge, Layers3, Target } from "lucide-react";
import { AnalysisStatusBanner } from "@/components/dashboard/analysis-status-banner";
import { AmdModelChart } from "@/components/stocks/amd-model-chart";
import { useAnalysisData } from "@/hooks/use-analysis-data";
import { formatDateTime, formatPrice } from "@/lib/formatters";
import type { StockDetailData } from "@/lib/types/report";

type PageProps = {
  params: Promise<{
    symbol: string;
  }>;
};

function Metric({ label, value, note }: { label: string; value: string; note: string }) {
  return (
    <div className="rounded border border-slate-800 bg-black/60 p-3">
      <div className="text-[10px] uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-1 text-xl font-black text-slate-100">{value}</div>
      <div className="mt-1 text-xs text-slate-500">{note}</div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-3 border-b border-slate-800 py-1.5 last:border-b-0">
      <span className="text-[10px] uppercase tracking-wide text-slate-500">{label}</span>
      <span className="text-right text-sm font-bold text-slate-100">{value}</span>
    </div>
  );
}

export default function AmdModelSymbolPage({ params }: PageProps) {
  const { symbol } = use(params);
  const { data, status, error, isLoading, reload } = useAnalysisData<StockDetailData>({ symbol });

  if (isLoading) {
    return <div className="flex min-h-screen items-center justify-center bg-black text-slate-100">AMD model grafiği yükleniyor...</div>;
  }

  if (!data || !data.signal.amd_model) {
    return <div className="flex min-h-screen items-center justify-center bg-black text-rose-300">{error || "AMD model detayı bulunamadı."}</div>;
  }

  const refreshNow = async () => {
    await fetch("/api/analysis/refresh", { method: "POST" });
    await reload();
  };

  const amd = data.signal.amd_model;
  const projectionEntries = Object.entries(amd.projections);

  return (
    <main className="min-h-screen bg-black px-6 py-6 text-slate-50">
      <div className="mx-auto max-w-[1700px] space-y-5">
        <AnalysisStatusBanner status={status} generatedAt={data.generated_at} onRefresh={refreshNow} />

        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <Link href="/amd-model" className="inline-flex items-center gap-2 text-sm text-cyan-300 hover:text-cyan-200">
              <ArrowLeft className="h-4 w-4" />
              AMD Model tablosuna dön
            </Link>
            <div className="mt-3 flex flex-wrap items-center gap-3">
              <h1 className="text-4xl font-black tracking-tight">{data.signal.symbol}</h1>
              <span className="rounded border border-cyan-500/40 bg-cyan-500/10 px-3 py-1 text-sm font-bold text-cyan-100">{amd.model_bias}</span>
              <span className="rounded border border-yellow-500/40 bg-yellow-500/10 px-3 py-1 text-sm font-bold text-yellow-100">{amd.phase}</span>
            </div>
            <p className="mt-2 text-sm text-slate-500">Son snapshot: {formatDateTime(data.generated_at)} | Fiyat: {formatPrice(data.signal.price)}</p>
          </div>
          <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
            <Metric label="AMD Skor" value={amd.score.toFixed(1)} note={amd.status} />
            <Metric label="Sweep" value={amd.sweep?.direction ?? "-"} note={amd.sweep?.liquidity_pool ?? "Sweep yok"} />
            <Metric label="CISD" value={amd.cisd?.confirmed ? "Onaylı" : "Bekliyor"} note={amd.cisd ? formatPrice(amd.cisd.level) : "Seviye yok"} />
            <Metric label="Interval" value={amd.interval} note={amd.timeframe} />
          </div>
        </div>

        <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_380px]">
          <AmdModelChart detail={data} />
          <aside className="space-y-3">
            <div className="rounded-[8px] border border-cyan-500/40 bg-[#03131a] p-3">
              <div className="mb-2 flex items-center gap-2 text-cyan-100">
                <Layers3 className="h-4 w-4" />
                <h2 className="text-sm font-black">AMD Döngüsü</h2>
              </div>
              <Row label="Status" value={amd.status} />
              <Row label="Model" value={amd.model_bias} />
              <Row label="Faz" value={amd.phase} />
              <Row label="Skor" value={amd.score.toFixed(1)} />
              <p className="mt-3 rounded bg-black/50 p-2 text-xs leading-5 text-slate-300">{amd.summary}</p>
            </div>

            <div className="rounded-[8px] border border-slate-800 bg-slate-950 p-3">
              <div className="mb-2 flex items-center gap-2 text-blue-100">
                <Crosshair className="h-4 w-4" />
                <h2 className="text-sm font-black">Accumulation / Manipulation</h2>
              </div>
              <Row label="A High" value={amd.accumulation ? formatPrice(amd.accumulation.high) : "-"} />
              <Row label="A Low" value={amd.accumulation ? formatPrice(amd.accumulation.low) : "-"} />
              <Row label="Sweep Price" value={amd.sweep ? formatPrice(amd.sweep.price) : "-"} />
              <Row label="Rejection" value={amd.sweep ? `${amd.sweep.rejection_pct.toFixed(1)}%` : "-"} />
            </div>

            <div className="rounded-[8px] border border-slate-800 bg-slate-950 p-3">
              <div className="mb-2 flex items-center gap-2 text-yellow-100">
                <Gauge className="h-4 w-4" />
                <h2 className="text-sm font-black">CISD ve Projections</h2>
              </div>
              <Row label="CISD Level" value={amd.cisd ? formatPrice(amd.cisd.level) : "-"} />
              <Row label="CISD Time" value={amd.cisd?.time ? formatDateTime(amd.cisd.time) : "-"} />
              {projectionEntries.length > 0 ? projectionEntries.map(([multiple, level]) => (
                <Row key={multiple} label={`${multiple} Projection`} value={formatPrice(level)} />
              )) : <div className="text-xs text-slate-500">Projection için CISD onayı bekleniyor.</div>}
            </div>

            <div className="rounded-[8px] border border-slate-800 bg-slate-950 p-3">
              <div className="mb-2 flex items-center gap-2 text-orange-100">
                <Target className="h-4 w-4" />
                <h2 className="text-sm font-black">Likidite ve HTF</h2>
              </div>
              <Row label="HTF Sweep" value={amd.htf_sweep?.direction ?? "-"} />
              <Row label="EQH" value={String(amd.equal_highs.length)} />
              <Row label="EQL" value={String(amd.equal_lows.length)} />
            </div>

            <div className="rounded-[8px] border border-slate-800 bg-slate-950 p-3">
              <div className="mb-2 flex items-center gap-2 text-slate-100">
                <Clock3 className="h-4 w-4" />
                <h2 className="text-sm font-black">Key Open Prices</h2>
              </div>
              <div className="space-y-2">
                {amd.key_opens.length > 0 ? amd.key_opens.map((item) => (
                  <div key={`${item.label}-${item.time}`} className="flex justify-between gap-3 rounded border border-slate-800 bg-black/60 px-2 py-1.5 text-xs">
                    <span className="text-slate-400">{item.label}</span>
                    <span className="font-bold text-slate-100">{formatPrice(item.price)}</span>
                  </div>
                )) : <div className="text-xs text-slate-500">Key open seviyesi yok.</div>}
              </div>
            </div>

            <div className="rounded-[8px] border border-slate-800 bg-slate-950 p-3">
              <div className="mb-2 flex items-center gap-2 text-rose-100">
                <Bell className="h-4 w-4" />
                <h2 className="text-sm font-black">Uyarılar</h2>
              </div>
              <div className="space-y-2">
                {amd.alerts.length > 0 ? amd.alerts.map((alert) => (
                  <div key={alert} className="rounded border border-slate-800 bg-black/60 px-2 py-1.5 text-xs text-slate-200">{alert}</div>
                )) : <div className="text-xs text-slate-500">Aktif AMD uyarısı yok.</div>}
              </div>
            </div>

            <p className="rounded-[8px] border border-slate-800 bg-slate-950 p-3 text-xs leading-5 text-slate-500">
              Bu model intraday OHLCV verisinden türetilmiş analitik bir okuma sağlar. TradingView indikatörü yerine geçmez ve finansal tavsiye değildir.
            </p>
          </aside>
        </div>
      </div>
    </main>
  );
}
