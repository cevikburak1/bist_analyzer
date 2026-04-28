import fs from "fs";
import path from "path";
import type { BuffettListResponse, BuffettStockDetail } from "@/lib/types/buffett";

function getRepoRoot(): string {
  return path.resolve(/*turbopackIgnore: true*/ process.cwd(), "..");
}

function getBuffettDir(): string {
  return path.join(getRepoRoot(), "output", "web", "buffett");
}

function readJson<T>(filePath: string): T {
  return JSON.parse(fs.readFileSync(filePath, "utf-8")) as T;
}

export function loadBuffettList(): BuffettListResponse {
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

export function loadBuffettStock(symbol: string): BuffettStockDetail {
  const normalized = symbol.toUpperCase().replace(".IS", "");
  const filePath = path.join(getBuffettDir(), "stocks", `${normalized}.json`);
  if (!fs.existsSync(filePath)) {
    throw new Error(`Buffett detail not found for ${normalized}`);
  }
  return readJson<BuffettStockDetail>(filePath);
}
