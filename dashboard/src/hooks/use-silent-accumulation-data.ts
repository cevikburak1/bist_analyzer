"use client";

import { useCallback, useEffect, useState } from "react";
import type { SilentAccumulationResponse } from "@/lib/types/silent-accumulation";

async function fetchJson<T>(url: string) {
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Request failed: ${url}`);
  }
  return (await response.json()) as T;
}

export function useSilentAccumulationData() {
  const [data, setData] = useState<SilentAccumulationResponse | null>(null);
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      setData(await fetchJson<SilentAccumulationResponse>("/api/silent-accumulation"));
      setError("");
    } catch (nextError) {
      console.error(nextError);
      setError("Sessiz toplama verisi alınamadı.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => {
      void load();
    });
    return () => window.cancelAnimationFrame(frame);
  }, [load]);

  return { data, error, isLoading, reload: load };
}
