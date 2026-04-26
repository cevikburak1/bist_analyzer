"use client";

import Link from "next/link";
import { BrainCircuit, Search } from "lucide-react";
import { useMemo, useState } from "react";
import { AnalysisStatusBanner } from "@/components/dashboard/analysis-status-banner";
import { Input } from "@/components/ui/input";
import { useAnalysisData } from "@/hooks/use-analysis-data";
import { formatDateTime, formatPrice } from "@/lib/formatters";
import type { ReportData, ReportSignal } from "@/lib/types/report";

const PAGE_SIZE = 25;

type SortKey = "symbol" | "synthesis" | "layer" | "lr" | "knn" | "alerts";
type SortDirection = "asc" | "desc";

function badgeTone(value: string) {
  if (value.includes("ALIŞ")) return "border-emerald-500/30 bg-emerald-500/10 text-emerald-200";
  if (value.includes("SATIŞ")) return "border-rose-500/30 bg-rose-500/10 text-rose-200";
  return "border-amber-500/30 bg-amber-500/10 text-amber-100";
}

export default function AnkaEnginePage() {
  const { data, status, error, isLoading, reload } = useAnalysisData<ReportData>();
  const [search, setSearch] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("synthesis");
  const [sortDirection, setSortDirection] = useState<SortDirection>("desc");
  const [page, setPage] = useState(1);

  const rows = useMemo(() => {
    const normalized = search.trim().toLowerCase();
    const filtered = (data?.signals ?? [])
      .filter((signal) => signal.anka_v2)
      .filter((signal) => {
        if (!normalized) return true;
        const anka = signal.anka_v2;
        return (
          signal.symbol.toLowerCase().includes(normalized) ||
          anka?.layer_engine.recommendation.toLowerCase().includes(normalized) ||
          anka?.lr_engine.direction.toLowerCase().includes(normalized) ||
          anka?.knn_pattern.prediction.toLowerCase().includes(normalized)
        );
      });
    const value = (signal: ReportSignal) => {
      const anka = signal.anka_v2;
      switch (sortKey) {
        case "symbol":
          return signal.symbol;
        case "synthesis":
          return anka?.synthesis_score ?? 0;
        case "layer":
          return anka?.layer_engine.score ?? 0;
        case "lr":
          return anka?.lr_engine.score ?? 0;
        case "knn":
          return anka?.knn_pattern.score ?? 0;
        case "alerts":
          return anka?.alerts.length ?? 0;
      }
    };
    return [...filtered].sort((left, right) => {
      const leftValue = value(left);
      const rightValue = value(right);
      const result = typeof leftValue === "string" || typeof rightValue === "string"
        ? String(leftValue).localeCompare(String(rightValue), "tr")
        : leftValue - rightValue;
      return result * (sortDirection === "asc" ? 1 : -1);
    });
  }, [data?.signals, search, sortDirection, sortKey]);

  if (isLoading) {
    return <div className="flex min-h-screen items-center justify-center bg-slate-950 text-slate-100">ANKA motorları yükleniyor...</div>;
  }

  if (!data) {
    return <div className="flex min-h-screen items-center justify-center bg-slate-950 text-rose-300">{error || "ANKA motor verisi bulunamadı."}</div>;
  }

  const refreshNow = async () => {
    await fetch("/api/analysis/refresh", { method: "POST" });
    await reload();
  };
  const totalPages = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));
  const currentPage = Math.min(page, totalPages);
  const pageRows = rows.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE);
  const updateSort = (key: SortKey) => {
    setPage(1);
    if (key === sortKey) {
      setSortDirection((current) => (current === "asc" ? "desc" : "asc"));
      return;
    }
    setSortKey(key);
    setSortDirection(key === "symbol" ? "asc" : "desc");
  };
  const label = (key: SortKey, text: string) => `${text}${sortKey === key ? (sortDirection === "asc" ? " ↑" : " ↓") : ""}`;

  return (
    <main className="min-h-screen bg-black px-6 py-8 text-slate-50">
      <div className="mx-auto max-w-[1600px] space-y-6">
        <section className="rounded-3xl border border-yellow-500/20 bg-[radial-gradient(circle_at_top_left,#14532d99,transparent_36%),linear-gradient(135deg,#020617,#020617_50%,#111827)] p-6">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-3xl">
              <div className="inline-flex items-center gap-2 rounded border border-yellow-500/40 bg-yellow-500/10 px-3 py-1 text-xs font-bold uppercase tracking-[0.18em] text-yellow-100">
                <BrainCircuit className="h-4 w-4" />
                ANKA Motor Grafiği
              </div>
              <h1 className="mt-4 text-4xl font-bold tracking-tight">LR + kNN + K1-K5 katman sentezi</h1>
              <p className="mt-3 text-sm leading-6 text-slate-300">
                Bu sayfa ANKA v2.0’ın karar motorlarını ayrı ayrı gösterir: Lineer Regresyon trend yoğunluğu,
                sabit parametreli kNN örüntü tahmini, K1-K5 katman akıl yürütme ve nihai ağırlıklı sentez.
              </p>
              <p className="mt-2 text-xs text-slate-500">Son snapshot: {formatDateTime(data.generated_at)}</p>
            </div>
            <div className="grid grid-cols-3 gap-3 text-sm lg:min-w-[520px]">
              <div className="rounded-2xl border border-slate-800 bg-slate-950/70 p-4">
                <div className="text-xs text-slate-500">Motorlu Hisse</div>
                <div className="mt-2 text-3xl font-bold text-slate-100">{rows.length}</div>
              </div>
              <div className="rounded-2xl border border-slate-800 bg-slate-950/70 p-4">
                <div className="text-xs text-slate-500">Güçlü Sentez</div>
                <div className="mt-2 text-3xl font-bold text-emerald-200">{rows.filter((row) => row.anka_v2?.synthesis_decision.includes("GÜÇLÜ")).length}</div>
              </div>
              <div className="rounded-2xl border border-slate-800 bg-slate-950/70 p-4">
                <div className="text-xs text-slate-500">Aktif Uyarı</div>
                <div className="mt-2 text-3xl font-bold text-yellow-200">{rows.reduce((sum, row) => sum + (row.anka_v2?.alerts.length ?? 0), 0)}</div>
              </div>
            </div>
          </div>
        </section>

        <AnalysisStatusBanner status={status} generatedAt={data.generated_at} onRefresh={refreshNow} />

        <section className="rounded-2xl border border-slate-800 bg-slate-950/80 p-5">
          <div className="mb-4 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div>
              <h2 className="text-xl font-semibold text-slate-100">Motor Sentez Tablosu</h2>
              <p className="text-sm text-slate-500">K.Motor %40, LR %30, kNN %30 ağırlığıyla sıralanır.</p>
            </div>
            <div className="relative w-full md:max-w-sm">
              <Search className="absolute left-3 top-3.5 h-4 w-4 text-slate-500" />
              <Input value={search} onChange={(event) => {
                setSearch(event.target.value);
                setPage(1);
              }} placeholder="Hisse veya motor sinyali ara..." className="border-slate-800 bg-black pl-9 text-slate-100" />
            </div>
          </div>
          <div className="overflow-hidden rounded-xl border border-slate-800">
            <table className="w-full text-sm">
              <thead className="bg-black text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-4 py-3 text-left"><button type="button" onClick={() => updateSort("symbol")}>{label("symbol", "Hisse")}</button></th>
                  <th className="px-4 py-3 text-left"><button type="button" onClick={() => updateSort("synthesis")}>{label("synthesis", "Sentez")}</button></th>
                  <th className="px-4 py-3 text-right"><button type="button" onClick={() => updateSort("layer")}>{label("layer", "K.Motor")}</button></th>
                  <th className="px-4 py-3 text-right"><button type="button" onClick={() => updateSort("lr")}>{label("lr", "LR")}</button></th>
                  <th className="px-4 py-3 text-right"><button type="button" onClick={() => updateSort("knn")}>{label("knn", "kNN")}</button></th>
                  <th className="px-4 py-3 text-left">Katman Zinciri</th>
                  <th className="px-4 py-3 text-left"><button type="button" onClick={() => updateSort("alerts")}>{label("alerts", "Uyarılar")}</button></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {pageRows.map((signal) => {
                  const anka = signal.anka_v2;
                  if (!anka) return null;
                  return (
                    <tr key={signal.symbol} className="bg-slate-950/50 hover:bg-slate-900">
                      <td className="px-4 py-3">
                        <Link href={`/anka-engine/${signal.symbol}`} className="font-bold text-cyan-200 hover:text-cyan-100">{signal.symbol}</Link>
                        <div className="text-xs text-slate-500">{formatPrice(signal.price)}</div>
                      </td>
                      <td className="px-4 py-3">
                        <span className={`inline-flex rounded border px-2 py-1 text-xs font-bold ${badgeTone(anka.synthesis_decision)}`}>{anka.synthesis_decision}</span>
                        <div className="mt-1 text-xs text-slate-500">{anka.synthesis_score.toFixed(1)}</div>
                      </td>
                      <td className="px-4 py-3 text-right text-slate-100">{anka.layer_engine.score.toFixed(1)}</td>
                      <td className="px-4 py-3 text-right text-slate-100">{anka.lr_engine.score.toFixed(1)}</td>
                      <td className="px-4 py-3 text-right text-slate-100">{anka.knn_pattern.score.toFixed(1)}</td>
                      <td className="px-4 py-3 font-mono text-xs text-yellow-100">{anka.layer_engine.chain}</td>
                      <td className="px-4 py-3 text-xs text-slate-400">{anka.alerts.slice(0, 2).join(" · ") || "-"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <div className="mt-4 flex items-center justify-between text-sm text-slate-400">
            <span>{rows.length} kayıt · Sayfa {currentPage}/{totalPages}</span>
            <div className="flex gap-2">
              <button type="button" disabled={currentPage <= 1} onClick={() => setPage((value) => Math.max(1, value - 1))} className="rounded border border-slate-800 px-3 py-1 disabled:opacity-40">Önceki</button>
              <button type="button" disabled={currentPage >= totalPages} onClick={() => setPage((value) => Math.min(totalPages, value + 1))} className="rounded border border-slate-800 px-3 py-1 disabled:opacity-40">Sonraki</button>
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}
