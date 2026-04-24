import { Badge } from "@/components/ui/badge";

const SIGNAL_STYLES: Record<string, string> = {
  AL: "bg-emerald-500/20 text-emerald-300 border-emerald-400/30",
  SAT: "bg-rose-500/20 text-rose-300 border-rose-400/30",
  BEKLE: "bg-amber-500/20 text-amber-200 border-amber-400/30",
};

type SignalBadgeProps = {
  signal: string;
};

export function SignalBadge({ signal }: SignalBadgeProps) {
  return (
    <Badge className={SIGNAL_STYLES[signal] ?? "bg-slate-700 text-slate-200 border-slate-600"}>
      {signal}
    </Badge>
  );
}
