import fs from "fs";
import path from "path";
import type { SilentAccumulationResponse } from "@/lib/types/silent-accumulation";

const DEFAULT_MARKET_DATA_BASE_URL = "https://raw.githubusercontent.com/cevikburak1/bist_analyzer/market-data";

function getRepoRoot(): string {
  return path.resolve(/*turbopackIgnore: true*/ process.cwd(), "..");
}

function readJson<T>(filePath: string): T {
  return JSON.parse(fs.readFileSync(filePath, "utf-8")) as T;
}

function getMarketDataBaseUrl(): string {
  return (process.env.MARKET_DATA_BASE_URL || DEFAULT_MARKET_DATA_BASE_URL).replace(/\/+$/, "");
}

async function fetchRemoteJson<T>(relativePath: string): Promise<T | null> {
  try {
    const response = await fetch(`${getMarketDataBaseUrl()}/${relativePath}`, {
      cache: "no-store",
    });

    if (!response.ok) {
      return null;
    }

    return response.json() as Promise<T>;
  } catch (error) {
    console.warn(`Remote silent accumulation data unavailable for ${relativePath}:`, error);
    return null;
  }
}

export async function loadSilentAccumulation(): Promise<SilentAccumulationResponse> {
  const remoteData = await fetchRemoteJson<SilentAccumulationResponse>("silent_accumulation/latest.json");
  if (remoteData) {
    return remoteData;
  }

  const filePath = path.join(getRepoRoot(), "output", "web", "silent_accumulation", "latest.json");
  if (!fs.existsSync(filePath)) {
    return {
      generated_at: new Date(0).toISOString(),
      summary: {
        requested_symbols: 0,
        successful_symbols: 0,
        flawless: 0,
        strong: 0,
        watch: 0,
        groups: {},
      },
      items: [],
    };
  }
  return readJson<SilentAccumulationResponse>(filePath);
}
