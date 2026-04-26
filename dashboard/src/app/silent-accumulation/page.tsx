"use client";

import { Radar, RefreshCcw } from "lucide-react";
import { useMemo, useState } from "react";
import { useSilentAccumulationData } from "@/hooks/use-silent-accumulation-data";
import { formatDateTime, formatPrice } from "@/lib/formatters";
import type { SilentAccumulationItem } from "@/lib/types/silent-accumulation";

type FilterKey = "ANY" | "AT_LEAST_2" | "FLAWLESS" | "ONLY_RSI" | "ONLY_VOLUME" | "ONLY_RS" | "ONLY_CMF";
type SortKey = "symbol" | "rsi" | "volume" | "relativeStrength" | "score" | "bottomDistance" | "range";
type SortDirection = "asc" | "desc";

const PAGE_SIZE = 40;

const FILTERS: { value: FilterKey; label: string }[] = [
  { value: "ANY", label: "Any (1+)" },
  { value: "AT_LEAST_2", label: "At Least 2" },
  { value: "FLAWLESS", label: "Flawless 3/3" },
  { value: "ONLY_RSI", label: "Only RSI" },
  { value: "ONLY_VOLUME", label: "Only Volume" },
  { value: "ONLY_RS", label: "Only RS" },
  { value: "ONLY_CMF", label: "Only CMF" },
];

function passFilter(item: SilentAccumulationItem, filter: FilterKey) {
  switch (filter) {
    case "AT_LEAST_2":
      return item.score >= 2;
    case "FLAWLESS":
      return item.score >= 3;
    case "ONLY_RSI":
      return item.rsi_divergence;
    case "ONLY_VOLUME":
      return item.volume_accumulation;
    case "ONLY_RS":
      return item.relative_strength;
    case "ONLY_CMF":
      return item.cmf_positive;
    default:
      return item.score >= 1;
  }
}

function Mark({ ok }: { ok: boolean }) {
  return <span className={ok ? "text-emerald-300" : "text-rose-300"}>{ok ? "✔" : "✕"}</span>;
}

function Row({ item }: { item: SilentAccumulationItem }) {
  return (
    <tr className="border-b border-slate-800 bg-slate-950/60 hover:bg-slate-900">
      <td className="px-3 py-2">
        <div className="font-bold text-cyan-200">{item.symbol}</div>
        <div className="text-[10px] text-slate-500">{formatPrice(item.price)}</div>
      </td>
      <td className="px-2 py-2 text-center"><Mark ok={item.rsi_divergence} /></td>
      <td className="px-2 py-2 text-center"><Mark ok={item.volume_accumulation} /></td>
      <td className="px-2 py-2 text-center"><Mark ok={item.relative_strength} /></td>
      <td className="px-2 py-2 text-center font-bold text-yellow-100">{item.score}/3</td>
      <td className="px-3 py-2 text-xs text-slate-400">{item.label}</td>
    </tr>
  );
}

function ResultTable({
  title,
  items,
  sortLabel,
  updateSort,
}: {
  title: string;
  items: SilentAccumulationItem[];
  sortLabel: (key: SortKey, label: string) => string;
  updateSort: (key: SortKey) => void;
}) {
  return (
    <div className="overflow-hidden rounded-xl border border-slate-800 bg-black">
      <div className="border-b border-slate-800 bg-slate-950 px-3 py-2 text-sm font-bold text-slate-100">{title}</div>
      <table className="w-full text-sm">
        <thead className="bg-black text-[10px] uppercase tracking-wide text-slate-500">
          <tr>
            <th className="px-3 py-2 text-left"><button type="button" onClick={() => updateSort("symbol")}>{sortLabel("symbol", "Hisse")}</button></th>
            <th className="px-2 py-2 text-center"><button type="button" onClick={() => updateSort("rsi")}>{sortLabel("rsi", "RSI")}</button></th>
            <th className="px-2 py-2 text-center"><button type="button" onClick={() => updateSort("volume")}>{sortLabel("volume", "Vol")}</button></th>
            <th className="px-2 py-2 text-center"><button type="button" onClick={() => updateSort("relativeStrength")}>{sortLabel("relativeStrength", "Res")}</button></th>
            <th className="px-2 py-2 text-center"><button type="button" onClick={() => updateSort("score")}>{sortLabel("score", "Skor")}</button></th>
            <th className="px-3 py-2 text-left">Durum</th>
          </tr>
        </thead>
        <tbody>{items.map((item) => <Row key={item.symbol} item={item} />)}</tbody>
      </table>
    </div>
  );
}

