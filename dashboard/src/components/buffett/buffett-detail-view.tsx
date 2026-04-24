"use client";

import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { LabelPill } from "@/components/buffett/label-pill";
import { ScoreBreakdown } from "@/components/buffett/score-breakdown";
import { HistoryCharts } from "@/components/buffett/history-charts";
import { DcfCard } from "@/components/buffett/dcf-card";
import { WarningsCard } from "@/components/buffett/warnings-card";
import { DecisionReasonCard } from "@/components/shared/decision-reason-card";
import { HorizonGuidanceCard } from "@/components/shared/horizon-guidance-card";
import { describeRatioPercent, formatPrice } from "@/lib/formatters";
import type { BuffettStockDetail } from "@/lib/types/buffett";

type Props = { detail: BuffettStockDetail };

function pct(v: number | null | undefined) {
  if (v === null || v === undefined || Number.isNaN(v)) return "-";
  return describeRatioPercent(v).label;
}

export function BuffettDetailView({ detail }: Props) {
  const sig = detail.signal;
  const intrinsic = detail.intrinsic;
  const moat = detail.score.moat.details;
  const fin = detail.score.financial_health.details;

  return (
    <div className="min-h-screen bg-slate-950 px-6 py-8 text-slate-50">
      <div className="mx-auto max-w-[1500px] space-y-6">
        <div className="flex items-center justify-between">
          <Link
            href="/buffett"
            className="inline-flex items-center gap-1 text-sm text-cyan-300 hover:text-cyan-200"
          >
            <ArrowLeft className="h-4 w-4" />
            Buffett listesine dön
          </Link>
          <Link
            href={`/hisse/${detail.symbol}`}
            className="text-xs text-slate-400 hover:text-slate-200"
          >
            Teknik analiz görünümü →
          </Link>
        </div>

        <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-6">
          <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
            <div>
              <div className="flex items-center gap-3">
                <h1 className="text-3xl font-bold">{detail.symbol}</h1>
                <LabelPill color={sig.color} label={sig.label} size="md" />
              </div>
              <p className="mt-1 text-sm text-slate-400">{detail.name}</p>
              <p className="mt-1 text-xs text-slate-500">
                Sektör: {detail.sector.label}
              </p>
            </div>
            <div className="grid grid-cols-3 gap-4 text-right">
              <Stat label="Toplam Skor" value={detail.score.total_score.toFixed(1)} accent="text-emerald-300" />
              <Stat
                label="Adil Değer"
                value={formatPrice(intrinsic.intrinsic_value_per_share ?? null)}
              />
              <Stat
                label="Güvenlik Marjı"
                value={pct(sig.margin_of_safety)}
                accent={sig.margin_of_safety && sig.margin_of_safety >= 0.30 ? "text-emerald-300" : "text-slate-200"}
              />
            </div>
          </div>
          <div className="mt-4 flex flex-col gap-2 border-t border-slate-800 pt-4 md:flex-row md:items-center md:justify-between">
            <p className="text-sm text-slate-300">{sig.holding_recommendation}</p>
            <p className="text-xs text-slate-500">Mevcut fiyat: {formatPrice(intrinsic.current_price ?? null)}</p>
          </div>
        </div>

        <DecisionReasonCard
          title="Karar Gerekçesi"
          decisionLabel={sig.label}
          reason={sig.classification_reason || sig.holding_recommendation}
          factors={sig.classification_factors}
        />

        {sig.horizon_guidance ? (
          <HorizonGuidanceCard
            title="Buffett Vade Önerileri (Temel Analiz)"
            description="Buffett çerçevesinde kısa, orta ve uzun vade için ayrı tutma kararı"
            short={{
              label: sig.horizon_guidance.short.label,
              verdict: sig.horizon_guidance.short.verdict,
              color: sig.horizon_guidance.short.color,
              reason: sig.horizon_guidance.short.reason,
              factors: sig.horizon_guidance.short.factors,
            }}
            medium={{
              label: sig.horizon_guidance.medium.label,
              verdict: sig.horizon_guidance.medium.verdict,
              color: sig.horizon_guidance.medium.color,
              reason: sig.horizon_guidance.medium.reason,
              factors: sig.horizon_guidance.medium.factors,
            }}
            long={{
              label: sig.horizon_guidance.long.label,
              verdict: sig.horizon_guidance.long.verdict,
              color: sig.horizon_guidance.long.color,
              reason: sig.horizon_guidance.long.reason,
              factors: sig.horizon_guidance.long.factors,
            }}
            overall={sig.horizon_guidance.overall}
          />
        ) : null}

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5 lg:col-span-1">
            <h2 className="text-lg font-semibold text-slate-100">Skor Kırılımı</h2>
            <p className="mt-1 text-xs text-slate-500">
              Kategoriler N/A geçildiğinde skor o kategori hariç normalize edilir.
            </p>
            <div className="mt-4">
              <ScoreBreakdown score={detail.score} />
            </div>
          </div>

          <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5 lg:col-span-2">
            <h2 className="text-lg font-semibold text-slate-100">Temel Oranlar</h2>
            <p className="mt-1 text-xs text-slate-500">
              Buffett özet bakışı için en önemli kalemler
            </p>
            <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-3">
              <Metric label="ROE 5y Ort." value={pct(numOrNull(moat.roe_avg_5y))} />
              <Metric label="ROE 5y Std." value={pct(numOrNull(moat.roe_std_5y))} />
              <Metric label="Net Kâr CAGR" value={pct(numOrNull(moat.net_income_cagr))} />
              <Metric label="Net Marj 5y" value={pct(numOrNull(moat.net_margin_avg_5y))} />
              <Metric label="Marj İstikrarı" value={pct(numOrNull(moat.net_margin_std_5y))} />
              <Metric
                label="Borç / Özsermaye"
                value={
                  typeof fin.debt_to_equity === "number"
                    ? fin.debt_to_equity.toFixed(2)
                    : (fin.debt_to_equity as string | null) ?? "-"
                }
              />
              <Metric
                label="Faiz Karşılama"
                value={typeof fin.interest_coverage === "number" ? fin.interest_coverage.toFixed(2) : "-"}
              />
              <Metric
                label="Cari Oran"
                value={
                  typeof fin.current_ratio === "number"
                    ? fin.current_ratio.toFixed(2)
                    : (fin.current_ratio as string | null) ?? "-"
                }
              />
              <Metric
                label="Pozitif FCF Yıl"
                value={
                  typeof fin.positive_fcf_years === "number"
                    ? `${fin.positive_fcf_years} / ${fin.fcf_years_evaluated ?? 5}`
                    : "-"
                }
              />
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          <div className="lg:col-span-2">
            <DcfCard intrinsic={intrinsic} />
          </div>
          <div>
            <WarningsCard warnings={sig.warnings} />
          </div>
        </div>

        <div>
          <h2 className="mb-3 text-lg font-semibold text-slate-100">5 Yıllık Temel Grafikler</h2>
          <HistoryCharts history={detail.history} />
        </div>

        {detail.fetch_errors.length > 0 && (
          <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4 text-xs text-slate-500">
            <div className="mb-1 font-semibold text-slate-400">Veri çekme uyarıları</div>
            <ul className="list-disc space-y-1 pl-5">
              {detail.fetch_errors.map((e, i) => (
                <li key={i}>{e}</li>
              ))}
            </ul>
          </div>
        )}

        <p className="text-xs text-slate-500">
          Bu sayfa AL/SAT/BEKLE üretmez. Tutma süresi 3-5+ yıl varsayılır. Şirket bozulduğunda
          (ROE çöker, borç patlar, kâr negatife döner) yeniden değerlendirin. Fiyat hareketine göre
          karar vermeyin.
        </p>
      </div>
    </div>
  );
}

function Stat({ label, value, accent }: { label: string; value: string; accent?: string }) {
  return (
    <div>
      <div className="text-xs text-slate-400">{label}</div>
      <div className={`mt-1 text-xl font-semibold ${accent ?? "text-slate-100"}`}>{value}</div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-3">
      <div className="text-xs text-slate-400">{label}</div>
      <div className="mt-1 text-base font-semibold text-slate-100">{value}</div>
    </div>
  );
}

function numOrNull(v: unknown): number | null {
  return typeof v === "number" ? v : null;
}
