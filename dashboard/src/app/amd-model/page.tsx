"use client";

import Link from "next/link";
import { Search, Target } from "lucide-react";
import { useMemo, useState } from "react";
import { AnalysisStatusBanner } from "@/components/dashboard/analysis-status-banner";
import { Input } from "@/components/ui/input";
import { useAnalysisData } from "@/hooks/use-analysis-data";
import { formatDateTime, formatPrice } from "@/lib/formatters";
import type { ReportData, ReportSignal } from "@/lib/types/report";

const PAGE_SIZE = 25;

type SortKey = "symbol" | "score" | "phase" | "bias" | "status";
type SortDirection = "asc" | "desc";

function tone(value: string) {
  if (value === "BULLISH" || value === "CONFIRMED") return "border-emerald-500/30 bg-emerald-500/10 text-emerald-200";
  if (value === "BEARISH") return "border-rose-500/30 bg-rose-500/10 text-rose-200";
  return "border-amber-500/30 bg-amber-500/10 text-amber-100";
}

export default function AmdModelPage() {
  const { data, status, error, isLoading, reload } = useAnalysisData<ReportData>();
  const [search, setSearch] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("score");
  const [sortDirection, setSortDirection] = useState<SortDirection>("desc");
  const [page, setPage] = useState(1);

  const rows = useMemo(() => {
    const normalized = search.trim().toLowerCase();
    const filtered = (data?.signals ?? [])
      .filter((signal) => signal.amd_model)
      .filter((signal) => {
        if (!normalized) return true;
        const amd = signal.amd_model;
        return (
          signal.symbol.toLowerCase().includes(normalized) ||
          amd?.model_bias.toLowerCase().includes(normalized) ||
          amd?.phase.toLowerCase().includes(normalized) ||
          amd?.summary.toLowerCase().includes(normalized)
        );
      });
    const value = (signal: ReportSignal) => {
      const amd = signal.amd_model;
      switch (sortKey) {
        case "symbol":
          return signal.symbol;
        case "score":
          return amd?.score ?? 0;
        case "phase":
          return amd?.phase ?? "";
        case "bias":
          return amd?.model_bias ?? "";
        case "status":
          return amd?.status ?? "";
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
    return <div className="flex min-h-screen items-center justify-center bg-black text-slate-100">AMD modelleri yükleniyor...</div>;
  }

  if (!data) {
    return <div className="flex min-h-screen items-center justify-center bg-black text-rose-300">{error || "AMD model verisi bulunamadı."}</div>;
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
    setSortDirection(key === "symbol" || key === "phase" || key === "bias" || key === "status" ? "asc" : "desc");
  };
  const label = (key: SortKey, text: string) => `${text}${sortKey === key ? (sortDirection === "asc" ? " ↑" : " ↓") : ""}`;

  return (
    <main className="min-h-screen bg-black px-6 py-8 text-slate-50">
      <div className="mx-auto max-w-[1600px] space-y-6">
        <section className="rounded-3xl border border-cyan-500/20 bg-[radial-gradient(circle_at_top_left,#0e749055,transparent_36%),linear-gradient(135deg,#020617,#111827_55%,#020617)] p-6">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-4xl">
              <div className="inline-flex items-center gap-2 rounded border border-cyan-500/40 bg-cyan-500/10 px-3 py-1 text-xs font-bold uppercase tracking-[0.18em] text-cyan-100">
                <Target className="h-4 w-4" />
                CandelaCharts AMD Model
              </div>
              <h1 className="mt-4 text-4xl font-bold tracking-tight">Intraday Power of 3: Accumulation, Manipulation, Distribution</h1>
              <p className="mt-3 text-sm leading-6 text-slate-300">
                BIST hisselerinde LTF intraday veriyi okuyarak accumulation aralığını, liquidity sweep/Judas hareketini,
                CISD onayını ve distribution hedeflerini aynı ekranda takip eder.
              </p>
              <p className="mt-2 text-xs text-slate-500">Son snapshot: {formatDateTime(data.generated_at)}</p>
            </div>
            <div className="grid grid-cols-3 gap-3 text-sm lg:min-w-[520px]">
              <div className="rounded-2xl border border-slate-800 bg-slate-950/70 p-4">
                <div className="text-xs text-slate-500">Intraday Kapsam</div>
                <div className="mt-2 text-3xl font-bold text-slate-100">{rows.length}</div>
              </div>
              <div className="rounded-2xl border border-slate-800 bg-slate-950/70 p-4">
                <div className="text-xs text-slate-500">CISD Onaylı</div>
                <div className="mt-2 text-3xl font-bold text-emerald-200">{rows.filter((row) => row.amd_model?.status === "CONFIRMED").length}</div>
              </div>
              <div className="rounded-2xl border border-slate-800 bg-slate-950/70 p-4">
                <div className="text-xs text-slate-500">Bull / Bear</div>
                <div className="mt-2 text-3xl font-bold text-cyan-200">
                  {rows.filter((row) => row.amd_model?.model_bias === "BULLISH").length}/{rows.filter((row) => row.amd_model?.model_bias === "BEARISH").length}
                </div>
              </div>
            </div>
          </div>
        </section>

        <AnalysisStatusBanner status={status} generatedAt={data.generated_at} onRefresh={refreshNow} />

        <section className="grid gap-4 md:grid-cols-3">
          {[
            ["Accumulation", "Pozisyonların sessizce kurulduğu sıkışma aralığı. Dashboard mavi kutuyla range sınırlarını gösterir."],
            ["Manipulation", "Likiditeyi süpüren false move. Sweep yönü bullish/bearish modeli belirler."],
            ["Distribution", "CISD sonrası gerçek genişleme. 1.0, 2.0 ve 4.0 projection seviyeleri hedef okuması sağlar."],
          ].map(([title, copy]) => (
            <div key={title} className="rounded-2xl border border-slate-800 bg-slate-950/70 p-4">
              <h2 className="text-sm font-bold text-slate-100">{title}</h2>
              <p className="mt-2 text-xs leading-5 text-slate-400">{copy}</p>
            </div>
          ))}
        </section>

        <section className="rounded-2xl border border-slate-800 bg-slate-950/80 p-5">
          <div className="mb-4 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div>
              <h2 className="text-xl font-semibold text-slate-100">AMD Model Tablosu</h2>
              <p className="text-sm text-slate-500">Skor; sweep reddi, CISD, displacement ve HTF sweep uyumuna göre sıralanır.</p>
            </div>
            <div className="relative w-full md:max-w-sm">
              <Search className="absolute left-3 top-3.5 h-4 w-4 text-slate-500" />
              <Input value={search} onChange={(event) => {
                setSearch(event.target.value);
                setPage(1);
              }} placeholder="Hisse, faz veya bias ara..." className="border-slate-800 bg-black pl-9 text-slate-100" />
            </div>
          </div>
          <div className="overflow-hidden rounded-xl border border-slate-800">
            <table className="w-full text-sm">
              <thead className="bg-black text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-4 py-3 text-left"><button type="button" onClick={() => updateSort("symbol")}>{label("symbol", "Hisse")}</button></th>
                  <th className="px-4 py-3 text-left"><button type="button" onClick={() => updateSort("status")}>{label("status", "Durum")}</button></th>
                  <th className="px-4 py-3 text-left"><button type="button" onClick={() => updateSort("bias")}>{label("bias", "Model")}</button></th>
                  <th className="px-4 py-3 text-left"><button type="button" onClick={() => updateSort("phase")}>{label("phase", "Faz")}</button></th>
                  <th className="px-4 py-3 text-right"><button type="button" onClick={() => updateSort("score")}>{label("score", "Skor")}</button></th>
                  <th className="px-4 py-3 text-left">CISD / Sweep</th>
                  <th className="px-4 py-3 text-left">Özet</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {pageRows.map((signal) => {
                  const amd = signal.amd_model;
                  if (!amd) return null;
                  return (
                    <tr key={signal.symbol} className="bg-slate-950/50 hover:bg-slate-900">
                      <td className="px-4 py-3">
                        <Link href={`/amd-model/${signal.symbol}`} className="font-bold text-cyan-200 hover:text-cyan-100">{signal.symbol}</Link>
                        <div className="text-xs text-slate-500">{formatPrice(signal.price)}</div>
                      </td>
                      <td className="px-4 py-3"><span className={`inline-flex rounded border px-2 py-1 text-xs font-bold ${tone(amd.status)}`}>{amd.status}</span></td>
                      <td className="px-4 py-3"><span className={`inline-flex rounded border px-2 py-1 text-xs font-bold ${tone(amd.model_bias)}`}>{amd.model_bias}</span></td>
                      <td className="px-4 py-3 text-slate-100">{amd.phase}</td>
                      <td className="px-4 py-3 text-right font-bold text-yellow-100">{amd.score.toFixed(1)}</td>
                      <td className="px-4 py-3 text-xs text-slate-400">{amd.cisd?.confirmed ? "CISD onaylı" : "CISD bekliyor"} · {amd.sweep?.liquidity_pool ?? "-"}</td>
                      <td className="px-4 py-3 text-xs text-slate-400">{amd.summary}</td>
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

        <p className="text-xs leading-5 text-slate-500">
          Bu ekran otomatik AL/SAT botu değildir. AMD/CISD yapıları eğitim ve filtreleme amaçlıdır; finansal tavsiye olarak kullanılmamalıdır.
        </p>
      </div>
    </main>
  );
}
