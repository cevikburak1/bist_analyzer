/**
 * DCF Şeffaflığı: Hangi varsayımlarla hangi adil değer çıktığı.
 * V1: read-only. V2'de iskonto sliderı eklenecek.
 */

import type { BuffettIntrinsic } from "@/lib/types/buffett";
import { describeRatioPercent, formatPrice } from "@/lib/formatters";

type Props = { intrinsic: BuffettIntrinsic };

function pct(v: number | null | undefined) {
  return describeRatioPercent(v).label;
}

function isAnomaly(v: number | null | undefined) {
  return describeRatioPercent(v).isAnomaly;
}

export function DcfCard({ intrinsic }: Props) {
  if (intrinsic.is_na) {
    return (
      <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
        <h3 className="text-sm font-semibold text-slate-100">DCF (Adil Değer)</h3>
        <p className="mt-2 text-sm text-slate-400">
          Hesaplanamadı: {intrinsic.reason || "veri yetersiz"}
        </p>
      </div>
    );
  }

  const mos = intrinsic.margin_of_safety;
  const mosAnomaly = isAnomaly(mos);
  const mosColor = mosAnomaly
    ? "text-amber-300"
    : mos === null
      ? "text-slate-300"
      : mos >= 0.30
        ? "text-emerald-300"
        : mos >= 0
          ? "text-amber-300"
          : "text-rose-300";

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
      <h3 className="text-sm font-semibold text-slate-100">DCF (Adil Değer)</h3>
      {mosAnomaly ? (
        <p className="mt-2 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-200">
          Bu hisse için DCF çıktıları olağan dışı bir büyüklüğe sahip (hisse adedi
          veya FCF eşleşmesinde uyumsuzluk). Güvenlik marjı bu nedenle "Veri
          Anomalisi" olarak işaretlendi.
        </p>
      ) : null}
      <div className="mt-3 grid grid-cols-2 gap-3 text-sm">
        <Row label="Adil Değer / Hisse" value={formatPrice(intrinsic.intrinsic_value_per_share ?? null)} accent="text-slate-100" />
        <Row label="Mevcut Fiyat" value={formatPrice(intrinsic.current_price ?? null)} />
        <Row label="Güvenlik Marjı (MoS)" value={pct(mos)} accent={mosColor} />
        <Row label="Baz FCF" value={formatPrice(intrinsic.base_fcf ?? null)} />
        <Row label="Kullanılan Büyüme" value={pct(intrinsic.growth_used)} />
        <Row label="İskonto Oranı" value={pct(intrinsic.discount_rate)} />
        <Row label="Terminal Büyüme" value={pct(intrinsic.terminal_growth)} />
        <Row label="Projeksiyon Süresi" value={`${intrinsic.projection_years} yıl`} />
      </div>
      <p className="mt-3 text-xs text-slate-500">
        Bu basit bir DCF modelidir. Gerçek hayatta varsayımları kendi bilginize göre ayarlamanız beklenir;
        sektör/şirket bazlı sapma %20-50 olabilir. Buffett: &quot;Adil değer sezgidir, formül değildir.&quot;
      </p>
    </div>
  );
}

function Row({ label, value, accent }: { label: string; value: string; accent?: string }) {
  return (
    <div className="flex items-center justify-between border-b border-slate-800/50 py-1.5">
      <span className="text-slate-400">{label}</span>
      <span className={`font-medium ${accent ?? "text-slate-200"}`}>{value}</span>
    </div>
  );
}
