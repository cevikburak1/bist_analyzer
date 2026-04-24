/**
 * Buffett etiket görsel temsilcisi.
 * Renk eşlemesi backend'deki LABELS sözlüğüyle uyumlu (emerald/amber/lime/slate/rose/sky).
 */

const COLOR_MAP: Record<string, string> = {
  emerald: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  amber: "bg-amber-500/15 text-amber-300 border-amber-500/30",
  lime: "bg-lime-500/15 text-lime-300 border-lime-500/30",
  slate: "bg-slate-500/15 text-slate-300 border-slate-500/30",
  rose: "bg-rose-500/15 text-rose-300 border-rose-500/30",
  sky: "bg-sky-500/15 text-sky-300 border-sky-500/30",
};

type LabelPillProps = {
  color: string;
  label: string;
  size?: "sm" | "md";
};

export function LabelPill({ color, label, size = "sm" }: LabelPillProps) {
  const classes = COLOR_MAP[color] ?? COLOR_MAP.slate;
  const sizing =
    size === "md" ? "px-3 py-1 text-sm" : "px-2 py-0.5 text-xs";
  return (
    <span
      className={`inline-flex items-center rounded-full border font-medium ${classes} ${sizing}`}
    >
      {label}
    </span>
  );
}
