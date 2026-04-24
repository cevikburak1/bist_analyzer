"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { ArrowDownAZ, ArrowUpAZ, ChevronLeft, ChevronRight, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { describeRatioPercent, formatPrice } from "@/lib/formatters";
import { LabelPill } from "@/components/buffett/label-pill";
import type { BuffettListItem } from "@/lib/types/buffett";

type SortKey = "symbol" | "score" | "mos" | "pe" | "roe";

type Props = {
  items: BuffettListItem[];
};

const PAGE_SIZE = 25;

const LABEL_OPTIONS: { value: string; label: string }[] = [
  { value: "ALL", label: "Tüm etiketler" },
  { value: "HARIKA_IS_UCUZ", label: "Harika - Ucuz" },
  { value: "HARIKA_IS_PAHALI", label: "Harika - Pahalı" },
  { value: "IYI_IS_UCUZ", label: "İyi - Ucuz" },
  { value: "GECER", label: "Geçer" },
  { value: "PAS_GEC", label: "Pas Geç" },
  { value: "YETERSIZ_VERI", label: "Yetersiz Veri" },
];

const SECTOR_OPTIONS: { value: string; label: string }[] = [
  { value: "ALL", label: "Tüm sektörler" },
  { value: "BANKA", label: "Banka" },
  { value: "GYO", label: "GYO" },
  { value: "SIGORTA", label: "Sigorta" },
  { value: "HOLDING", label: "Holding" },
  { value: "SANAYI", label: "Sanayi" },
  { value: "DIGER", label: "Diğer" },
];

function formatPct(value: number | null | undefined) {
  return describeRatioPercent(value).label;
}

function formatScore(value: number) {
  return value.toFixed(1);
}

