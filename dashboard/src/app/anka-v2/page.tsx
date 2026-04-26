"use client";

import Link from "next/link";
import { Activity, Flame, Gauge, Search, ShieldCheck, TrendingDown, TrendingUp } from "lucide-react";
import { useMemo, useState } from "react";
import { AnalysisStatusBanner } from "@/components/dashboard/analysis-status-banner";
import { Input } from "@/components/ui/input";
import { useAnalysisData } from "@/hooks/use-analysis-data";
import { formatDateTime, formatPrice } from "@/lib/formatters";
import type { ReportData, ReportSignal } from "@/lib/types/report";

const PAGE_SIZE = 25;

type SortKey = "symbol" | "decision" | "score" | "valley" | "relativeVolume" | "calibration";
type SortDirection = "asc" | "desc";

function StatCard({ label, value, note }: { label: string; value: string | number; note: string }) {
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-4">
      <div className="text-xs uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-2 text-2xl font-semibold text-slate-100">{value}</div>
      <div className="mt-1 text-xs text-slate-400">{note}</div>
    </div>
  );
}

function decisionClass(decision: string) {
  if (decision.includes("ALIŞ")) {
    return "border-emerald-500/30 bg-emerald-500/10 text-emerald-200";
  }
  if (decision.includes("SATIŞ")) {
    return "border-rose-500/30 bg-rose-500/10 text-rose-200";
  }
  return "border-amber-500/30 bg-amber-500/10 text-amber-100";
}

function calibrationText(signal: ReportSignal) {
  const calibration = signal.anka_v2?.calibration;
  if (!calibration) {
    return "-";
  }
  return `${calibration.label} (${calibration.total_success_rate ?? "-"}%)`;
}

function compareValues(left: string | number | null | undefined, right: string | number | null | undefined) {
  if (typeof left === "string" || typeof right === "string") {
    return String(left ?? "").localeCompare(String(right ?? ""), "tr");
  }
  return (left ?? 0) - (right ?? 0);
}