export default function SilentAccumulationPage() {
  const { data, error, isLoading, reload } = useSilentAccumulationData();
  const [group, setGroup] = useState("ALL");
  const [filter, setFilter] = useState<FilterKey>("AT_LEAST_2");
  const [sortKey, setSortKey] = useState<SortKey>("score");
  const [sortDirection, setSortDirection] = useState<SortDirection>("desc");
  const [page, setPage] = useState(1);

  const filtered = useMemo(() => {
    const rows = (data?.items ?? [])
      .filter((item) => group === "ALL" || String(item.group) === group)
      .filter((item) => passFilter(item, filter));
    const value = (item: SilentAccumulationItem) => {
      switch (sortKey) {
        case "symbol":
          return item.symbol;
        case "rsi":
          return item.rsi_divergence ? 1 : 0;
        case "volume":
          return item.volume_accumulation ? 1 : 0;
        case "relativeStrength":
          return item.relative_strength ? 1 : 0;
        case "score":
          return item.score;
        case "bottomDistance":
          return item.bottom_distance_pct;
        case "range":
          return item.range_pct;
      }
    };
    return [...rows].sort((left, right) => {
      const leftValue = value(left);
      const rightValue = value(right);
      const result = typeof leftValue === "string" || typeof rightValue === "string"
        ? String(leftValue).localeCompare(String(rightValue), "tr")
        : leftValue - rightValue;
      return result * (sortDirection === "asc" ? 1 : -1);
    });
  }, [data?.items, filter, group, sortDirection, sortKey]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const currentPage = Math.min(page, totalPages);
  const pageRows = filtered.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE);
  const midpoint = Math.ceil(pageRows.length / 2);
  const left = pageRows.slice(0, midpoint);
  const right = pageRows.slice(midpoint);
  const groups = Object.keys(data?.summary.groups ?? {});
  const updateSort = (key: SortKey) => {
    setPage(1);
    if (key === sortKey) {
      setSortDirection((current) => (current === "asc" ? "desc" : "asc"));
      return;
    }
    setSortKey(key);
    setSortDirection(key === "symbol" || key === "bottomDistance" || key === "range" ? "asc" : "desc");
  };
  const sortLabel = (key: SortKey, label: string) => `${label}${sortKey === key ? (sortDirection === "asc" ? " ↑" : " ↓") : ""}`;

  if (isLoading) {
    return <div className="flex min-h-screen items-center justify-center bg-black text-slate-100">Sessiz toplama taranıyor...</div>;
  }

  if (!data) {
    return <div className="flex min-h-screen items-center justify-center bg-black text-rose-300">{error || "Sessiz toplama verisi yok."}</div>;
  }

  return (
    <main className="min-h-screen bg-black px-6 py-8 text-slate-50">
      <div className="mx-auto max-w-[1600px] space-y-6">
        <section className="rounded-3xl border border-emerald-500/20 bg-[radial-gradient(circle_at_top_left,#065f4633,transparent_36%),linear-gradient(135deg,#020617,#0f172a_58%,#020617)] p-6">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-3xl">
              <div className="inline-flex items-center gap-2 rounded border border-emerald-500/40 bg-emerald-500/10 px-3 py-1 text-xs font-bold uppercase tracking-[0.18em] text-emerald-100">
                <Radar className="h-4 w-4" />
                Smart Money Silent Accumulation Scanner · PRO
              </div>
              <h1 className="mt-4 text-4xl font-bold tracking-tight">Sessiz toplama ve kırılım öncesi BIST tarayıcı</h1>
              <p className="mt-3 text-sm leading-6 text-slate-300">
                RSI pozitif uyumsuzluk, OBV/CMF sessiz birikim ve XU100’e göre relatif güç kriterlerini uzun dönem dip filtresiyle birlikte tarar.
              </p>
              <p className="mt-2 text-xs text-slate-500">Son snapshot: {formatDateTime(data.generated_at)}</p>
            </div>
            <div className="grid grid-cols-3 gap-3 text-sm lg:min-w-[520px]">
              <div className="rounded-2xl border border-slate-800 bg-slate-950/70 p-4">
                <div className="text-xs text-slate-500">Taranan</div>
                <div className="mt-2 text-3xl font-bold text-slate-100">{data.summary.successful_symbols}</div>
              </div>
              <div className="rounded-2xl border border-slate-800 bg-slate-950/70 p-4">
                <div className="text-xs text-slate-500">2+ Sinyal</div>
                <div className="mt-2 text-3xl font-bold text-emerald-200">{data.summary.strong}</div>
              </div>
              <div className="rounded-2xl border border-slate-800 bg-slate-950/70 p-4">
                <div className="text-xs text-slate-500">Flawless</div>
                <div className="mt-2 text-3xl font-bold text-yellow-200">{data.summary.flawless}</div>
              </div>
            </div>
          </div>
        </section>

        <section className="rounded-2xl border border-slate-800 bg-slate-950/80 p-4">
          <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div className="flex flex-wrap gap-3">
              <select value={group} onChange={(event) => {
                setGroup(event.target.value);
                setPage(1);
              }} className="h-10 rounded border border-slate-800 bg-black px-3 text-sm text-slate-100">
                <option value="ALL">Tüm Gruplar</option>
                {groups.map((groupNo) => <option key={groupNo} value={groupNo}>Grup {groupNo}</option>)}
              </select>
              <select value={filter} onChange={(event) => {
                setFilter(event.target.value as FilterKey);
                setPage(1);
              }} className="h-10 rounded border border-slate-800 bg-black px-3 text-sm text-slate-100">
                {FILTERS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
              </select>
            </div>
            <button type="button" onClick={() => void reload()} className="inline-flex items-center gap-2 rounded border border-slate-800 bg-black px-3 py-2 text-sm text-slate-200 hover:bg-slate-900">
              <RefreshCcw className="h-4 w-4" />
              Yenile
            </button>
          </div>
        </section>

        <section className="grid gap-4 xl:grid-cols-2">
          <ResultTable title="Sol Panel" items={left} sortLabel={sortLabel} updateSort={updateSort} />
          <ResultTable title="Sağ Panel" items={right} sortLabel={sortLabel} updateSort={updateSort} />
        </section>

        <div className="flex items-center justify-between text-sm text-slate-400">
          <span>{filtered.length} kayıt · Sayfa {currentPage}/{totalPages}</span>
          <div className="flex gap-2">
            <button type="button" disabled={currentPage <= 1} onClick={() => setPage((value) => Math.max(1, value - 1))} className="rounded border border-slate-800 px-3 py-1 disabled:opacity-40">Önceki</button>
            <button type="button" disabled={currentPage >= totalPages} onClick={() => setPage((value) => Math.min(totalPages, value + 1))} className="rounded border border-slate-800 px-3 py-1 disabled:opacity-40">Sonraki</button>
          </div>
        </div>

        <p className="text-xs text-slate-500">
          Bu ekran otomatik AL/SAT botu değildir. Kırılım öncesi adayları hızlı filtrelemek için tasarlanmış yardımcı tarayıcıdır.
        </p>
      </div>
    </main>
  );
}
