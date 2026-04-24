import { LoaderCircle, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { formatDateTime } from "@/lib/formatters";
import type { AnalysisStatus } from "@/lib/types/report";

type AnalysisStatusBannerProps = {
  status: AnalysisStatus | null;
  generatedAt?: string;
  onRefresh?: () => void;
};

export function AnalysisStatusBanner({
  status,
  generatedAt,
  onRefresh,
}: AnalysisStatusBannerProps) {
  const isRunning = status?.state === "running";

  return (
    <div className="flex flex-col gap-3 rounded-xl border border-slate-800 bg-slate-900/70 p-4 md:flex-row md:items-center md:justify-between">
      <div className="space-y-1">
        <div className="flex items-center gap-2 text-sm font-medium text-slate-100">
          {isRunning ? (
            <LoaderCircle className="h-4 w-4 animate-spin text-cyan-300" />
          ) : (
            <RefreshCw className="h-4 w-4 text-cyan-300" />
          )}
          {isRunning ? "15 dakikalık tam analiz yenileniyor" : "Dashboard son başarılı snapshot üzerinden çalışıyor"}
        </div>
        <div className="text-xs text-slate-400">
          Son başarılı analiz: {formatDateTime(status?.last_success_at ?? generatedAt)}
          {" | "}
          Yenileme aralığı: {status?.refresh_interval_minutes ?? 15} dk
        </div>
        {status?.error ? <div className="text-xs text-rose-300">Son hata: {status.error}</div> : null}
      </div>
      <Button
        type="button"
        variant="outline"
        className="border-slate-700 bg-slate-950 text-slate-100 hover:bg-slate-800"
        disabled={isRunning}
        onClick={onRefresh}
      >
        {isRunning ? "Analiz Çalışıyor" : "Şimdi Yenile"}
      </Button>
    </div>
  );
}
