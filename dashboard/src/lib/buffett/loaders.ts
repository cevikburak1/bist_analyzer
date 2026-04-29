import fs from "fs";
import path from "path";
import type { BuffettListResponse, BuffettStockDetail } from "@/lib/types/buffett";

const DEFAULT_MARKET_DATA_BASE_URL = "https://raw.githubusercontent.com/cevikburak1/bist_analyzer/market-data";

function getRepoRoot(): string {
  return path.resolve(/*turbopackIgnore: true*/ process.cwd(), "..");
}

function getBuffettDir(): string {
  return path.join(getRepoRoot(), "output", "web", "buffett");
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
    console.warn(`Remote Buffett data unavailable for ${relativePath}:`, error);
    return null;
  }
}

export async function loadBuffettList(): Promise<BuffettListResponse> {
  const remoteList = await fetchRemoteJson<BuffettListResponse>("buffett/latest.json");
  if (remoteList) {
    return remoteList;
  }

  const filePath = path.join(getBuffettDir(), "latest.json");
  if (!fs.existsSync(filePath)) {
    return {
      generated_at: new Date(0).toISOString(),
      summary: { total: 0, by_label: {} },
      items: [],
    };
  }
  return readJson<BuffettListResponse>(filePath);
}

export async function loadBuffettStock(symbol: string): Promise<BuffettStockDetail> {
  const normalized = symbol.toUpperCase().replace(".IS", "");
  const remoteStock = await fetchRemoteJson<BuffettStockDetail>(`buffett/stocks/${normalized}.json`);
  if (remoteStock) {
    return remoteStock;
  }

  const filePath = path.join(getBuffettDir(), "stocks", `${normalized}.json`);
  if (!fs.existsSync(filePath)) {
    throw new Error(`Buffett detail not found for ${normalized}`);
  }
  return readJson<BuffettStockDetail>(filePath);
}
