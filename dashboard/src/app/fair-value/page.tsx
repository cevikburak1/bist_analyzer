"use client";

import Link from "next/link";
import { Banknote, Search } from "lucide-react";
import { useMemo, useState } from "react";
import { Input } from "@/components/ui/input";
import { useBuffettData } from "@/hooks/use-buffett-data";
import { formatDateTime, formatPrice } from "@/lib/formatters";
import type { BuffettListItem, BuffettListResponse } from "@/lib/types/buffett";

const PAGE_SIZE = 25;

type SortKey = "symbol" | "price" | "fairValue" | "margin" | "confidence" | "sector";
type SortDirection = "asc" | "desc";

function pct(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  return `${value >= 0 ? "+" : ""}${value.toFixed(1)}%`;
}

export default function FairValuePage() {
  const { data, error, isLoading } = useBuffettData<BuffettListResponse>();
  const [search, setSearch] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("margin");
  const [sortDirection, setSortDirection] = useState<SortDirection>("desc");
  const [page, setPage] = useState(1);

  const rows = useMemo(() => {
    const normalized = search.trim().toLowerCase();
    const filtered = (data?.items ?? [])
      .filter((item) => item.fair_value !== undefined)
      .filter((item) => {
        if (!normalized) return true;
        return item.symbol.toLowerCase().includes(normalized) || item.name.toLowerCase().includes(normalized);
      });
    const value = (item: BuffettListItem) => {
      switch (sortKey) {
        case "symbol":
          return item.symbol;
        case "price":
          return item.current_price ?? 0;
        case "fairValue":
          return item.fair_value ?? 0;
        case "margin":
          return item.fair_value_margin_pct ?? -999;
        case "confidence":
          return item.fair_value_confidence ?? "";
        case "sector":
          return item.sector.label;
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
  }, [data?.items, search, sortDirection, sortKey]);

  if (isLoading) {
    return <div className="flex min-h-screen items-center justify-center bg-black text-slate-100">Adil değer yükleniyor...</div>;
  }

  if (!data) {
    return <div className="flex min-h-screen items-center justify-center bg-black text-rose-300">{error || "Adil değer verisi bulunamadı."}</div>;
  }
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
    setSortDirection(key === "symbol" || key === "confidence" || key === "sector" ? "asc" : "desc");
  };
  const label = (key: SortKey, text: string) => `${text}${sortKey === key ? (sortDirection === "asc" ? " ↑" : " ↓") : ""}`;

  return (
    <main className="min-h-screen bg-black px-6 py-8 text-slate-50">
      <div className="mx-auto max-w-[1600px] space-y-6">
        <section className="rounded-3xl border border-blue-500/20 bg-[radial-gradient(circle_at_top_left,#1d4ed844,transparent_35%),linear-gradient(135deg,#020617,#111827_55%,#020617)] p-6">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-3xl">
              <div className="inline-flex items-center gap-2 rounded border border-blue-500/40 bg-blue-500/10 px-3 py-1 text-xs font-bold uppercase tracking-[0.18em] text-blue-100">
                <Banknote className="h-4 w-4" />
                Adil Değer v3.7.1
              </div>
              <h1 className="mt-4 text-4xl font-bold tracking-tight">10 yöntemli sektör ağırlıklı fair value ekranı</h1>
              <p className="mt-3 text-sm leading-6 text-slate-300">
                Net kâr F/K, ROE, EV çarpanları, forward metrikler, P/FCF, Graham ve DCF aynı anda hesaplanır.
                Geçerli yöntemler sektör ağırlıklarıyla toplanır ve confidence sapmasıyla birlikte gösterilir.
              </p>
              <p className="mt-2 text-xs text-slate-500">Son snapshot: {formatDateTime(data.generated_at)}</p>
            </div>
            <div className="grid grid-cols-3 gap-3 text-sm lg:min-w-[520px]">
              <div className="rounded-2xl border border-slate-800 bg-slate-950/70 p-4">
                <div className="text-xs text-slate-500">Kapsam</div>
                <div className="mt-2 text-3xl font-bold text-slate-100">{rows.length}</div>
              </div>
              <div className="rounded-2xl border border-slate-800 bg-slate-950/70 p-4">
                <div className="text-xs text-slate-500">İskonto</div>
                <div className="mt-2 text-3xl font-bold text-emerald-200">{rows.filter((row) => (row.fair_value_margin_pct ?? 0) >= 20).length}</div>
              </div>
              <div className="rounded-2xl border border-slate-800 bg-slate-950/70 p-4">
                <div className="text-xs text-slate-500">Prim</div>
                <div className="mt-2 text-3xl font-bold text-rose-200">{rows.filter((row) => (row.fair_value_margin_pct ?? 0) <= -20).length}</div>
              </div>
            </div>
          </div>
        </section>

        <section className="rounded-2xl border border-slate-800 bg-slate-950/80 p-5">
          <div className="mb-4 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div>
              <h2 className="text-xl font-semibold text-slate-100">Fair Value Tablosu</h2>
              <p className="text-sm text-slate-500">Sektör ağırlıklı adil değer ve iskonto/prim oranına göre sıralanır.</p>
            </div>
            <div className="relative w-full md:max-w-sm">
              <Search className="absolute left-3 top-3.5 h-4 w-4 text-slate-500" />
              <Input value={search} onChange={(event) => {
                setSearch(event.target.value);
                setPage(1);
              }} placeholder="Hisse veya şirket ara..." className="border-slate-800 bg-black pl-9 text-slate-100" />
            </div>
          </div>
          <div className="overflow-hidden rounded-xl border border-slate-800">
            <table className="w-full text-sm">
              <thead className="bg-black text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-4 py-3 text-left"><button type="button" onClick={() => updateSort("symbol")}>{label("symbol", "Hisse")}</button></th>
                  <th className="px-4 py-3 text-right"><button type="button" onClick={() => updateSort("price")}>{label("price", "Fiyat")}</button></th>
                  <th className="px-4 py-3 text-right"><button type="button" onClick={() => updateSort("fairValue")}>{label("fairValue", "Adil Değer")}</button></th>
                  <th className="px-4 py-3 text-right"><button type="button" onClick={() => updateSort("margin")}>{label("margin", "İskonto/Prim")}</button></th>
                  <th className="px-4 py-3 text-left"><button type="button" onClick={() => updateSort("confidence")}>{label("confidence", "Güven")}</button></th>
                  <th className="px-4 py-3 text-left"><button type="button" onClick={() => updateSort("sector")}>{label("sector", "Sektör")}</button></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {pageRows.map((item) => (
                  <tr key={item.symbol} className="bg-slate-950/50 hover:bg-slate-900">
                    <td className="px-4 py-3">
                      <Link href={`/fair-value/${item.symbol}`} className="font-bold text-cyan-200 hover:text-cyan-100">{item.symbol}</Link>
                      <div className="text-xs text-slate-500">{item.name}</div>
                    </td>
                    <td className="px-4 py-3 text-right text-slate-100">{formatPrice(item.current_price)}</td>
                    <td className="px-4 py-3 text-right text-blue-100">{formatPrice(item.fair_value)}</td>
                    <td className={`px-4 py-3 text-right font-bold ${(item.fair_value_margin_pct ?? 0) >= 20 ? "text-emerald-300" : (item.fair_value_margin_pct ?? 0) <= -20 ? "text-rose-300" : "text-yellow-200"}`}>{pct(item.fair_value_margin_pct)}</td>
                    <td className="px-4 py-3 text-slate-300">{item.fair_value_confidence ?? "-"}</td>
                    <td className="px-4 py-3 text-slate-400">{item.sector.label}</td>
                  </tr>
                ))}
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
