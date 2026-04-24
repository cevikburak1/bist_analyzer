/**
 * Tez bozulma uyarıları.
 * Buffett'a göre satış kararı fiyat hareketinden değil, şirket tezinin
 * bozulmasından gelir.
 */

import { AlertTriangle, ShieldCheck } from "lucide-react";

type Props = { warnings: string[] };

export function WarningsCard({ warnings }: Props) {
  if (warnings.length === 0) {
    return (
      <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-4">
        <div className="flex items-center gap-2">
          <ShieldCheck className="h-4 w-4 text-emerald-300" />
          <h3 className="text-sm font-semibold text-emerald-300">Tez Bozulması Yok</h3>
        </div>
        <p className="mt-2 text-xs text-slate-400">
          Şirket temellerinde son dönem belirgin bozulma sinyali tespit edilmedi.
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-amber-500/20 bg-amber-500/5 p-4">
      <div className="flex items-center gap-2">
        <AlertTriangle className="h-4 w-4 text-amber-300" />
        <h3 className="text-sm font-semibold text-amber-300">Tez Bozulma Uyarıları</h3>
      </div>
      <ul className="mt-3 space-y-2">
        {warnings.map((w, i) => (
          <li key={i} className="flex items-start gap-2 text-sm text-slate-200">
            <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-amber-300" />
            <span>{w}</span>
          </li>
        ))}
      </ul>
      <p className="mt-3 text-xs text-slate-500">
        Bu sinyaller fiyat değil, şirket bilanço/karlılık eğilimi üzerinden çıkarılmıştır.
        Buffett: &quot;Tez bozulduysa sat. Sadece fiyat düştüyse satma.&quot;
      </p>
    </div>
  );
}
