"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import type { BuffettListResponse, BuffettStockDetail } from "@/lib/types/buffett";

type Payload = BuffettListResponse | BuffettStockDetail;

type Options = { symbol?: string };

async function fetchJson<T>(url: string) {
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`Request failed: ${url}`);
  }
  return (await res.json()) as T;
}

export function useBuffettData<T extends Payload>({ symbol }: Options = {}) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string>("");
  const [isLoading, setIsLoading] = useState(true);

  const url = useMemo(
    () => (symbol ? `/api/buffett/${symbol}` : "/api/buffett"),
    [symbol],
  );

  const load = useCallback(async () => {
    try {
      const next = await fetchJson<T>(url);
      setData(next);
      setError("");
    } catch (e) {
      console.error(e);
      setError("Buffett verisi alınamadı.");
    } finally {
      setIsLoading(false);
    }
  }, [url]);

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => {
      void load();
    });
    return () => window.cancelAnimationFrame(frame);
  }, [load]);

  return { data, error, isLoading, reload: load };
}
