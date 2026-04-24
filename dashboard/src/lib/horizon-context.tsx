"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import type { HorizonKey } from "@/lib/types/report";

type HorizonContextValue = {
  horizon: HorizonKey;
  setHorizon: (h: HorizonKey) => void;
};

const STORAGE_KEY = "bist_analyzer.horizon";
const DEFAULT_HORIZON: HorizonKey = "short";

export const HORIZON_OPTIONS: { value: HorizonKey; label: string; subtitle: string }[] = [
  { value: "short", label: "Gunluk", subtitle: "1-5 gun" },
  { value: "swing", label: "Haftalik", subtitle: "1-4 hafta" },
  { value: "medium", label: "Aylik", subtitle: "1-6 ay" },
  { value: "long", label: "Yillik", subtitle: "6+ ay" },
];

const HorizonContext = createContext<HorizonContextValue | null>(null);

export function HorizonProvider({ children }: { children: React.ReactNode }) {
  const [horizon, setHorizonState] = useState<HorizonKey>(DEFAULT_HORIZON);

  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      const stored = window.localStorage.getItem(STORAGE_KEY);
      if (stored === "short" || stored === "swing" || stored === "medium" || stored === "long") {
        setHorizonState(stored);
      }
    } catch {
      // localStorage devre disi olabilir; default ile devam
    }
  }, []);

  const setHorizon = useCallback((h: HorizonKey) => {
    setHorizonState(h);
    if (typeof window !== "undefined") {
      try {
        window.localStorage.setItem(STORAGE_KEY, h);
      } catch {
        // sessizce yut
      }
    }
  }, []);

  const value = useMemo(() => ({ horizon, setHorizon }), [horizon, setHorizon]);

  return <HorizonContext.Provider value={value}>{children}</HorizonContext.Provider>;
}

export function useHorizon(): HorizonContextValue {
  const ctx = useContext(HorizonContext);
  if (!ctx) {
    return { horizon: DEFAULT_HORIZON, setHorizon: () => undefined };
  }
  return ctx;
}
