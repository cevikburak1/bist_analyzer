"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { isMarketOpen, isSnapshotStale } from "@/lib/market-hours";
import type { AnalysisStatus, ReportData, StockDetailData } from "@/lib/types/report";

type AnalysisPayload = ReportData | StockDetailData;

type UseAnalysisDataOptions = {
  symbol?: string;
};

async function fetchJson<T>(url: string) {
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Request failed: ${url}`);
  }

  return response.json() as Promise<T>;
}

export function useAnalysisData<T extends AnalysisPayload>({ symbol }: UseAnalysisDataOptions = {}) {
  const [data, setData] = useState<T | null>(null);
  const [status, setStatus] = useState<AnalysisStatus | null>(null);
  const [error, setError] = useState<string>("");
  const [isLoading, setIsLoading] = useState(true);
  const lastTriggerAtRef = useRef(0);

  const dataUrl = useMemo(() => {
    return symbol ? `/api/data/${symbol}` : "/api/data";
  }, [symbol]);

  const load = useCallback(async () => {
    try {
      const [nextData, nextStatus] = await Promise.all([
        fetchJson<T>(dataUrl),
        fetchJson<AnalysisStatus>("/api/analysis/status"),
      ]);
      setData(nextData);
      setStatus(nextStatus);
      setError("");
    } catch (nextError) {
      console.error(nextError);
      setError("Analiz verisi alınamadı.");
    } finally {
      setIsLoading(false);
    }
  }, [dataUrl]);

  const triggerRefresh = useCallback(async () => {
    try {
      await fetch("/api/analysis/refresh", {
        method: "POST",
      });
      lastTriggerAtRef.current = Date.now();
    } catch (refreshError) {
      console.error(refreshError);
    }
  }, []);

  useEffect(() => {
    const run = () => {
      void load();
    };

    const frame = window.requestAnimationFrame(run);
    const dataInterval = window.setInterval(() => {
      run();
    }, 60_000);

    const statusInterval = window.setInterval(() => {
      run();
    }, 15_000);

    return () => {
      window.cancelAnimationFrame(frame);
      window.clearInterval(dataInterval);
      window.clearInterval(statusInterval);
    };
  }, [load]);

  useEffect(() => {
    if (!data || !status) {
      return;
    }

    const shouldRefresh =
      isMarketOpen() &&
      status.state !== "running" &&
      isSnapshotStale(data.generated_at, status.refresh_interval_minutes || 15) &&
      Date.now() - lastTriggerAtRef.current > 60_000;

    if (shouldRefresh) {
      void triggerRefresh();
    }
  }, [data, status, triggerRefresh]);

  return {
    data,
    status,
    error,
    isLoading,
    isRefreshing: status?.state === "running",
    reload: load,
  };
}
