export type MarketRegime = {
  regime: string;
  label: string;
  index_price: number;
  sma_short: number;
  sma_long: number;
  performance_20d: number;
};

export type ReportSummary = {
  total: number;
  buy: number;
  sell: number;
  hold: number;
};

export type ReportMeta = {
  requested_symbols: number;
  successful_symbols: number;
  refresh_interval_minutes: number;
};

export type Timeframes = {
  daily: string;
  weekly: string;
  monthly: string;
  yearly: string;
};

export type TargetLevels = {
  short_target: number;
  short_rr: number;
  short_reward_pct: number;
  medium_target: number;
  medium_rr: number;
  medium_reward_pct: number;
  long_target: number;
  long_rr: number;
  long_reward_pct: number;
  stop_loss: number;
  risk_pct: number;
};

export type FibonacciData = {
  support: number;
  resistance: number;
  zone: string;
  swing_low: number;
  swing_high: number;
  retracement_levels: Record<string, number>;
  extension_levels: Record<string, number>;
};

export type CandlePattern = {
  name: string;
  direction: string;
  strength: string;
  description: string;
};

export type ElliottWaveData = {
  current_wave: string;
  phase: string;
  confidence: string;
  next_expected: string;
};

export type CommentaryData = {
  summary: string;
  paragraph: string;
  key_points: string[];
  risks: string[];
};

export type ScoreBreakdown = {
  trend: number;
  momentum: number;
  volume: number;
  price_position: number;
  market_regime: number;
};

export type ReportSignal = {
  symbol: string;
  price: number;
  score: number;
  signal_daily: string;
  summary: string;
  timeframes: Timeframes;
  trend: string;
  rsi: number;
  volume_status: string;
  entry: number;
  stop_loss: number;
  target: number;
  risk_pct: number;
  reward_pct: number;
  rr_ratio: number;
  targets: TargetLevels;
  fibonacci: FibonacciData;
  candle_patterns: CandlePattern[];
  candle_summary: string;
  candle_bias: string;
  elliott_wave: ElliottWaveData;
  commentary: CommentaryData;
  reason: string;
  score_breakdown: ScoreBreakdown;
};

export type ReportData = {
  generated_at: string;
  market_regime: MarketRegime;
  summary: ReportSummary;
  meta: ReportMeta;
  signals: ReportSignal[];
};

export type StockSeriesPoint = {
  date: string;
  open: number | null;
  high: number | null;
  low: number | null;
  close: number | null;
  volume: number | null;
  sma_short: number | null;
  sma_long: number | null;
  bb_upper: number | null;
  bb_lower: number | null;
  rsi: number | null;
};

export type StockDetailData = {
  generated_at: string;
  market_regime: MarketRegime;
  meta: ReportMeta;
  signal: ReportSignal;
  series: StockSeriesPoint[];
};

export type AnalysisStatus = {
  state: "idle" | "running" | "error";
  run_id: string;
  pid: number;
  requested_symbols: number;
  successful_symbols: number;
  refresh_interval_minutes: number;
  started_at: string | null;
  finished_at: string | null;
  last_success_at: string | null;
  error: string;
  updated_at: string;
};
