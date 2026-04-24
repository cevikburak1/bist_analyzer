"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LineChart, Landmark } from "lucide-react";

const ITEMS = [
  { href: "/", label: "Teknik Analiz", icon: LineChart, match: (p: string) => p === "/" || p.startsWith("/hisse") },
  { href: "/buffett", label: "Buffett (Temel)", icon: Landmark, match: (p: string) => p.startsWith("/buffett") },
];

export function TopNav() {
  const pathname = usePathname() || "/";

  return (
    <nav className="border-b border-slate-800 bg-slate-950/80 backdrop-blur">
      <div className="mx-auto flex max-w-[1600px] items-center gap-1 px-6 py-2">
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
    </nav>
  );
}
