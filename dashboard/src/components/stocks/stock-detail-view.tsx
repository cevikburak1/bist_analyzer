import type { ReactNode } from "react";
import Link from "next/link";
import { ArrowLeft, TrendingDown, TrendingUp } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatDateTime, formatPercent, formatPrice } from "@/lib/formatters";
import type { StockDetailData } from "@/lib/types/report";
import { SignalBadge } from "@/components/stocks/signal-badge";
import { StockPriceChart } from "@/components/stocks/stock-price-chart";
import { DecisionReasonCard } from "@/components/shared/decision-reason-card";
import { HorizonGuidanceCard } from "@/components/shared/horizon-guidance-card";
import { HorizonScoresPanel } from "@/components/stocks/horizon-scores-panel";

type StockDetailViewProps = {
  detail: StockDetailData;
};

function DetailCard({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <Card className="border-slate-800 bg-slate-900/70">
      <CardHeader className="pb-3">
        <CardTitle className="text-base text-slate-100">{title}</CardTitle>
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}

export function StockDetailView({ detail }: StockDetailViewProps) {
  const { signal, market_regime: marketRegime } = detail;
  const trendIcon =
    signal.trend === "YUKARI" ? (
      <TrendingUp className="h-4 w-4 text-emerald-300" />
    ) : (
      <TrendingDown className="h-4 w-4 text-rose-300" />
    );

  return (
    <div className="min-h-screen bg-slate-950 px-6 py-8 text-slate-50">
      <div className="mx-auto max-w-[1500px] space-y-6">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div className="space-y-2">
            <Link href="/" className="inline-flex items-center gap-2 text-sm text-cyan-300 hover:text-cyan-200">
              <ArrowLeft className="h-4 w-4" />
              Tum hisselere don
            </Link>
            <div className="flex items-center gap-3">
              <h1 className="text-3xl font-bold">{signal.symbol}</h1>
              <SignalBadge signal={signal.signal_daily} />
              {trendIcon}
            </div>
            <p className="text-sm text-slate-400">
              Son snapshot: {formatDateTime(detail.generated_at)} | Piyasa rejimi: {marketRegime.label}
            </p>
          </div>
          <div className="rounded-xl border border-slate-800 bg-slate-900/70 px-4 py-3 text-right">
            <div className="text-xs text-slate-400">Guncel fiyat</div>
            <div className="text-3xl font-semibold text-slate-100">{formatPrice(signal.price)}</div>
            <div className="text-xs text-slate-500">Yorum: {signal.commentary.summary || signal.summary}</div>
          </div>
        </div>

        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <DetailCard title="Risk ve Islem Seviyeleri">
            <div className="space-y-2 text-sm text-slate-300">
              <div>Entry: <span className="text-slate-100">{formatPrice(signal.entry)}</span></div>
              <div>ATR Stop: <span className="text-rose-300">{formatPrice(signal.targets.stop_loss || signal.stop_loss)}</span></div>
              <div>Risk: <span className="text-slate-100">{formatPercent(signal.targets.risk_pct || signal.risk_pct)}</span></div>
              <div>Genel R/O: <span className="text-slate-100">{signal.rr_ratio.toFixed(2)}</span></div>
            </div>
          </DetailCard>

          <DetailCard title="3 Vade Hedef">
            <div className="space-y-2 text-sm text-slate-300">
              <div>Kisa: <span className="text-emerald-300">{formatPrice(signal.targets.short_target)}</span> ({signal.targets.short_rr.toFixed(2)})</div>
              <div>Orta: <span className="text-emerald-300">{formatPrice(signal.targets.medium_target)}</span> ({signal.targets.medium_rr.toFixed(2)})</div>
              <div>Uzun: <span className="text-emerald-300">{formatPrice(signal.targets.long_target)}</span> ({signal.targets.long_rr.toFixed(2)})</div>
            </div>
          </DetailCard>

          <DetailCard title="Fibonacci ve Elliott">
            <div className="space-y-2 text-sm text-slate-300">
              <div>Destek: <span className="text-slate-100">{formatPrice(signal.fibonacci.support)}</span></div>
              <div>Direnc: <span className="text-slate-100">{formatPrice(signal.fibonacci.resistance)}</span></div>
              <div>Bolge: <span className="text-slate-100">{signal.fibonacci.zone || "-"}</span></div>
              <div>Dalga: <span className="text-cyan-300">{signal.elliott_wave.current_wave || "-"}</span></div>
              <div>Guven: <span className="text-slate-100">{signal.elliott_wave.confidence || "-"}</span></div>
            </div>
          </DetailCard>

          <DetailCard title="Zaman Dilimi ve Momentum">
            <div className="space-y-2 text-sm text-slate-300">
              <div>Gunluk: <span className="text-slate-100">{signal.timeframes.daily}</span></div>
              <div>Haftalik: <span className="text-slate-100">{signal.timeframes.weekly || "-"}</span></div>
              <div>Aylik: <span className="text-slate-100">{signal.timeframes.monthly || "-"}</span></div>
              <div>Yillik: <span className="text-slate-100">{signal.timeframes.yearly || "-"}</span></div>
              <div>RSI: <span className="text-slate-100">{signal.rsi.toFixed(1)}</span></div>
            </div>
          </DetailCard>
        </div>

        {signal.horizon_scores ? (
          <HorizonScoresPanel scores={signal.horizon_scores} />
        ) : null}

        <DecisionReasonCard
          title="Gunluk Karar Gerekcesi (legacy)"
          decisionLabel={signal.signal_daily}
          reason={signal.reason}
          bulletReasons={signal.reason_factors}
        />

        {signal.horizon_guidance ? (
          <HorizonGuidanceCard
            title="Teknik Vade Onerileri (Kisa / Orta / Uzun)"
            description="Teknik gostergelere ve hedef R/O degerlerine dayali vade bazli karar"
            short={{
              label: signal.horizon_guidance.short.label,
              verdict: signal.horizon_guidance.short.verdict,
              color: signal.horizon_guidance.short.color,
              reason: signal.horizon_guidance.short.reason,
              factors: signal.horizon_guidance.short.factors,
              rr: signal.horizon_guidance.short.rr,
              targetPrice: signal.horizon_guidance.short.target_price,
              rewardPct: signal.horizon_guidance.short.reward_pct,
            }}
            medium={{
              label: signal.horizon_guidance.medium.label,
              verdict: signal.horizon_guidance.medium.verdict,
              color: signal.horizon_guidance.medium.color,
              reason: signal.horizon_guidance.medium.reason,
              factors: signal.horizon_guidance.medium.factors,
              rr: signal.horizon_guidance.medium.rr,
              targetPrice: signal.horizon_guidance.medium.target_price,
              rewardPct: signal.horizon_guidance.medium.reward_pct,
            }}
            long={{
              label: signal.horizon_guidance.long.label,
              verdict: signal.horizon_guidance.long.verdict,
              color: signal.horizon_guidance.long.color,
              reason: signal.horizon_guidance.long.reason,
              factors: signal.horizon_guidance.long.factors,
              rr: signal.horizon_guidance.long.rr,
              targetPrice: signal.horizon_guidance.long.target_price,
              rewardPct: signal.horizon_guidance.long.reward_pct,
            }}
            overall={signal.horizon_guidance.overall}
          />
        ) : null}

        <StockPriceChart detail={detail} />

        <div className="grid gap-4 lg:grid-cols-3">
          <DetailCard title="Analiz Ozeti">
            <div className="space-y-3 text-sm text-slate-300">
              <p className="leading-6 text-slate-200">{signal.commentary.paragraph || signal.reason}</p>
              {signal.commentary.key_points.length > 0 ? (
                <div>
                  <div className="mb-2 text-xs uppercase tracking-wide text-slate-500">One cikan noktalar</div>
                  <ul className="space-y-2">
                    {signal.commentary.key_points.map((point) => (
                      <li key={point} className="rounded-lg bg-slate-950/70 px-3 py-2">
                        {point}
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </div>
          </DetailCard>

          <DetailCard title="Mum Formasyonlari">
            <div className="space-y-3 text-sm text-slate-300">
              <div>Bias: <span className="text-slate-100">{signal.candle_bias}</span></div>
              {signal.candle_patterns.length > 0 ? (
                <div className="space-y-2">
                  {signal.candle_patterns.map((pattern) => (
                    <div key={`${pattern.name}-${pattern.direction}`} className="rounded-lg bg-slate-950/70 px-3 py-2">
                      <div className="font-medium text-slate-100">{pattern.name}</div>
                      <div className="text-xs text-slate-400">{pattern.direction} | {pattern.strength}</div>
                      <div className="mt-1 text-xs text-slate-500">{pattern.description}</div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-slate-500">Bu snapshot icin formasyon bulunamadi.</div>
              )}
            </div>
          </DetailCard>

          <DetailCard title="Skor Dagilimi ve Riskler">
            <div className="space-y-3 text-sm text-slate-300">
              <div>Trendin yonu ve gucu: <span className="text-slate-100">{signal.score_breakdown.trend.toFixed(1)}</span></div>
              <div>Momentum ve trend kuvveti: <span className="text-slate-100">{signal.score_breakdown.momentum.toFixed(1)}</span></div>
              <div>Hacim patlamasi ve para akisi: <span className="text-slate-100">{signal.score_breakdown.volume.toFixed(1)}</span></div>
              <div>Fiyat pozisyonu: <span className="text-slate-100">{signal.score_breakdown.price_position.toFixed(1)}</span></div>
              <div>Sikisma ve kirilim potansiyeli: <span className="text-slate-100">{(signal.score_breakdown.squeeze_breakout ?? 0).toFixed(1)}</span></div>
              <div className="grid grid-cols-2 gap-2 rounded-lg bg-slate-950/70 p-3 text-xs">
                <div title="Maliyet tamponlu tarihsel kurulum proxy'sidir; gerçek backtest değildir">
                  Kurulum proxy: <span className="text-slate-100">%{(signal.score_breakdown.wr_pct ?? 0).toFixed(0)} (n={signal.score_breakdown.wr_samples ?? 0})</span>
                </div>
                <div>ADX: <span className="text-slate-100">{(signal.score_breakdown.adx ?? 0).toFixed(1)}</span></div>
                <div>V/K: <span className="text-slate-100">{(signal.score_breakdown.v_kat ?? 0).toFixed(2)}</span></div>
                <div>DZL: <span className="text-slate-100">{signal.score_breakdown.dzl_ok ? "OK" : "--"}</span></div>
                <div>SQZ: <span className="text-slate-100">{signal.score_breakdown.sqz_ok ? "OK" : "--"}</span></div>
                <div>EMA uzaklik: <span className="text-slate-100">%{(signal.score_breakdown.ema_distance_pct ?? 0).toFixed(1)}</span></div>
              </div>
              {signal.commentary.risks.length > 0 ? (
                <div className="space-y-2 pt-2">
                  <div className="text-xs uppercase tracking-wide text-slate-500">Risk notlari</div>
                  {signal.commentary.risks.map((risk) => (
                    <div key={risk} className="rounded-lg border border-rose-500/20 bg-rose-500/10 px-3 py-2 text-rose-200">
                      {risk}
                    </div>
                  ))}
                </div>
              ) : null}
            </div>
          </DetailCard>
        </div>
      </div>
    </div>
  );
}
