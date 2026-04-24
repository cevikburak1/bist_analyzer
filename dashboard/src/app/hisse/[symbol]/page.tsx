"use client";

import { use } from "react";
import { AnalysisStatusBanner } from "@/components/dashboard/analysis-status-banner";
import { StockDetailView } from "@/components/stocks/stock-detail-view";
import { useAnalysisData } from "@/hooks/use-analysis-data";
import type { StockDetailData } from "@/lib/types/report";

type PageProps = {
  params: Promise<{
    symbol: string;
  }>;
};

export default function StockDetailPage({ params }: PageProps) {
  const { symbol } = use(params);
  const { data, status, error, isLoading, reload } = useAnalysisData<StockDetailData>({ symbol });

  if (isLoading) {
    return <div className="flex min-h-screen items-center justify-center bg-slate-950 text-slate-100">Detay yukleniyor...</div>;
  }

  if (!data) {
    return <div className="flex min-h-screen items-center justify-center bg-slate-950 text-rose-300">{error || "Hisse detayi bulunamadi."}</div>;
  }

  const refreshNow = async () => {
    await fetch("/api/analysis/refresh", { method: "POST" });
    await reload();
  };

  return (
    <div className="space-y-4">
      <div className="px-6 pt-6">
        <AnalysisStatusBanner status={status} generatedAt={data.generated_at} onRefresh={refreshNow} />
      </div>
      <StockDetailView detail={data} />
    </div>
  );
}
