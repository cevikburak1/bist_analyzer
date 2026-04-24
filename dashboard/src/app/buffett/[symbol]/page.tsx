"use client";

import { use } from "react";
import { BuffettDetailView } from "@/components/buffett/buffett-detail-view";
import { useBuffettData } from "@/hooks/use-buffett-data";
import type { BuffettStockDetail } from "@/lib/types/buffett";

type PageProps = {
  params: Promise<{ symbol: string }>;
};

export default function BuffettStockPage({ params }: PageProps) {
  const { symbol } = use(params);
  const { data, error, isLoading } = useBuffettData<BuffettStockDetail>({ symbol });

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-950 text-slate-100">
        Detay yükleniyor...
      </div>
    );
  }

  if (!data) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-950 text-rose-300">
        {error || "Buffett detayı bulunamadı."}
      </div>
    );
  }

  return <BuffettDetailView detail={data} />;
}
