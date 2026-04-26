"use client";

import Link from "next/link";
import { use } from "react";
import { ArrowLeft, Flame, Gauge, Layers3, ShieldCheck, Volume2 } from "lucide-react";
import { AnalysisStatusBanner } from "@/components/dashboard/analysis-status-banner";
import { AnkaV2Chart } from "@/components/stocks/anka-v2-chart";
import { useAnalysisData } from "@/hooks/use-analysis-data";
import { formatCompactNumber, formatDateTime, formatPrice } from "@/lib/formatters";
import type { AnkaV2Data, StockDetailData } from "@/lib/types/report";

type PageProps = {
  params: Promise<{
    symbol: string;
  }>;
};

function panelTone(value: string) {
  if (value.includes("ALIŞ") || value.includes("Boğa") || value.includes("Yükseliş")) {
    return "text-emerald-200";
  }
  if (value.includes("SATIŞ") || value.includes("Ayı") || value.includes("Düşüş")) {
    return "text-rose-200";
  }
  return "text-amber-100";
}

function InfoRow({ label, value, tone = "text-slate-100" }: { label: string; value: string; tone?: string }) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-l border-slate-800/80 border-l-slate-700/60 px-2 py-1.5 last:border-b-0">
      <span className="text-[10px] uppercase tracking-wide text-slate-500">{label}</span>
      <span className={`text-right text-sm font-semibold ${tone}`}>{value}</span>
    </div>
  );
}

function MiniBlock({ label, value, tone }: { label: string; value: string; tone: string }) {
  return (
    <div className={`rounded border px-2 py-1.5 ${tone}`}>
      <div className="text-[9px] uppercase tracking-wide opacity-70">{label}</div>
      <div className="text-sm font-bold">{value}</div>
    </div>
  );
}

function CalibrationPanel({ anka }: { anka: AnkaV2Data }) {
  const calibration = anka.calibration;
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/80 p-4">
      <div className="mb-3 flex items-center gap-2 text-slate-100">
        <ShieldCheck className="h-4 w-4 text-cyan-200" />
        <h2 className="font-semibold">Geçmiş Başarı Kalibrasyonu</h2>
      </div>
      <div className="grid gap-3 sm:grid-cols-3">
        <div className="rounded-xl bg-slate-950/70 p-3">
          <div className="text-xs text-slate-500">Genel</div>
          <div className="mt-1 text-xl font-semibold text-slate-100">{calibration.total_success_rate ?? "-"}%</div>
          <div className="text-xs text-slate-500">{calibration.label}</div>
        </div>
        <div className="rounded-xl bg-emerald-500/10 p-3">
          <div className="text-xs text-emerald-200/70">Boğa Başarı</div>
          <div className="mt-1 text-xl font-semibold text-emerald-100">{calibration.bull_success_rate ?? "-"}%</div>
          <div className="text-xs text-emerald-200/60">{calibration.bull_signals} sinyal</div>
        </div>
        <div className="rounded-xl bg-rose-500/10 p-3">
          <div className="text-xs text-rose-200/70">Ayı Başarı</div>
          <div className="mt-1 text-xl font-semibold text-rose-100">{calibration.bear_success_rate ?? "-"}%</div>
          <div className="text-xs text-rose-200/60">{calibration.bear_signals} sinyal</div>
        </div>
      </div>
    </div>
  );
}

