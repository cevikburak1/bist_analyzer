import fs from "fs";
import path from "path";
import type { SilentAccumulationResponse } from "@/lib/types/silent-accumulation";

function getRepoRoot(): string {
  return path.resolve(process.cwd(), "..");
}

function readJson<T>(filePath: string): T {
  return JSON.parse(fs.readFileSync(filePath, "utf-8")) as T;
}

export function loadSilentAccumulation(): SilentAccumulationResponse {
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
