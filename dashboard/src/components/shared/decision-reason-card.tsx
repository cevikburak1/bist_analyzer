/**
 * Karar Gerekçesi Kartı.
 * Buffett (label_key) veya Teknik (AL/SAT/BEKLE) sistemlerinin neden bu
 * kararı verdiğini açıkça gösterir: tek cümlelik özet + tetikleyen
 * kural/faktör listesi.
 */

import { CheckCircle2, AlertTriangle, MinusCircle } from "lucide-react";

type FactorStatus = "OK" | "FAIL" | "NA" | string;

export type DecisionFactor = {
  rule: string;
  status: FactorStatus;
  detail: string;
};

type Props = {
  title: string;
  decisionLabel: string;
  decisionColor?: string;
  reason: string;
  factors?: DecisionFactor[];
  bulletReasons?: string[];
};

const STATUS_VISUAL: Record<
  string,
  { icon: typeof CheckCircle2; classes: string; label: string }
> = {
  OK: {
    icon: CheckCircle2,
    classes: "text-emerald-300",
    label: "Karşılandı",
  },
  FAIL: {
    icon: AlertTriangle,
    classes: "text-rose-300",
    label: "Karşılanmadı",
  },
  NA: {
    icon: MinusCircle,
    classes: "text-slate-400",
    label: "Veri Yok",
  },
};

export function DecisionReasonCard({
  title,
  decisionLabel,
  decisionColor,
  reason,
  factors,
  bulletReasons,
}: Props) {
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-slate-100">{title}</h2>
          <p className="mt-1 text-xs text-slate-500">
            Bu karar neden verildi? Hangi kurallar tetiklendi?
          </p>
        </div>
        {decisionLabel ? (
          <span
            className={`inline-flex items-center rounded-full border px-3 py-1 text-xs font-semibold ${
              decisionColor ?? "border-slate-700 bg-slate-800 text-slate-200"
            }`}
          >
            {decisionLabel}
          </span>
        ) : null}
      </div>

      <p className="mt-3 rounded-lg border border-slate-800 bg-slate-950/70 px-3 py-2 text-sm text-slate-200">
        {reason || "Açıklama mevcut değil."}
      </p>

      {factors && factors.length > 0 ? (
        <div className="mt-4 space-y-2">
          <div className="text-xs uppercase tracking-wide text-slate-500">
            Tetiklenen Kurallar
          </div>
          <ul className="space-y-2">
            {factors.map((f) => {
              const visual = STATUS_VISUAL[f.status] ?? STATUS_VISUAL.NA;
              const Icon = visual.icon;
              return (
                <li
                  key={`${f.rule}-${f.detail}`}
                  className="flex items-start gap-2 rounded-lg bg-slate-950/40 px-3 py-2"
                >
                  <Icon className={`mt-0.5 h-4 w-4 shrink-0 ${visual.classes}`} />
                  <div className="flex-1 text-sm text-slate-200">
                    <div className="flex items-center gap-2 text-xs uppercase tracking-wide">
                      <span className="text-slate-300">{f.rule}</span>
                      <span className={visual.classes}>{visual.label}</span>
                    </div>
                    <div className="mt-1 text-slate-300">{f.detail}</div>
                  </div>
                </li>
              );
            })}
          </ul>
        </div>
      ) : null}

      {bulletReasons && bulletReasons.length > 0 ? (
        <div className="mt-4 space-y-2">
          <div className="text-xs uppercase tracking-wide text-slate-500">
            Tetikleyen Faktörler
          </div>
          <ul className="space-y-1 text-sm text-slate-300">
            {bulletReasons.map((b) => (
              <li
                key={b}
                className="rounded-lg bg-slate-950/40 px-3 py-2"
              >
                {b}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
