"use client";

import Link from "next/link";
import { use } from "react";
import { ArrowLeft, Bell, Ruler, Target, Trophy } from "lucide-react";
import { AnalysisStatusBanner } from "@/components/dashboard/analysis-status-banner";
import { CupHandleChart } from "@/components/stocks/cup-handle-chart";
import { useAnalysisData } from "@/hooks/use-analysis-data";
import { formatDateTime, formatPrice } from "@/lib/formatters";
import type { StockDetailData } from "@/lib/types/report";

type PageProps = {
  params: Promise<{
    symbol: string;
  }>;
};

function Metric({ label, value, tone = "text-slate-100" }: { label: string; value: string; tone?: string }) {
  return (
    <div className="rounded border border-slate-800 bg-black/60 p-3">
      <div className="text-[10px] uppercase tracking-wide text-slate-500">{label}</div>
      <div className={`mt-1 text-xl font-black ${tone}`}>{value}</div>
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

export default function CupHandleQualitySymbolPage({ params }: PageProps) {
  const { symbol } = use(params);
  const { data, status, error, isLoading, reload } = useAnalysisData<StockDetailData>({ symbol });

  if (isLoading) {
    return <div className="flex min-h-screen items-center justify-center bg-black text-slate-100">Cup & Handle detayı yükleniyor...</div>;
  }

  if (!data || !data.signal.cup_handle_quality) {
    return <div className="flex min-h-screen items-center justify-center bg-black text-rose-300">{error || "Cup & Handle detayı bulunamadı."}</div>;
  }

  const refreshNow = async () => {
    await fetch("/api/analysis/refresh", { method: "POST" });
    await reload();
  };

  const cup = data.signal.cup_handle_quality;

  return (
    <main className="min-h-screen bg-black px-6 py-6 text-slate-50">
      <div className="mx-auto max-w-[1700px] space-y-5">
        <AnalysisStatusBanner status={status} generatedAt={data.generated_at} onRefresh={refreshNow} />

        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <Link href="/cup-handle-quality" className="inline-flex items-center gap-2 text-sm text-cyan-300 hover:text-cyan-200">
              <ArrowLeft className="h-4 w-4" />
              Cup & Handle tablosuna dön
            </Link>
            <div className="mt-3 flex flex-wrap items-center gap-3">
              <h1 className="text-4xl font-black tracking-tight">{data.signal.symbol}</h1>
              <span className="rounded border border-blue-500/40 bg-blue-500/10 px-3 py-1 text-sm font-bold text-blue-100">{cup.status}</span>
              <span className="rounded border border-emerald-500/40 bg-emerald-500/10 px-3 py-1 text-sm font-bold text-emerald-100">{cup.score ?? "-"} Score</span>
            </div>
            <p className="mt-2 text-sm text-slate-500">Son snapshot: {formatDateTime(data.generated_at)} | Fiyat: {formatPrice(data.signal.price)}</p>
          </div>
          <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
            <Metric label="Cup Symmetry" value={cup.cup_symmetry?.toFixed(0) ?? "-"} />
            <Metric label="Handle Depth" value={cup.handle_depth_pct !== null ? `${cup.handle_depth_pct?.toFixed(1)}%` : "-"} />
            <Metric label="Breakout Quality" value={cup.breakout_quality?.toFixed(0) ?? "-"} />
            <Metric label="Target" value={formatPrice(cup.target_price)} tone="text-emerald-200" />
          </div>
        </div>

        <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
          <CupHandleChart detail={data} />
          <aside className="space-y-3">
            <div className="rounded-[8px] border border-blue-500/40 bg-slate-950 p-3">
              <div className="mb-2 flex items-center gap-2 text-blue-100">
                <Trophy className="h-4 w-4" />
                <h2 className="text-sm font-black">AGPro Quality Panel</h2>
              </div>
              <Row label="Cup Symmetry" value={cup.cup_symmetry?.toFixed(1) ?? "Waiting"} />
              <Row label="Handle Depth" value={cup.handle_depth_pct !== null ? `${cup.handle_depth_pct?.toFixed(1)}%` : "Waiting"} />
              <Row label="Breakout Quality" value={cup.breakout_quality?.toFixed(1) ?? "Waiting"} />
              <Row label="Score" value={cup.score?.toFixed(1) ?? "Waiting"} />
              <p className="mt-3 rounded bg-black/50 p-2 text-xs leading-5 text-slate-300">{cup.message}</p>
            </div>

            <div className="rounded-[8px] border border-slate-800 bg-slate-950 p-3">
              <div className="mb-2 flex items-center gap-2 text-violet-100">
                <Ruler className="h-4 w-4" />
                <h2 className="text-sm font-black">Ölçüm Mantığı</h2>
              </div>
              <Row label="Rim" value={formatPrice(cup.rim_price)} />
              <Row label="Cup Depth" value={formatPrice(cup.cup_depth)} />
              <Row label="Handle Low" value={formatPrice(cup.points.handle_low?.price)} />
              <Row label="Projection Bars" value={String(cup.params.target_projection_bars ?? "-")} />
            </div>

            <div className="rounded-[8px] border border-slate-800 bg-slate-950 p-3">
              <div className="mb-2 flex items-center gap-2 text-emerald-100">
                <Target className="h-4 w-4" />
                <h2 className="text-sm font-black">Target Context</h2>
              </div>
              <p className="text-xs leading-5 text-slate-400">
                Target çizgisi cup depth değerinin rim seviyesinden yukarı taşınmasıyla hesaplanır.
                DEPTH ve MOVE etiketleri ölçümün nereden geldiğini gösterir.
              </p>
            </div>

            <div className="rounded-[8px] border border-slate-800 bg-slate-950 p-3">
              <div className="mb-2 flex items-center gap-2 text-rose-100">
                <Bell className="h-4 w-4" />
                <h2 className="text-sm font-black">Alert</h2>
              </div>
              <div className="rounded border border-slate-800 bg-black/60 px-2 py-2 text-xs text-slate-300">
                Cup and Handle Quality Breakout
              </div>
            </div>
          </aside>
        </div>
      </div>
    </main>
  );
}
