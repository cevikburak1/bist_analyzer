"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Banknote, BrainCircuit, Flame, Landmark, LineChart, Radar, Trophy } from "lucide-react";
import { HORIZON_OPTIONS, useHorizon } from "@/lib/horizon-context";

const ITEMS = [
  { href: "/", label: "Teknik Analiz", icon: LineChart, match: (p: string) => p === "/" || p.startsWith("/hisse") },
  { href: "/anka-v2", label: "ANKA v2", icon: Flame, match: (p: string) => p.startsWith("/anka-v2") },
  { href: "/anka-engine", label: "ANKA Motor", icon: BrainCircuit, match: (p: string) => p.startsWith("/anka-engine") },
  { href: "/cup-handle-quality", label: "Cup Handle", icon: Trophy, match: (p: string) => p.startsWith("/cup-handle-quality") },
  { href: "/fair-value", label: "Adil Değer", icon: Banknote, match: (p: string) => p.startsWith("/fair-value") },
  { href: "/silent-accumulation", label: "Sessiz Toplama", icon: Radar, match: (p: string) => p.startsWith("/silent-accumulation") },
  { href: "/buffett", label: "Buffett (Temel)", icon: Landmark, match: (p: string) => p.startsWith("/buffett") },
];

export function TopNav() {
  const pathname = usePathname() || "/";
  const { horizon, setHorizon } = useHorizon();

  // Buffett sayfasinda vade secici alakasiz; sadece teknik tarafta goster.
  const showHorizonSelector =
    !pathname.startsWith("/buffett") &&
    !pathname.startsWith("/anka-v2") &&
    !pathname.startsWith("/anka-engine") &&
    !pathname.startsWith("/cup-handle-quality") &&
    !pathname.startsWith("/fair-value") &&
    !pathname.startsWith("/silent-accumulation");

  return (
    <nav className="border-b border-slate-800 bg-slate-950/80 backdrop-blur">
      <div className="mx-auto flex max-w-[1600px] flex-wrap items-center gap-3 px-6 py-2">
        <div className="flex items-center gap-1">
          {ITEMS.map((it) => {
            const active = it.match(pathname);
            const Icon = it.icon;
            return (
              <Link
                key={it.href}
                href={it.href}
                className={`inline-flex items-center gap-2 rounded-md px-3 py-1.5 text-sm transition ${
                  active
                    ? "bg-slate-800 text-cyan-300"
                    : "text-slate-400 hover:bg-slate-900 hover:text-slate-200"
                }`}
              >
                <Icon className="h-4 w-4" />
                {it.label}
              </Link>
            );
          })}
        </div>

        {showHorizonSelector ? (
          <div className="ml-auto flex items-center gap-2">
            <span className="text-xs uppercase tracking-wide text-slate-500">
              Vade
            </span>
            <div className="inline-flex overflow-hidden rounded-md border border-slate-800">
              {HORIZON_OPTIONS.map((opt) => {
                const active = opt.value === horizon;
                return (
                  <button
                    key={opt.value}
                    type="button"
                    onClick={() => setHorizon(opt.value)}
                    className={`px-3 py-1.5 text-xs transition ${
                      active
                        ? "bg-cyan-500/15 text-cyan-200"
                        : "text-slate-400 hover:bg-slate-900 hover:text-slate-200"
                    }`}
                    title={opt.subtitle}
                  >
                    <div className="font-medium">{opt.label}</div>
                    <div className="text-[10px] text-slate-500">{opt.subtitle}</div>
                  </button>
                );
              })}
            </div>
          </div>
        ) : null}
      </div>
    </nav>
  );
}