export default function AnkaV2SymbolPage({ params }: PageProps) {
  const { symbol } = use(params);
  const { data, status, error, isLoading, reload } = useAnalysisData<StockDetailData>({ symbol });

  if (isLoading) {
    return <div className="flex min-h-screen items-center justify-center bg-slate-950 text-slate-100">ANKA detay yükleniyor...</div>;
  }

  if (!data || !data.signal.anka_v2) {
    return <div className="flex min-h-screen items-center justify-center bg-slate-950 text-rose-300">{error || "ANKA v2 hisse detayı bulunamadı."}</div>;
  }

  const refreshNow = async () => {
    await fetch("/api/analysis/refresh", { method: "POST" });
    await reload();
  };

  const anka = data.signal.anka_v2;
  const tv = data.signal.tradingview_snapshot;

  return (
    <main className="min-h-screen bg-slate-950 px-6 py-6 text-slate-50">
      <div className="mx-auto max-w-[1700px] space-y-5">
        <AnalysisStatusBanner status={status} generatedAt={data.generated_at} onRefresh={refreshNow} />

        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <Link href="/anka-v2" className="inline-flex items-center gap-2 text-sm text-cyan-300 hover:text-cyan-200">
              <ArrowLeft className="h-4 w-4" />
              ANKA v2 listesine dön
            </Link>
            <div className="mt-3 flex flex-wrap items-center gap-3">
              <h1 className="text-4xl font-bold tracking-tight">{data.signal.symbol}</h1>
              <span className={`rounded-full border border-slate-700 bg-slate-900 px-3 py-1 text-sm font-semibold ${panelTone(anka.synthesis_decision)}`}>
                {anka.synthesis_decision}
              </span>
              <span className="rounded-full border border-cyan-500/30 bg-cyan-500/10 px-3 py-1 text-sm text-cyan-100">
                {anka.primary_signal}
              </span>
            </div>
            <p className="mt-2 text-sm text-slate-400">
              Son snapshot: {formatDateTime(data.generated_at)} | Güncel fiyat: {formatPrice(data.signal.price)}
            </p>
          </div>
          <div className="rounded-2xl border border-cyan-500/30 bg-cyan-500/10 px-5 py-4 text-right">
            <div className="text-xs uppercase tracking-wide text-cyan-200/70">Sentez Puanı</div>
            <div className="text-4xl font-bold text-cyan-100">{anka.synthesis_score.toFixed(1)}</div>
            <div className="text-xs text-slate-400">Fibo bonus: {anka.fibonacci_confirmation.bonus.toFixed(1)}</div>
          </div>
        </div>

        <div className="grid min-w-0 gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
          <AnkaV2Chart detail={data} />

          <aside className="space-y-3">
            <div className="rounded-[10px] border border-yellow-500/40 bg-[#061405] p-2 shadow-2xl shadow-black/30">
              <div className="mb-2 rounded bg-yellow-400 px-2 py-1 text-center text-[11px] font-black uppercase tracking-wide text-black">
                ANKA SİSTEMİ v2.0 · AKTİF PANEL
              </div>
              <div className="grid grid-cols-2 gap-1.5">
                <MiniBlock label="Sentez" value={anka.synthesis_decision} tone="border-emerald-400/40 bg-emerald-500/20 text-emerald-100" />
                <MiniBlock label="Skor" value={anka.synthesis_score.toFixed(1)} tone="border-cyan-400/40 bg-cyan-500/20 text-cyan-100" />
                <MiniBlock label="Vadi" value={anka.valley.name} tone="border-yellow-400/40 bg-yellow-500/20 text-yellow-100" />
                <MiniBlock label="Ateş" value={anka.fire_power.toFixed(1)} tone="border-orange-400/40 bg-orange-500/20 text-orange-100" />
              </div>

              <div className="mt-2 rounded border border-slate-700 bg-black/55 p-2">
                <div className="mb-2 flex items-center gap-2 text-slate-100">
                  <Flame className="h-4 w-4 text-amber-200" />
                  <h2 className="text-sm font-semibold">Bilgi Paneli</h2>
                </div>
                <InfoRow label="Vadi Puanı" value={`${anka.valley.score.toFixed(1)} / 100`} />
                <InfoRow label="Momentum" value={anka.momentum_label} />
                <InfoRow label="Faz" value={anka.phase} />
                <InfoRow label="Trend" value={anka.trend} tone={panelTone(anka.trend)} />
                <InfoRow label="Sinyal" value={anka.primary_signal} tone={panelTone(anka.primary_signal)} />
                <InfoRow label="kNN Rölatif Hacim" value={`${anka.knn_volume.relative_volume.toFixed(2)}x`} />
                <InfoRow label="kNN Boğa / Ayı" value={`${anka.knn_volume.bullish_ratio.toFixed(1)} / ${anka.knn_volume.bearish_ratio.toFixed(1)}`} />
                <InfoRow label="Fibo Teyidi" value={`${anka.fibonacci_confirmation.label} (${anka.fibonacci_confirmation.bonus.toFixed(0)})`} />
                <InfoRow label="Kalibrasyon" value={`${anka.calibration.label} ${anka.calibration.total_success_rate ?? "-"}%`} />
              </div>

              <div className="mt-2 rounded border border-slate-700 bg-black/55 p-2">
                <div className="mb-1 text-[10px] font-bold uppercase tracking-wide text-yellow-200">TradingView Snapshot</div>
                <InfoRow label="Durum" value={tv?.status ?? "Yok"} tone={tv?.status === "verified" ? "text-emerald-200" : "text-amber-100"} />
                <InfoRow label="TV Fiyat" value={formatPrice(tv?.close)} />
                <InfoRow label="TV Hacim" value={formatCompactNumber(tv?.volume)} />
                <InfoRow label="Fiyat Sapma" value={tv?.price_delta_pct === null || tv?.price_delta_pct === undefined ? "-" : `${tv.price_delta_pct.toFixed(2)}%`} />
              </div>
            </div>

            <div className="rounded-2xl border border-slate-800 bg-slate-900/90 p-4 shadow-2xl shadow-black/30">
              <div className="mb-3 flex items-center gap-2 text-slate-100">
                <Flame className="h-4 w-4 text-amber-200" />
                <h2 className="font-semibold">Stratejik Okuma</h2>
              </div>
              <div className="space-y-2 text-xs leading-5 text-slate-300">
                <p>1. Kalibrasyon %60 üzerindeyse sinyal istatistiksel olarak daha güvenilirdir.</p>
                <p>2. Rölatif hacim 1.2x üzerindeyse hareket hacimle desteklenir.</p>
                <p>3. Güçlü alış + F38.2/F50 destek teyidi en yüksek olasılıklı kurulumdur.</p>
                <p>4. Kül Fazı sırasında kırılım beklemek daha sağlıklı kabul edilir.</p>
              </div>
            </div>

            <div className="rounded-2xl border border-slate-800 bg-slate-900/80 p-4">
              <div className="mb-3 flex items-center gap-2 text-slate-100">
                <Layers3 className="h-4 w-4 text-cyan-200" />
                <h2 className="font-semibold">Vadi Yorumu</h2>
              </div>
              <p className="text-sm leading-6 text-slate-300">{anka.valley.market_comment}</p>
              <p className="mt-2 text-xs text-slate-500">{anka.valley.potential_move}</p>
            </div>

            <div className="rounded-2xl border border-slate-800 bg-slate-900/80 p-4">
              <div className="mb-3 flex items-center gap-2 text-slate-100">
                <Volume2 className="h-4 w-4 text-emerald-200" />
                <h2 className="font-semibold">kNN Rölatif Hacim</h2>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="rounded-xl bg-slate-950/70 p-3">
                  <div className="text-xs text-slate-500">Boğa</div>
                  <div className="mt-1 text-xl font-semibold text-emerald-100">{anka.knn_volume.bullish_ratio.toFixed(1)}%</div>
                </div>
                <div className="rounded-xl bg-slate-950/70 p-3">
                  <div className="text-xs text-slate-500">Ayı</div>
                  <div className="mt-1 text-xl font-semibold text-rose-100">{anka.knn_volume.bearish_ratio.toFixed(1)}%</div>
                </div>
              </div>
              <p className="mt-3 text-sm text-slate-400">{anka.knn_volume.label}</p>
            </div>

            <div className="rounded-2xl border border-slate-800 bg-slate-900/80 p-4">
              <div className="mb-3 flex items-center gap-2 text-slate-100">
                <Gauge className="h-4 w-4 text-amber-200" />
                <h2 className="font-semibold">Fibonacci Sentez Teyidi</h2>
              </div>
              <p className="text-sm leading-6 text-slate-300">{anka.fibonacci_confirmation.message}</p>
              <div className="mt-3 rounded-xl bg-slate-950/70 p-3 text-sm text-slate-300">
                {anka.fibonacci_confirmation.level_name || "Seviye yok"} | {formatPrice(anka.fibonacci_confirmation.level_price)}
              </div>
            </div>
          </aside>
        </div>

        <CalibrationPanel anka={anka} />
      </div>
    </main>
  );
}
