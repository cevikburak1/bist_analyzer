"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { ArrowDownAZ, ArrowUpAZ, ChevronLeft, ChevronRight, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { formatPrice } from "@/lib/formatters";
import type { ReportSignal } from "@/lib/types/report";
import { SignalBadge } from "@/components/stocks/signal-badge";

type SortKey = "symbol" | "score" | "price" | "wr" | "adx" | "vkat" | "stopLoss" | "target";

type StockTableProps = {
  signals: ReportSignal[];
  fairValueBySymbol?: Record<string, {
    fairValue: number | null;
    marginPct: number | null;
    confidence: string | null;
  }>;
};

const PAGE_SIZE = 25;

function getAction(signal: ReportSignal): string {
  return signal.action || signal.signal_daily;
}

function getTarget(signal: ReportSignal): number {
  return signal.targets.short_target || signal.target;
}

function getStop(signal: ReportSignal): number {
  return signal.targets.stop_loss || signal.stop_loss;
}

export function StockTable({ signals }: StockTableProps) {
  const [search, setSearch] = useState("");
  const [signalFilter, setSignalFilter] = useState("ALL");
  const [sortKey, setSortKey] = useState<SortKey>("score");
  const [sortDirection, setSortDirection] = useState<"asc" | "desc">("desc");
  const [page, setPage] = useState(1);

  const filtered = useMemo(() => {
    const normalizedSearch = search.trim().toLowerCase();
    return signals.filter((signal) => {
      const action = getAction(signal);
      const matchesSearch =
        !normalizedSearch ||
        signal.symbol.toLowerCase().includes(normalizedSearch) ||
        signal.commentary.summary.toLowerCase().includes(normalizedSearch) ||
        signal.reason.toLowerCase().includes(normalizedSearch);

      const matchesSignal =
        signalFilter === "ALL" ||
        action === signalFilter ||
        signal.signal_daily === signalFilter;
      return matchesSearch && matchesSignal;
    });
  }, [search, signalFilter, signals]);

  const sorted = useMemo(() => {
    const next = [...filtered];
    next.sort((left, right) => {
      const multiplier = sortDirection === "asc" ? 1 : -1;

      const value = (signal: ReportSignal) => {
        switch (sortKey) {
          case "symbol":
            return signal.symbol;
          case "score":
            return signal.score;
          case "price":
            return signal.price;
          case "wr":
            return signal.score_breakdown.wr_pct ?? 0;
          case "adx":
            return signal.score_breakdown.adx ?? 0;
          case "vkat":
            return signal.score_breakdown.v_kat ?? 0;
          case "stopLoss":
            return getStop(signal);
          case "target":
            return getTarget(signal);
        }
      };

      const leftValue = value(left);
      const rightValue = value(right);

      if (typeof leftValue === "string" && typeof rightValue === "string") {
        return leftValue.localeCompare(rightValue) * multiplier;
      }

      return (((leftValue as number) ?? 0) - ((rightValue as number) ?? 0)) * multiplier;
    });
    return next;
  }, [filtered, sortDirection, sortKey]);

  const totalPages = Math.max(1, Math.ceil(sorted.length / PAGE_SIZE));
  const currentPage = Math.min(page, totalPages);
  const pageData = sorted.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE);

  const updateSort = (nextKey: SortKey) => {
    setPage(1);
    if (sortKey === nextKey) {
      setSortDirection((current) => (current === "asc" ? "desc" : "asc"));
      return;
    }

    setSortKey(nextKey);
    setSortDirection(nextKey === "symbol" ? "asc" : "desc");
  };

  const sortIcon =
    sortDirection === "asc" ? (
      <ArrowUpAZ className="h-3.5 w-3.5" />
    ) : (
      <ArrowDownAZ className="h-3.5 w-3.5" />
    );

  return (
    <div className="space-y-4">
      <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-4">
        <div className="text-xs uppercase tracking-wide text-slate-400">
          Morpheus Puanlama
        </div>
        <div className="text-sm text-slate-200">
          Perfect Order, tarihsel kurulum proxy'si, ADX, hacim katı ve sıkışma/kırılım potansiyeline göre sıralanır
        </div>
      </div>

      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div className="relative w-full md:max-w-sm">
          <Search className="absolute left-3 top-3.5 h-4 w-4 text-slate-500" />
          <Input
            value={search}
            onChange={(event) => {
              setSearch(event.target.value);
              setPage(1);
            }}
            placeholder="Hisse, özet veya sebep ara..."
            className="border-slate-800 bg-slate-950 pl-9 text-slate-100"
          />
        </div>

        <div className="flex items-center gap-3">
          <select
            value={signalFilter}
            onChange={(event) => {
              setSignalFilter(event.target.value);
              setPage(1);
            }}
            className="h-10 rounded-md border border-slate-800 bg-slate-950 px-3 text-sm text-slate-100"
          >
            <option value="ALL">Tum sinyaller</option>
            <option value="GÜÇLÜ AL">GÜÇLÜ AL</option>
            <option value="AL">AL</option>
            <option value="KAR AL">KAR AL</option>
            <option value="SAT">SAT</option>
            <option value="BEKLE">BEKLE</option>
          </select>
          <div className="text-sm text-slate-400">{filtered.length} hisse</div>
        </div>
      </div>

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
                <TableHead className="text-right">
                  <button type="button" className="ml-auto flex items-center gap-1 text-slate-300" onClick={() => updateSort("price")}>
                    Fiyat {sortKey === "price" ? sortIcon : null}
                  </button>
                </TableHead>
                <TableHead className="text-center">
                  <button type="button" className="mx-auto flex items-center gap-1 text-slate-300" onClick={() => updateSort("score")}>
                    Skor {sortKey === "score" ? sortIcon : null}
                  </button>
                </TableHead>
                <TableHead className="text-center text-slate-300">Aksiyon</TableHead>
                <TableHead className="text-slate-300">Neden</TableHead>
                <TableHead className="text-right">
                  <button type="button" className="ml-auto flex items-center gap-1 text-slate-300" onClick={() => updateSort("wr")}>
                    Kurulum % {sortKey === "wr" ? sortIcon : null}
                  </button>
                </TableHead>
                <TableHead className="text-right">
                  <button type="button" className="ml-auto flex items-center gap-1 text-slate-300" onClick={() => updateSort("adx")}>
                    ADX {sortKey === "adx" ? sortIcon : null}
                  </button>
                </TableHead>
                <TableHead className="text-right">
                  <button type="button" className="ml-auto flex items-center gap-1 text-slate-300" onClick={() => updateSort("vkat")}>
                    V/K {sortKey === "vkat" ? sortIcon : null}
                  </button>
                </TableHead>
                <TableHead className="text-center text-slate-300">DZL</TableHead>
                <TableHead className="text-center text-slate-300">SQZ</TableHead>
                <TableHead className="text-right">
                  <button type="button" className="ml-auto flex items-center gap-1 text-slate-300" onClick={() => updateSort("stopLoss")}>
                    Stop {sortKey === "stopLoss" ? sortIcon : null}
                  </button>
                </TableHead>
                <TableHead className="text-right">
                  <button type="button" className="ml-auto flex items-center gap-1 text-slate-300" onClick={() => updateSort("target")}>
                    Hedef {sortKey === "target" ? sortIcon : null}
                  </button>
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {pageData.map((signal) => {
                const action = getAction(signal);
                const metrics = signal.score_breakdown;
                const stop = getStop(signal);
                const target = getTarget(signal);
                return (
                  <TableRow key={signal.symbol} className="border-slate-800 hover:bg-slate-900/60">
                    <TableCell>
                      <Link href={`/hisse/${signal.symbol}`} className="font-semibold text-cyan-300 hover:text-cyan-200">
                        {signal.symbol}
                      </Link>
                    </TableCell>
                    <TableCell className="text-right text-slate-200">{formatPrice(signal.price)}</TableCell>
                    <TableCell className="text-center">
                      <span
                        className={
                          signal.score >= 170
                            ? "font-semibold text-emerald-300"
                            : signal.score <= 90
                              ? "font-semibold text-rose-300"
                              : "font-semibold text-amber-200"
                        }
                      >
                        {signal.score.toFixed(1)}
                      </span>
                    </TableCell>
                    <TableCell className="text-center">
                      <SignalBadge signal={action} />
                    </TableCell>
                    <TableCell className="max-w-[280px] text-xs text-slate-300">
                      <div className="truncate" title={signal.reason}>
                        {signal.reason}
                      </div>
                    </TableCell>
                    <TableCell
                      className="text-right text-slate-300"
                      title={`Maliyet tamponlu tarihsel proxy; n=${metrics.wr_samples ?? 0}, backtest değil`}
                    >
                      {(metrics.wr_pct ?? 0).toFixed(0)}
                    </TableCell>
                    <TableCell className="text-right text-slate-300">{(metrics.adx ?? 0).toFixed(1)}</TableCell>
                    <TableCell className="text-right text-slate-300">{(metrics.v_kat ?? 0).toFixed(1)}</TableCell>
                    <TableCell className="text-center text-xs font-semibold text-slate-300">
                      {metrics.dzl_ok ? "OK" : "--"}
                    </TableCell>
                    <TableCell className="text-center text-xs font-semibold text-slate-300">
                      {metrics.sqz_ok ? "OK" : "--"}
                    </TableCell>
                    <TableCell className="text-right text-rose-300">{stop > 0 ? formatPrice(stop) : "-"}</TableCell>
                    <TableCell className="text-right text-emerald-300">{target > 0 ? formatPrice(target) : "-"}</TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>
      </div>

      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div className="text-sm text-slate-400">
          Sayfa {currentPage} / {totalPages}
        </div>
        <div className="flex items-center gap-2">
          <Button
            type="button"
            variant="outline"
            className="border-slate-700 bg-slate-950 text-slate-100 hover:bg-slate-800"
            onClick={() => setPage((current) => Math.max(1, current - 1))}
            disabled={currentPage === 1}
          >
            <ChevronLeft className="h-4 w-4" />
            Onceki
          </Button>
          <Button
            type="button"
            variant="outline"
            className="border-slate-700 bg-slate-950 text-slate-100 hover:bg-slate-800"
            onClick={() => setPage((current) => Math.min(totalPages, current + 1))}
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
