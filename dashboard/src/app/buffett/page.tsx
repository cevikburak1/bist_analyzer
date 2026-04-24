"use client";

import { BuffettTable } from "@/components/buffett/buffett-table";
import { useBuffettData } from "@/hooks/use-buffett-data";
import { formatDateTime } from "@/lib/formatters";
import type { BuffettListResponse } from "@/lib/types/buffett";

export default function BuffettListPage() {
  const { data, error, isLoading } = useBuffettData<BuffettListResponse>();

  if (isLoading) {
    return <div className="flex min-h-screen items-center justify-center bg-slate-950 text-slate-100">Yükleniyor...</div>;
  }
  if (!data) {
    return <div className="flex min-h-screen items-center justify-center bg-slate-950 text-rose-300">{error || "Veri yok."}</div>;
  }
  if (!data.items.length) {
    return (
      <div className="min-h-screen bg-slate-950 px-6 py-8 text-slate-50">
        <div className="mx-auto max-w-3xl rounded-2xl border border-slate-800 bg-slate-900/70 p-8 text-center">
          <h1 className="text-2xl font-bold">Buffett Analizi Henüz Çalıştırılmamış</h1>
          <p className="mt-3 text-sm text-slate-400">
            Veri üretmek için proje kökünde şunu çalıştır:
          </p>
          <pre className="mt-4 rounded-md bg-slate-950 p-3 text-left text-xs text-cyan-300">
            python buffett_main.py
          </pre>
          <p className="mt-3 text-xs text-slate-500">
            Komut tamamlandığında bu sayfa otomatik dolacaktır.
          </p>
        </div>
      </div>
    );
  }

  const labels = data.summary.by_label || {};

  return (
    <div className="min-h-screen bg-slate-950 px-6 py-8 text-slate-50">
      <div className="mx-auto max-w-[1600px] space-y-6">
        <div className="flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">Buffett Analizi</h1>
            <p className="mt-1 text-sm text-slate-400">
              Şirket kalitesi + adil değer + güvenlik marjı. Çıktı &quot;AL/SAT&quot; değil; etiket + tutma önerisidir.
            </p>
            <p className="mt-1 text-xs text-slate-500">
              Snapshot: {formatDateTime(data.generated_at)}
            </p>
          </div>
          <div className="text-sm text-slate-400">
            {data.summary.total} hisse
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
          <SummaryCard label="Harika - Ucuz" count={labels.HARIKA_IS_UCUZ ?? 0} accent="text-emerald-300" />
          <SummaryCard label="Harika - Pahalı" count={labels.HARIKA_IS_PAHALI ?? 0} accent="text-amber-300" />
          <SummaryCard label="İyi - Ucuz" count={labels.IYI_IS_UCUZ ?? 0} accent="text-lime-300" />
          <SummaryCard label="Geçer" count={labels.GECER ?? 0} accent="text-slate-300" />
          <SummaryCard label="Pas Geç" count={labels.PAS_GEC ?? 0} accent="text-rose-300" />
          <SummaryCard label="Yetersiz Veri" count={labels.YETERSIZ_VERI ?? 0} accent="text-sky-300" />
        </div>

        <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5">
          <BuffettTable items={data.items} />
        </div>

        <p className="text-xs text-slate-500">
          Bu liste teknik analiz değildir. AL/SAT sinyali içermez. Tutma ufku 3-5+ yıl varsayılır.
          Şirket tezi bozulduğunda (ROE çöker, borç patlar, kâr negatife döner) yeniden değerlendirin.
        </p>
      </div>
    </div>
  );
}

function SummaryCard({ label, count, accent }: { label: string; count: number; accent: string }) {
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900/70 p-3">
      <div className="text-xs text-slate-400">{label}</div>
      <div className={`mt-1 text-xl font-semibold ${accent}`}>{count}</div>
    </div>
  );
}
