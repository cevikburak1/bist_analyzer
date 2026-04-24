import fs from "fs";
import path from "path";
import type { AnalysisStatus, ReportData, StockDetailData } from "@/lib/types/report";

function getRepoRoot(): string {
  return path.resolve(process.cwd(), "..");
}

function getOutputDir(): string {
  return path.join(getRepoRoot(), "output");
}

function getWebOutputDir(): string {
  return path.join(getOutputDir(), "web");
}

function readJsonFile<T>(filePath: string): T {
  return JSON.parse(fs.readFileSync(filePath, "utf-8")) as T;
}

export function loadLatestReport(): ReportData {
  const webReportPath = path.join(getWebOutputDir(), "latest_report.json");
  if (fs.existsSync(webReportPath)) {
    return readJsonFile<ReportData>(webReportPath);
  }

  const outputDir = getOutputDir();
  const files = fs.readdirSync(outputDir);
  const jsonFiles = files
    .filter((file) => file.startsWith("signals_") && file.endsWith(".json"))
    .sort((left, right) => right.localeCompare(left));

  if (jsonFiles.length === 0) {
    throw new Error("No analysis report found");
  }

  const fallback = readJsonFile<{
    date: string;
    market_regime: ReportData["market_regime"];
    summary: ReportData["summary"];
    signals: Array<Record<string, unknown>>;
  }>(path.join(outputDir, jsonFiles[0]));

  return {
    generated_at: fallback.date,
    market_regime: fallback.market_regime,
    summary: fallback.summary,
    meta: {
      requested_symbols: fallback.summary.total,
      successful_symbols: fallback.summary.total,
      refresh_interval_minutes: 15,
    },
    signals: [],
  };
}

export function loadStockDetail(symbol: string): StockDetailData {
  const normalized = symbol.toUpperCase().replace(".IS", "");
  const filePath = path.join(getWebOutputDir(), "stocks", `${normalized}.json`);

  if (!fs.existsSync(filePath)) {
    throw new Error(`Stock detail not found for ${normalized}`);
  }

  return readJsonFile<StockDetailData>(filePath);
}

export function loadAnalysisStatus(): AnalysisStatus {
  const filePath = path.join(getWebOutputDir(), "analysis_status.json");

  if (!fs.existsSync(filePath)) {
    return {
      state: "idle",
      run_id: "",
      pid: 0,
      requested_symbols: 0,
      successful_symbols: 0,
      refresh_interval_minutes: 15,
      started_at: null,
      finished_at: null,
      last_success_at: null,
      error: "",
      updated_at: new Date(0).toISOString(),
    };
  }

  return readJsonFile<AnalysisStatus>(filePath);
}

export function getRepoPaths() {
  return {
    repoRoot: getRepoRoot(),
    outputDir: getOutputDir(),
    webOutputDir: getWebOutputDir(),
  };
}
