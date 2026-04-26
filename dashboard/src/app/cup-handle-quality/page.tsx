"use client";

import Link from "next/link";
import { Search, Trophy } from "lucide-react";
import { useMemo, useState } from "react";
import { AnalysisStatusBanner } from "@/components/dashboard/analysis-status-banner";
import { Input } from "@/components/ui/input";
import { useAnalysisData } from "@/hooks/use-analysis-data";
import { formatDateTime, formatPrice } from "@/lib/formatters";
import type { ReportData, ReportSignal } from "@/lib/types/report";

const PAGE_SIZE = 25;

type SortKey = "symbol" | "status" | "symmetry" | "depth" | "breakout" | "score" | "target";
type SortDirection = "asc" | "desc";

function tone(status: string) {
  if (status === "CONFIRMED") return "border-emerald-500/30 bg-emerald-500/10 text-emerald-200";
  if (status === "DEVELOPING") return "border-yellow-500/30 bg-yellow-500/10 text-yellow-100";
  return "border-slate-700 bg-slate-900 text-slate-300";
}

export default function CupHandleQualityPage() {
  const { data, status, error, isLoading, reload } = useAnalysisData<ReportData>();
  const [search, setSearch] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("score");
  const [sortDirection, setSortDirection] = useState<SortDirection>("desc");
  const [page, setPage] = useState(1);

  const rows = useMemo(() => {
    const normalized = search.trim().toLowerCase();
    const filtered = (data?.signals ?? [])
      .filter((signal) => signal.cup_handle_quality)
      .filter((signal) => {
        if (!normalized) return true;
        return (
          signal.symbol.toLowerCase().includes(normalized) ||
          signal.cup_handle_quality?.status.toLowerCase().includes(normalized)
        );
      });
    const value = (signal: ReportSignal) => {
      const cup = signal.cup_handle_quality;
      switch (sortKey) {
        case "symbol":
          return signal.symbol;
        case "status":
          return cup?.status ?? "";
        case "symmetry":
          return cup?.cup_symmetry ?? 0;
        case "depth":
          return cup?.handle_depth_pct ?? 0;
        case "breakout":
          return cup?.breakout_quality ?? 0;
        case "score":
          return cup?.score ?? 0;
        case "target":
          return cup?.target_price ?? 0;
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
    return <div className="flex min-h-screen items-center justify-center bg-black text-slate-100">Cup & Handle taranıyor...</div>;
  }

  if (!data) {
    return <div className="flex min-h-screen items-center justify-center bg-black text-rose-300">{error || "Cup & Handle verisi bulunamadı."}</div>;
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
    setSortDirection(key === "symbol" || key === "status" ? "asc" : "desc");
  };
  const label = (key: SortKey, text: string) => `${text}${sortKey === key ? (sortDirection === "asc" ? " ↑" : " ↓") : ""}`;

  return (
    <main className="min-h-screen bg-black px-6 py-8 text-slate-50">
      <div className="mx-auto max-w-[1600px] space-y-6">
        <section className="rounded-3xl border border-blue-500/20 bg-[radial-gradient(circle_at_top_left,#1d4ed833,transparent_38%),linear-gradient(135deg,#020617,#0f172a_58%,#020617)] p-6">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-3xl">
              <div className="inline-flex items-center gap-2 rounded border border-blue-500/40 bg-blue-500/10 px-3 py-1 text-xs font-bold uppercase tracking-[0.18em] text-blue-100">
                <Trophy className="h-4 w-4" />
                Cup and Handle Quality
              </div>
              <h1 className="mt-4 text-4xl font-bold tracking-tight">Cup rim recovery, handle depth ve breakout kalitesi</h1>
              <p className="mt-3 text-sm leading-6 text-slate-300">
                AGPro yaklaşımına göre sol rim, cup tabanı, sağ rim, handle pullback, breakout davranışı ve ölçülen target çizgisi ayrı kalite katmanlarıyla izlenir.
              </p>
              <p className="mt-2 text-xs text-slate-500">Son snapshot: {formatDateTime(data.generated_at)}</p>
            </div>
            <div className="grid grid-cols-3 gap-3 text-sm lg:min-w-[520px]">
              <div className="rounded-2xl border border-slate-800 bg-slate-950/70 p-4">
                <div className="text-xs text-slate-500">Taranan</div>
                <div className="mt-2 text-3xl font-bold text-slate-100">{rows.length}</div>
              </div>
              <div className="rounded-2xl border border-slate-800 bg-slate-950/70 p-4">
                <div className="text-xs text-slate-500">Onaylı</div>
                <div className="mt-2 text-3xl font-bold text-emerald-200">{rows.filter((row) => row.cup_handle_quality?.is_confirmed).length}</div>
              </div>
              <div className="rounded-2xl border border-slate-800 bg-slate-950/70 p-4">
                <div className="text-xs text-slate-500">Gelişen</div>
                <div className="mt-2 text-3xl font-bold text-yellow-200">{rows.filter((row) => row.cup_handle_quality?.status === "DEVELOPING").length}</div>
              </div>
            </div>
          </div>
        </section>

        <AnalysisStatusBanner status={status} generatedAt={data.generated_at} onRefresh={refreshNow} />

        <section className="rounded-2xl border border-slate-800 bg-slate-950/80 p-5">
          <div className="mb-4 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div>
              <h2 className="text-xl font-semibold text-slate-100">Cup & Handle Kalite Tablosu</h2>
              <p className="text-sm text-slate-500">Cup symmetry, handle depth, breakout quality ve final score’a göre sıralanır.</p>
            </div>
            <div className="relative w-full md:max-w-sm">
              <Search className="absolute left-3 top-3.5 h-4 w-4 text-slate-500" />
              <Input value={search} onChange={(event) => {
                setSearch(event.target.value);
                setPage(1);
              }} placeholder="Hisse veya durum ara..." className="border-slate-800 bg-black pl-9 text-slate-100" />
            </div>
          </div>
          <div className="overflow-hidden rounded-xl border border-slate-800">
            <table className="w-full text-sm">
              <thead className="bg-black text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-4 py-3 text-left"><button type="button" onClick={() => updateSort("symbol")}>{label("symbol", "Hisse")}</button></th>
                  <th className="px-4 py-3 text-left"><button type="button" onClick={() => updateSort("status")}>{label("status", "Durum")}</button></th>
                  <th className="px-4 py-3 text-right"><button type="button" onClick={() => updateSort("symmetry")}>{label("symmetry", "Cup Symmetry")}</button></th>
                  <th className="px-4 py-3 text-right"><button type="button" onClick={() => updateSort("depth")}>{label("depth", "Handle Depth")}</button></th>
                  <th className="px-4 py-3 text-right"><button type="button" onClick={() => updateSort("breakout")}>{label("breakout", "Breakout Quality")}</button></th>
                  <th className="px-4 py-3 text-right"><button type="button" onClick={() => updateSort("score")}>{label("score", "Score")}</button></th>
                  <th className="px-4 py-3 text-right"><button type="button" onClick={() => updateSort("target")}>{label("target", "Target")}</button></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {pageRows.map((signal) => {
                  const cup = signal.cup_handle_quality;
                  if (!cup) return null;
                  return (
                    <tr key={signal.symbol} className="bg-slate-950/50 hover:bg-slate-900">
                      <td className="px-4 py-3">
                        <Link href={`/cup-handle-quality/${signal.symbol}`} className="font-bold text-cyan-200 hover:text-cyan-100">{signal.symbol}</Link>
                        <div className="text-xs text-slate-500">{formatPrice(signal.price)}</div>
                      </td>
                      <td className="px-4 py-3">
                        <span className={`inline-flex rounded border px-2 py-1 text-xs font-bold ${tone(cup.status)}`}>{cup.status}</span>
                      </td>
                      <td className="px-4 py-3 text-right text-slate-100">{cup.cup_symmetry ?? "-"}</td>
                      <td className="px-4 py-3 text-right text-slate-100">{cup.handle_depth_pct !== null ? `${cup.handle_depth_pct}%` : "-"}</td>
                      <td className="px-4 py-3 text-right text-slate-100">{cup.breakout_quality ?? "-"}</td>
                      <td className="px-4 py-3 text-right font-bold text-slate-100">{cup.score ?? "-"}</td>
                      <td className="px-4 py-3 text-right text-emerald-200">{formatPrice(cup.target_price)}</td>
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
