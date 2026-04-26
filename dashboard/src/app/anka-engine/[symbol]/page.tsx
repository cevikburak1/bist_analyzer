"use client";

import Link from "next/link";
import { use } from "react";
import { ArrowLeft, Bell, BrainCircuit, Gauge, GitBranch, LineChart, SearchCheck } from "lucide-react";
import { AnalysisStatusBanner } from "@/components/dashboard/analysis-status-banner";
import { AnkaEngineChart } from "@/components/stocks/anka-engine-chart";
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

export default function AnkaEngineSymbolPage({ params }: PageProps) {
  const { symbol } = use(params);
  const { data, status, error, isLoading, reload } = useAnalysisData<StockDetailData>({ symbol });

  if (isLoading) {
    return <div className="flex min-h-screen items-center justify-center bg-black text-slate-100">ANKA motor grafiği yükleniyor...</div>;
  }

  if (!data || !data.signal.anka_v2) {
    return <div className="flex min-h-screen items-center justify-center bg-black text-rose-300">{error || "ANKA motor detayı bulunamadı."}</div>;
  }

  const refreshNow = async () => {
    await fetch("/api/analysis/refresh", { method: "POST" });
    await reload();
  };

  const anka = data.signal.anka_v2;

  return (
    <main className="min-h-screen bg-black px-6 py-6 text-slate-50">
      <div className="mx-auto max-w-[1700px] space-y-5">
        <AnalysisStatusBanner status={status} generatedAt={data.generated_at} onRefresh={refreshNow} />

        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <Link href="/anka-engine" className="inline-flex items-center gap-2 text-sm text-cyan-300 hover:text-cyan-200">
              <ArrowLeft className="h-4 w-4" />
              ANKA Motor tablosuna dön
            </Link>
            <div className="mt-3 flex flex-wrap items-center gap-3">
              <h1 className="text-4xl font-black tracking-tight">{data.signal.symbol}</h1>
              <span className="rounded border border-yellow-500/40 bg-yellow-500/10 px-3 py-1 text-sm font-bold text-yellow-100">{anka.layer_engine.recommendation}</span>
              <span className="rounded border border-cyan-500/40 bg-cyan-500/10 px-3 py-1 text-sm font-bold text-cyan-100">{anka.lr_engine.direction}</span>
            </div>
            <p className="mt-2 text-sm text-slate-500">Son snapshot: {formatDateTime(data.generated_at)} | Fiyat: {formatPrice(data.signal.price)}</p>
          </div>
          <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
            <Metric label="K.Motor" value={anka.layer_engine.score.toFixed(1)} note={`${"★".repeat(anka.layer_engine.confidence_stars)} güven`} />
            <Metric label="LR" value={anka.lr_engine.score.toFixed(1)} note={anka.lr_engine.intensity} />
            <Metric label="kNN" value={anka.knn_pattern.score.toFixed(1)} note={anka.knn_pattern.prediction} />
            <Metric label="Sentez" value={anka.synthesis_score.toFixed(1)} note={anka.synthesis_decision} />
          </div>
        </div>

        <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_380px]">
          <AnkaEngineChart detail={data} />
          <aside className="space-y-3">
            <div className="rounded-[8px] border border-yellow-500/40 bg-[#061405] p-3">
              <div className="mb-2 flex items-center gap-2 text-yellow-100">
                <BrainCircuit className="h-4 w-4" />
                <h2 className="text-sm font-black">Katman Akıl Yürütme</h2>
              </div>
              <Row label="K.Motor Puanı" value={anka.layer_engine.score.toFixed(1)} />
              <Row label="K.Güven" value={"★".repeat(anka.layer_engine.confidence_stars)} />
              <Row label="Katman Zinciri" value={anka.layer_engine.chain} />
              <Row label="Öneri" value={anka.layer_engine.recommendation} />
              <p className="mt-3 rounded bg-black/50 p-2 text-xs leading-5 text-slate-300">{anka.layer_engine.scenario}</p>
            </div>

            <div className="rounded-[8px] border border-slate-800 bg-slate-950 p-3">
              <div className="mb-2 flex items-center gap-2 text-cyan-100">
                <LineChart className="h-4 w-4" />
                <h2 className="text-sm font-black">Lineer Regresyon</h2>
              </div>
              <Row label="Yön" value={anka.lr_engine.direction} />
              <Row label="Eğim" value={`${anka.lr_engine.slope_pct.toFixed(4)}%`} />
              <Row label="R²" value={anka.lr_engine.r2.toFixed(3)} />
            </div>

            <div className="rounded-[8px] border border-slate-800 bg-slate-950 p-3">
              <div className="mb-2 flex items-center gap-2 text-emerald-100">
                <SearchCheck className="h-4 w-4" />
                <h2 className="text-sm font-black">kNN Örüntü Motoru</h2>
              </div>
              <Row label="Tahmin" value={anka.knn_pattern.prediction} />
              <Row label="Güven" value={`${anka.knn_pattern.confidence.toFixed(1)}%`} />
              <Row label="Komşu" value={`${anka.knn_pattern.neighbors} / ${anka.knn_pattern.params.n}`} />
              <Row label="Parametre" value={`ND=${anka.knn_pattern.params.nd}, NY=${anka.knn_pattern.params.ny}, spacing=${anka.knn_pattern.params.spacing}`} />
            </div>

            <div className="rounded-[8px] border border-slate-800 bg-slate-950 p-3">
              <div className="mb-2 flex items-center gap-2 text-orange-100">
                <Gauge className="h-4 w-4" />
                <h2 className="text-sm font-black">Sentez Kararı</h2>
              </div>
              <Row label="Ağırlık" value="K%40 / LR%30 / kNN%30" />
              <Row label="Fibo Bonus" value={`${anka.fibonacci_confirmation.bonus.toFixed(0)} puan`} />
              <Row label="Nihai" value={anka.synthesis_decision} />
            </div>

            <div className="rounded-[8px] border border-slate-800 bg-slate-950 p-3">
              <div className="mb-2 flex items-center gap-2 text-rose-100">
                <Bell className="h-4 w-4" />
                <h2 className="text-sm font-black">Uyarılar</h2>
              </div>
              <div className="space-y-2">
                {anka.alerts.length > 0 ? anka.alerts.map((alert) => (
                  <div key={alert} className="rounded border border-slate-800 bg-black/60 px-2 py-1.5 text-xs text-slate-200">{alert}</div>
                )) : <div className="text-xs text-slate-500">Aktif uyarı yok.</div>}
              </div>
            </div>
            <div className="rounded-[8px] border border-slate-800 bg-slate-950 p-3">
              <div className="mb-2 flex items-center gap-2 text-slate-100">
                <GitBranch className="h-4 w-4" />
                <h2 className="text-sm font-black">Motor Özeti</h2>
              </div>
              <p className="text-xs leading-5 text-slate-400">
                Bu ekran ANKA v2.0’dan bağımsız ikinci okuma katmanıdır; karar, Katman Motoru, LR ve kNN skorlarının ağırlıklı sentezinden gelir.
              </p>
            </div>
          </aside>
        </div>
      </div>
    </main>
  );
}