export default function AnkaV2Page() {
  const { data, status, error, isLoading, reload } = useAnalysisData<ReportData>();
  const [search, setSearch] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("score");
  const [sortDirection, setSortDirection] = useState<SortDirection>("desc");
  const [page, setPage] = useState(1);

  const ankaSignals = useMemo(() => {
    const normalized = search.trim().toLowerCase();
    const rows = (data?.signals ?? [])
      .filter((signal) => signal.anka_v2)
      .filter((signal) => {
        if (!normalized) {
          return true;
        }
        return (
          signal.symbol.toLowerCase().includes(normalized) ||
          signal.anka_v2?.synthesis_decision.toLowerCase().includes(normalized) ||
          signal.anka_v2?.valley.name.toLowerCase().includes(normalized)
        );
      });
    const value = (signal: ReportSignal) => {
      const anka = signal.anka_v2;
      switch (sortKey) {
        case "symbol":
          return signal.symbol;
        case "decision":
          return anka?.synthesis_decision ?? "";
        case "score":
          return anka?.synthesis_score ?? 0;
        case "valley":
          return anka?.valley.score ?? 0;
        case "relativeVolume":
          return anka?.knn_volume.relative_volume ?? 0;
        case "calibration":
          return anka?.calibration.total_success_rate ?? 0;
      }
    };
    return [...rows].sort((left, right) => {
      const direction = sortDirection === "asc" ? 1 : -1;
      return compareValues(value(left), value(right)) * direction;
    });
  }, [data?.signals, search, sortDirection, sortKey]);

  if (isLoading) {
    return <div className="flex min-h-screen items-center justify-center bg-slate-950 text-slate-100">ANKA v2 yükleniyor...</div>;
  }

  if (!data) {
    return <div className="flex min-h-screen items-center justify-center bg-slate-950 text-rose-300">{error || "ANKA v2 verisi bulunamadı."}</div>;
  }

  const refreshNow = async () => {
    await fetch("/api/analysis/refresh", { method: "POST" });
    await reload();
  };

  const strongBuys = ankaSignals.filter((signal) => signal.anka_v2?.synthesis_decision.includes("ALIŞ")).length;
  const strongSells = ankaSignals.filter((signal) => signal.anka_v2?.synthesis_decision.includes("SATIŞ")).length;
  const calibrated = ankaSignals.filter((signal) => signal.anka_v2?.calibration.status === "CALIBRATED").length;
  const ashPhase = ankaSignals.filter((signal) => signal.anka_v2?.is_ash_phase).length;
  const totalPages = Math.max(1, Math.ceil(ankaSignals.length / PAGE_SIZE));
  const currentPage = Math.min(page, totalPages);
  const pageRows = ankaSignals.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE);

  const updateSort = (nextKey: SortKey) => {
    setPage(1);
    if (nextKey === sortKey) {
      setSortDirection((current) => (current === "asc" ? "desc" : "asc"));
      return;
    }
    setSortKey(nextKey);
    setSortDirection(nextKey === "symbol" || nextKey === "decision" ? "asc" : "desc");
  };

  const sortLabel = (key: SortKey, label: string) => `${label}${sortKey === key ? (sortDirection === "asc" ? " ↑" : " ↓") : ""}`;

  return (
    <main className="min-h-screen bg-slate-950 px-6 py-8 text-slate-50">
      <div className="mx-auto max-w-[1600px] space-y-6">
        <section className="overflow-hidden rounded-3xl border border-cyan-500/20 bg-[radial-gradient(circle_at_top_left,#0f766e33,transparent_35%),linear-gradient(135deg,#020617,#0f172a_60%,#020617)] p-6">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-3xl">
              <div className="inline-flex items-center gap-2 rounded-full border border-cyan-400/30 bg-cyan-400/10 px-3 py-1 text-xs uppercase tracking-[0.2em] text-cyan-200">
                <Flame className="h-3.5 w-3.5" />
                ANKA v2.0
              </div>
              <h1 className="mt-4 text-4xl font-bold tracking-tight text-slate-50">
                Yedi Vadi, kNN hacim ve Fibonacci senteziyle hisse ekranı
              </h1>
              <p className="mt-3 text-sm leading-6 text-slate-300">
                Bu sayfa mevcut teknik skoru bozmadan ANKA v2.0 sentez puanını, canlı başarı kalibrasyonunu,
                rölatif hacim örüntülerini ve piyasa fazlarını tek ekranda toplar.
              </p>
              <p className="mt-2 text-xs text-slate-500">Son snapshot: {formatDateTime(data.generated_at)}</p>
            </div>
            <div className="grid grid-cols-2 gap-3 text-sm md:grid-cols-4 lg:min-w-[620px]">
              <StatCard label="ANKA Kapsamı" value={ankaSignals.length} note="v2 payload üreten hisse" />
              <StatCard label="Alış Sentezi" value={strongBuys} note="ALIŞ / GÜÇLÜ ALIŞ" />
              <StatCard label="Satış Sentezi" value={strongSells} note="SATIŞ / GÜÇLÜ SATIŞ" />
              <StatCard label="Kalibre" value={calibrated} note={`${ashPhase} hisse Kül Fazı`} />
            </div>
          </div>
        </section>

        <AnalysisStatusBanner status={status} generatedAt={data.generated_at} onRefresh={refreshNow} />

        <section className="grid gap-4 lg:grid-cols-3">
          <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5 lg:col-span-2">
            <div className="mb-4 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <div>
                <h2 className="text-xl font-semibold text-slate-100">ANKA v2 Sentez Listesi</h2>
                <p className="text-sm text-slate-400">Sentez skoru, vadi, kNN hacim ve kalibrasyon birlikte gösterilir.</p>
              </div>
              <div className="relative w-full md:max-w-xs">
                <Search className="absolute left-3 top-3.5 h-4 w-4 text-slate-500" />
                <Input
                  value={search}
                  onChange={(event) => {
                    setSearch(event.target.value);
                    setPage(1);
                  }}
                  placeholder="Hisse, karar veya vadi ara..."
                  className="border-slate-800 bg-slate-950 pl-9 text-slate-100"
                />
              </div>
            </div>

            <div className="overflow-hidden rounded-xl border border-slate-800">
              <div className="max-h-[720px] overflow-auto">
                <table className="w-full text-sm">
                  <thead className="sticky top-0 z-10 bg-slate-950 text-xs uppercase tracking-wide text-slate-500">
                    <tr>
                      <th className="px-4 py-3 text-left"><button type="button" onClick={() => updateSort("symbol")}>{sortLabel("symbol", "Hisse")}</button></th>
                      <th className="px-4 py-3 text-left"><button type="button" onClick={() => updateSort("decision")}>{sortLabel("decision", "Sentez")}</button></th>
                      <th className="px-4 py-3 text-right"><button type="button" onClick={() => updateSort("score")}>{sortLabel("score", "Skor")}</button></th>
                      <th className="px-4 py-3 text-left"><button type="button" onClick={() => updateSort("valley")}>{sortLabel("valley", "Vadi")}</button></th>
                      <th className="px-4 py-3 text-right"><button type="button" onClick={() => updateSort("relativeVolume")}>{sortLabel("relativeVolume", "Rel. Hacim")}</button></th>
                      <th className="px-4 py-3 text-left"><button type="button" onClick={() => updateSort("calibration")}>{sortLabel("calibration", "Kalibrasyon")}</button></th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800">
                    {pageRows.map((signal) => {
                      const anka = signal.anka_v2;
                      if (!anka) {
                        return null;
                      }
                      return (
                        <tr key={signal.symbol} className="bg-slate-950/40 hover:bg-slate-900/80">
                          <td className="px-4 py-3">
                            <Link href={`/anka-v2/${signal.symbol}`} className="font-semibold text-cyan-200 hover:text-cyan-100">
                              {signal.symbol}
                            </Link>
                            <div className="text-xs text-slate-500">{formatPrice(signal.price)}</div>
                          </td>
                          <td className="px-4 py-3">
                            <span className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-semibold ${decisionClass(anka.synthesis_decision)}`}>
                              {anka.synthesis_decision}
                            </span>
                            <div className="mt-1 text-xs text-slate-500">{anka.primary_signal}</div>
                          </td>
                          <td className="px-4 py-3 text-right font-semibold text-slate-100">{anka.synthesis_score.toFixed(1)}</td>
                          <td className="px-4 py-3">
                            <div className="font-medium text-slate-200">{anka.valley.name}</div>
                            <div className="text-xs text-slate-500">{anka.valley.score.toFixed(1)} puan</div>
                          </td>
                          <td className="px-4 py-3 text-right">
                            <div className="font-semibold text-slate-100">{anka.knn_volume.relative_volume.toFixed(2)}x</div>
                            <div className="text-xs text-slate-500">{anka.knn_volume.label}</div>
                          </td>
                          <td className="px-4 py-3 text-slate-300">{calibrationText(signal)}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
            <div className="mt-4 flex items-center justify-between text-sm text-slate-400">
              <span>{ankaSignals.length} kayıt · Sayfa {currentPage}/{totalPages}</span>
              <div className="flex gap-2">
                <button type="button" disabled={currentPage <= 1} onClick={() => setPage((value) => Math.max(1, value - 1))} className="rounded border border-slate-800 px-3 py-1 disabled:opacity-40">Önceki</button>
                <button type="button" disabled={currentPage >= totalPages} onClick={() => setPage((value) => Math.min(totalPages, value + 1))} className="rounded border border-slate-800 px-3 py-1 disabled:opacity-40">Sonraki</button>
              </div>
            </div>
          </div>

          <aside className="space-y-4">
            <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5">
              <div className="flex items-center gap-2 text-cyan-200">
                <Gauge className="h-5 w-5" />
                <h2 className="font-semibold">Sentez Mantığı</h2>
              </div>
              <div className="mt-4 space-y-3 text-sm text-slate-300">
                <div className="flex gap-3">
                  <Activity className="mt-0.5 h-4 w-4 text-amber-200" />
                  <p>kNN motoru mum gövdesi, gölgeler, kapanış konumu ve rölatif hacim üzerinden benzer örüntüleri okur.</p>
                </div>
                <div className="flex gap-3">
                  <ShieldCheck className="mt-0.5 h-4 w-4 text-emerald-200" />
                  <p>Fibonacci destek/direnç bölgesi sentez puanına bonus veya temkin uyarısı olarak girer.</p>
                </div>
                <div className="flex gap-3">
                  <TrendingUp className="mt-0.5 h-4 w-4 text-cyan-200" />
                  <p>Son 50 bardaki 3-bar ufuk başarısı panelde Kalibre, Orta, Zayıf veya Ters olarak gösterilir.</p>
                </div>
              </div>
            </div>

            <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5">
              <div className="flex items-center gap-2 text-slate-100">
                <TrendingDown className="h-5 w-5 text-rose-200" />
                <h2 className="font-semibold">Risk Notu</h2>
              </div>
              <p className="mt-3 text-sm leading-6 text-slate-400">
                ANKA v2.0 istatistiksel ve teknik teyit ekranıdır. Hiçbir sinyal tek başına yatırım kararı değildir;
                özellikle Kül Fazı ve Zayıf/Ters kalibrasyonda ek teyit aranmalıdır.
              </p>
            </div>
          </aside>
        </section>
      </div>
    </main>
  );
}