export function BuffettTable({ items }: Props) {
  const [search, setSearch] = useState("");
  const [labelFilter, setLabelFilter] = useState("ALL");
  const [sectorFilter, setSectorFilter] = useState("ALL");
  const [minMos, setMinMos] = useState<string>("");
  const [minScore, setMinScore] = useState<string>("");
  const [sortKey, setSortKey] = useState<SortKey>("score");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [page, setPage] = useState(1);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    const minMosNum = minMos === "" ? null : Number(minMos) / 100;
    const minScoreNum = minScore === "" ? null : Number(minScore);

    return items.filter((it) => {
      if (q && !it.symbol.toLowerCase().includes(q) && !it.name.toLowerCase().includes(q)) {
        return false;
      }
      if (labelFilter !== "ALL" && it.label_key !== labelFilter) return false;
      if (sectorFilter !== "ALL" && it.sector.kind !== sectorFilter) return false;
      if (minMosNum !== null && (it.margin_of_safety ?? -Infinity) < minMosNum) return false;
      if (minScoreNum !== null && it.score < minScoreNum) return false;
      return true;
    });
  }, [items, search, labelFilter, sectorFilter, minMos, minScore]);

  const sorted = useMemo(() => {
    const arr = [...filtered];
    const mult = sortDir === "asc" ? 1 : -1;
    arr.sort((a, b) => {
      const v = (it: BuffettListItem) => {
        switch (sortKey) {
          case "symbol": return it.symbol;
          case "score": return it.score;
          case "mos": return it.margin_of_safety ?? -Infinity;
          case "pe": return it.key_metrics.pe ?? Infinity;
          case "roe": return it.key_metrics.roe_avg_5y ?? -Infinity;
        }
      };
      const lv = v(a), rv = v(b);
      if (typeof lv === "string" && typeof rv === "string") {
        return lv.localeCompare(rv) * mult;
      }
      return ((lv as number) - (rv as number)) * mult;
    });
    return arr;
  }, [filtered, sortKey, sortDir]);

  const totalPages = Math.max(1, Math.ceil(sorted.length / PAGE_SIZE));
  const currentPage = Math.min(page, totalPages);
  const pageData = sorted.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE);

  const updateSort = (next: SortKey) => {
    setPage(1);
    if (next === sortKey) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
      return;
    }
    setSortKey(next);
    setSortDir(next === "symbol" ? "asc" : "desc");
  };

  const sortIcon = sortDir === "asc" ? (
    <ArrowUpAZ className="h-3.5 w-3.5" />
  ) : (
    <ArrowDownAZ className="h-3.5 w-3.5" />
  );

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-5">
        <div className="relative xl:col-span-2">
          <Search className="absolute left-3 top-3.5 h-4 w-4 text-slate-500" />
          <Input
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1); }}
            placeholder="Sembol veya şirket adı ara..."
            className="border-slate-800 bg-slate-950 pl-9 text-slate-100"
          />
        </div>
        <select
          value={labelFilter}
          onChange={(e) => { setLabelFilter(e.target.value); setPage(1); }}
          className="h-10 rounded-md border border-slate-800 bg-slate-950 px-3 text-sm text-slate-100"
        >
          {LABEL_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
        <select
          value={sectorFilter}
          onChange={(e) => { setSectorFilter(e.target.value); setPage(1); }}
          className="h-10 rounded-md border border-slate-800 bg-slate-950 px-3 text-sm text-slate-100"
        >
          {SECTOR_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
        <div className="flex items-center gap-2">
          <Input
            type="number"
            value={minMos}
            onChange={(e) => { setMinMos(e.target.value); setPage(1); }}
            placeholder="Min MoS %"
            className="border-slate-800 bg-slate-950 text-slate-100"
          />
          <Input
            type="number"
            value={minScore}
            onChange={(e) => { setMinScore(e.target.value); setPage(1); }}
            placeholder="Min Skor"
            className="border-slate-800 bg-slate-950 text-slate-100"
          />
        </div>
      </div>

      <div className="text-sm text-slate-400">{filtered.length} hisse listeleniyor</div>

      <div className="overflow-hidden rounded-xl border border-slate-800">
        <div className="max-h-[720px] overflow-auto">
          <Table>
            <TableHeader className="sticky top-0 z-10 bg-slate-950">
              <TableRow className="border-slate-800 hover:bg-slate-950">
                <TableHead>
                  <button type="button" className="flex items-center gap-1 text-slate-300" onClick={() => updateSort("symbol")}>
                    Hisse {sortKey === "symbol" ? sortIcon : null}
                  </button>
                </TableHead>
                <TableHead className="text-slate-300">Sektör</TableHead>
                <TableHead className="text-slate-300">Etiket</TableHead>
                <TableHead className="text-right">
                  <button type="button" className="ml-auto flex items-center gap-1 text-slate-300" onClick={() => updateSort("score")}>
                    Skor {sortKey === "score" ? sortIcon : null}
                  </button>
                </TableHead>
                <TableHead className="text-right">
                  <button type="button" className="ml-auto flex items-center gap-1 text-slate-300" onClick={() => updateSort("mos")}>
                    MoS {sortKey === "mos" ? sortIcon : null}
                  </button>
                </TableHead>
                <TableHead className="text-right">
                  <button type="button" className="ml-auto flex items-center gap-1 text-slate-300" onClick={() => updateSort("pe")}>
                    F/K {sortKey === "pe" ? sortIcon : null}
                  </button>
                </TableHead>
                <TableHead className="text-right text-slate-300">PD/DD</TableHead>
                <TableHead className="text-right">
                  <button type="button" className="ml-auto flex items-center gap-1 text-slate-300" onClick={() => updateSort("roe")}>
                    ROE 5y {sortKey === "roe" ? sortIcon : null}
                  </button>
                </TableHead>
                <TableHead className="text-right text-slate-300">Borç/Öz</TableHead>
                <TableHead className="text-right text-slate-300">Fiyat</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {pageData.map((it) => (
                <TableRow key={it.symbol} className="border-slate-800 hover:bg-slate-900/60">
                  <TableCell>
                    <div className="flex flex-col">
                      <Link href={`/buffett/${it.symbol}`} className="font-semibold text-cyan-300 hover:text-cyan-200">
                        {it.symbol}
                      </Link>
                      <span className="max-w-[260px] truncate text-xs text-slate-500" title={it.name}>{it.name}</span>
                    </div>
                  </TableCell>
                  <TableCell className="text-xs text-slate-300">{it.sector.label}</TableCell>
                  <TableCell>
                    <LabelPill color={it.color} label={it.label} />
                  </TableCell>
                  <TableCell className="text-right font-semibold text-slate-100">{formatScore(it.score)}</TableCell>
                  <TableCell className={`text-right font-medium ${
                    describeRatioPercent(it.margin_of_safety).isAnomaly
                      ? "text-amber-300"
                      : it.margin_of_safety && it.margin_of_safety >= 0.30
                        ? "text-emerald-300"
                        : "text-slate-300"
                  }`}>
                    {formatPct(it.margin_of_safety)}
                  </TableCell>
                  <TableCell className="text-right text-slate-300">
                    {it.key_metrics.pe != null ? it.key_metrics.pe.toFixed(2) : "-"}
                  </TableCell>
                  <TableCell className="text-right text-slate-300">
                    {it.key_metrics.pb != null ? it.key_metrics.pb.toFixed(2) : "-"}
                  </TableCell>
                  <TableCell className="text-right text-slate-300">
                    {formatPct(it.key_metrics.roe_avg_5y)}
                  </TableCell>
                  <TableCell className="text-right text-slate-300">
                    {typeof it.key_metrics.debt_to_equity === "number"
                      ? it.key_metrics.debt_to_equity.toFixed(2)
                      : it.key_metrics.debt_to_equity ?? "-"}
                  </TableCell>
                  <TableCell className="text-right text-slate-200">{formatPrice(it.current_price)}</TableCell>
                </TableRow>
              ))}
              {pageData.length === 0 && (
                <TableRow>
                  <TableCell colSpan={10} className="py-8 text-center text-sm text-slate-500">
                    Filtrelere uyan hisse yok.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>
      </div>

      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div className="text-sm text-slate-400">Sayfa {currentPage} / {totalPages}</div>
        <div className="flex items-center gap-2">
          <Button
            type="button"
            variant="outline"
            className="border-slate-700 bg-slate-950 text-slate-100 hover:bg-slate-800"
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={currentPage === 1}
          >
            <ChevronLeft className="h-4 w-4" />
            Önceki
          </Button>
          <Button
            type="button"
            variant="outline"
            className="border-slate-700 bg-slate-950 text-slate-100 hover:bg-slate-800"
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={currentPage === totalPages}
          >
            Sonraki
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  );
}
