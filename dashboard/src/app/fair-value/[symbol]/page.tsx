"use client";

import Link from "next/link";
import { use } from "react";
import { ArrowLeft, Banknote, Bell } from "lucide-react";
import { FairValuePanel } from "@/components/buffett/fair-value-panel";
import { useBuffettData } from "@/hooks/use-buffett-data";
import { formatDateTime } from "@/lib/formatters";
import type { BuffettStockDetail } from "@/lib/types/buffett";

type PageProps = {
  params: Promise<{
    symbol: string;
  }>;
};

export default function FairValueDetailPage({ params }: PageProps) {
  const { symbol } = use(params);
  const { data, error, isLoading } = useBuffettData<BuffettStockDetail>({ symbol });

  if (isLoading) {
    return <div className="flex min-h-screen items-center justify-center bg-black text-slate-100">Adil değer detayı yükleniyor...</div>;
  }

  if (!data || !data.fair_value) {
    return <div className="flex min-h-screen items-center justify-center bg-black text-rose-300">{error || "Adil değer detayı bulunamadı."}</div>;
  }

  return (
    <main className="min-h-screen bg-black px-6 py-6 text-slate-50">
      <div className="mx-auto max-w-[1700px] space-y-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <Link href="/fair-value" className="inline-flex items-center gap-2 text-sm text-cyan-300 hover:text-cyan-200">
              <ArrowLeft className="h-4 w-4" />
              Adil değer tablosuna dön
            </Link>
            <div className="mt-3 flex flex-wrap items-center gap-3">
              <h1 className="text-4xl font-black tracking-tight">{data.symbol}</h1>
              <span className="rounded border border-blue-500/40 bg-blue-500/10 px-3 py-1 text-sm font-bold text-blue-100">{data.fair_value.aggregation_method}</span>
              <span className="rounded border border-slate-700 bg-slate-900 px-3 py-1 text-sm text-slate-300">{data.fair_value.valid_methods}/10 yöntem</span>
            </div>
            <p className="mt-2 text-sm text-slate-500">{data.name} | Snapshot: {formatDateTime(data.generated_at)}</p>
          </div>
          <div className="rounded-[10px] border border-slate-800 bg-slate-950 p-4">
            <div className="flex items-center gap-2 text-blue-100">
              <Banknote className="h-4 w-4" />
              <span className="text-sm font-bold">Market: {data.fair_value.market} · {data.fair_value.currency}</span>
            </div>
          </div>
        </div>

        <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_340px]">
          <FairValuePanel fairValue={data.fair_value} />
          <aside className="space-y-3">
            <div className="rounded-[10px] border border-slate-800 bg-slate-950 p-4">
              <h2 className="mb-3 text-sm font-black text-slate-100">Info Panel</h2>
              <div className="space-y-2 text-sm text-slate-300">
                <div>Sector: {data.fair_value.sector_label}</div>
                <div>Rate: {data.fair_value.bond_benchmark}</div>
                <div>Inflation: {data.fair_value.inflation_region}</div>
                <div>Fwd EPS: {data.fair_value.forward_eps_source}</div>
                <div>Confidence: {data.fair_value.confidence_label}</div>
              </div>
            </div>
            <div className="rounded-[10px] border border-slate-800 bg-slate-950 p-4">
              <div className="mb-3 flex items-center gap-2 text-rose-100">
                <Bell className="h-4 w-4" />
                <h2 className="text-sm font-black">Alerts</h2>
              </div>
              <div className="space-y-2">
                {data.fair_value.alerts.length ? data.fair_value.alerts.map((alert) => (
                  <div key={alert} className="rounded border border-slate-800 bg-black/60 px-2 py-2 text-xs text-slate-300">{alert}</div>
                )) : <div className="text-xs text-slate-500">Aktif uyarı yok.</div>}
              </div>
            </div>
            <div className="rounded-[10px] border border-slate-800 bg-slate-950 p-4">
              <h2 className="mb-3 text-sm font-black text-slate-100">Not</h2>
              <p className="text-xs leading-5 text-slate-400">
                Bu ekran temel değerleme modelidir. Eksik finansal alanlarda yöntemler otomatik null kalır;
                confidence değeri yöntemler arası ayrışmayı gösterir.
              </p>
            </div>
          </aside>
        </div>
      </div>
    </main>
  );
}
