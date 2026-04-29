import fs from "fs";
import path from "path";
import type { AnalysisStatus, ReportData, StockDetailData } from "@/lib/types/report";

const DEFAULT_MARKET_DATA_BASE_URL = "https://raw.githubusercontent.com/cevikburak1/bist_analyzer/market-data";

function getRepoRoot(): string {
  return path.resolve(/*turbopackIgnore: true*/ process.cwd(), "..");
}

function getOutputDir(): string {
  return path.join(getRepoRoot(), "output");
}

function getWebOutputDir(): string {
  return path.join(getOutputDir(), "web");
}

function getSeedReportPath(): string {
  return path.join(process.cwd(), "src", "data", "seed-report.json");
}

function getMarketDataBaseUrl(): string {
  return (process.env.MARKET_DATA_BASE_URL || DEFAULT_MARKET_DATA_BASE_URL).replace(/\/+$/, "");
}

function readJsonFile<T>(filePath: string): T {
  return JSON.parse(fs.readFileSync(filePath, "utf-8")) as T;
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
    console.warn(`Remote market data unavailable for ${relativePath}:`, error);
    return null;
  }
}

function loadSeedReport(): ReportData | null {
  const seedPath = getSeedReportPath();
  if (!fs.existsSync(seedPath)) {
    return null;
  }

  return readJsonFile<ReportData>(seedPath);
}

function emptyReport(): ReportData {
  return {
    generated_at: new Date(0).toISOString(),
    market_regime: {
      regime: "NOTR",
      label: "VERI BEKLENIYOR",
      index_price: 0,
      sma_short: 0,
      sma_long: 0,
      performance_20d: 0,
    },
    summary: {
      total: 0,
      buy: 0,
      sell: 0,
      hold: 0,
    },
    meta: {
      requested_symbols: 0,
      successful_symbols: 0,
      refresh_interval_minutes: 15,
    },
    signals: [],
  };
}

export async function loadLatestReport(): Promise<ReportData> {
  const remoteReport = await fetchRemoteJson<ReportData>("latest_report.json");
  if (remoteReport) {
    return remoteReport;
  }

  const webReportPath = path.join(getWebOutputDir(), "latest_report.json");
  if (fs.existsSync(webReportPath)) {
    return readJsonFile<ReportData>(webReportPath);
  }

  const seedReport = loadSeedReport();
  if (seedReport) {
    return seedReport;
  }

  const outputDir = getOutputDir();
  if (!fs.existsSync(outputDir)) {
    return emptyReport();
  }

  const files = fs.readdirSync(outputDir);
  const jsonFiles = files
    .filter((file) => file.startsWith("signals_") && file.endsWith(".json"))
    .sort((left, right) => right.localeCompare(left));

  if (jsonFiles.length === 0) {
    return emptyReport();
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

export async function loadStockDetail(symbol: string): Promise<StockDetailData> {
  const normalized = symbol.toUpperCase().replace(".IS", "");
  const remoteDetail = await fetchRemoteJson<StockDetailData>(`stocks/${normalized}.json`);
  if (remoteDetail) {
    return remoteDetail;
  }

  const filePath = path.join(getWebOutputDir(), "stocks", `${normalized}.json`);

  if (fs.existsSync(filePath)) {
    return readJsonFile<StockDetailData>(filePath);
  }

  const seedReport = loadSeedReport();
  const seedSignal = seedReport?.signals.find((signal) => signal.symbol === normalized);
  if (seedReport && seedSignal) {
    return {
      generated_at: seedReport.generated_at,
      market_regime: seedReport.market_regime,
      meta: seedReport.meta,
      signal: seedSignal,
      series: [],
      intraday_series: [],
    };
  }

  throw new Error(`Stock detail not found for ${normalized}`);
}

function loadLocalAnalysisStatus(): AnalysisStatus {
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

export async function loadAnalysisStatus({ preferRemote = true } = {}): Promise<AnalysisStatus> {
  if (preferRemote) {
    const remoteStatus = await fetchRemoteJson<AnalysisStatus>("analysis_status.json");
    if (remoteStatus) {
      return remoteStatus;
    }
  }

  return loadLocalAnalysisStatus();
}

export function getRepoPaths() {
  return {
    repoRoot: getRepoRoot(),
    outputDir: getOutputDir(),
    webOutputDir: getWebOutputDir(),
  };
}
