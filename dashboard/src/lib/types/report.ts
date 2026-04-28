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
  squeeze_breakout: number;
  wr_pct: number;
  wr_samples: number;
  adx: number;
  v_kat: number;
  dzl_ok: boolean;
  sqz_ok: boolean;
  ema_distance_pct: number;
  overextended: boolean;
  details: Record<string, unknown>;
};

export type HorizonVerdict = {
  verdict: string;
  label: string;
  color: string;
  reason: string;
  factors: string[];
  rr: number | null;
  target_price: number | null;
  reward_pct: number | null;
};

export type HorizonGuidance = {
  short: HorizonVerdict;
  medium: HorizonVerdict;
  long: HorizonVerdict;
  overall: string;
};

export type HorizonKey = "short" | "swing" | "medium" | "long";

export type HorizonCategoryScore = {
  earned: number;
  possible: number;
  factors: string[];
};

export type HorizonTargets = {
  direction: "LONG" | "SHORT" | "NONE" | string;
  entry: number;
  stop_loss: number;
  target_price: number;
  risk_pct: number;
  reward_pct: number;
  rr: number;
  note: string;
};

export type HorizonScore = {
  horizon: HorizonKey;
  label: string;
  total: number;
  decision: string;
  reason: string;
  reason_factors: string[];
  categories: Record<string, HorizonCategoryScore>;
  targets: HorizonTargets | null;
};

export type HorizonScoreSet = {
  short: HorizonScore;
  swing: HorizonScore;
  medium: HorizonScore;
  long: HorizonScore;
};

export type AnkaValley = {
  score: number;
  name: string;
  color: string;
  metaphor: string;
  market_comment: string;
  potential_move: string;
};

export type AnkaKnnVolume = {
  relative_volume: number;
  neighbor_count: number;
  bullish_ratio: number;
  bearish_ratio: number;
  confidence: number;
  label: string;
};

export type AnkaFibonacciConfirmation = {
  bonus: number;
  label: string;
  level_name: string;
  level_price: number;
  message: string;
};

export type AnkaCalibration = {
  status: string;
  label: string;
  total_success_rate: number | null;
  bull_success_rate: number | null;
  bear_success_rate: number | null;
  total_signals: number;
  bull_signals: number;
  bear_signals: number;
};

export type AnkaLayerState = {
  score: number;
  direction: string;
  symbol: string;
};

export type AnkaLayerEngine = {
  score: number;
  confidence_stars: number;
  chain: string;
  scenario: string;
  recommendation: string;
  layers: {
    valley: AnkaLayerState;
    momentum: AnkaLayerState;
    trend: AnkaLayerState;
    volatility: AnkaLayerState;
    signal: AnkaLayerState;
  };
};

export type AnkaLrEngine = {
  score: number;
  direction: string;
  slope_pct: number;
  r2: number;
  intensity: string;
};

export type AnkaKnnPattern = {
  score: number;
  prediction: string;
  confidence: number;
  neighbors: number;
  weighted_return_pct?: number;
  params: {
    n: number;
    nd: number;
    ny: number;
    spacing: number;
    atr_n: number;
    features: string[];
  };
};

export type AnkaV2Data = {
  synthesis_score: number;
  synthesis_decision: string;
  primary_signal: string;
  phase: string;
  trend: string;
  momentum_label: string;
  fire_power: number;
  body: number;
  breath: number;
  upper_wing: number;
  lower_wing: number;
  inner_upper_wing: number;
  inner_lower_wing: number;
  is_ash_phase: boolean;
  valley: AnkaValley;
  knn_volume: AnkaKnnVolume;
  fibonacci_confirmation: AnkaFibonacciConfirmation;
  calibration: AnkaCalibration;
  lr_engine: AnkaLrEngine;
  knn_pattern: AnkaKnnPattern;
  layer_engine: AnkaLayerEngine;
  synthesis_weights: Record<string, number>;
  alerts: string[];
};

export type TradingViewSnapshot = {
  symbol: string;
  close: number | null;
  high: number | null;
  low: number | null;
  volume: number | null;
  change_pct: number | null;
  source: string;
  status: string;
  price_delta_pct: number | null;
  volume_delta_pct: number | null;
};

export type CupHandlePoint = {
  index: number;
  price: number;
};

export type CupHandleQuality = {
  status: string;
  is_detected: boolean;
  is_confirmed: boolean;
  cup_symmetry: number | null;
  handle_depth_pct: number | null;
  breakout_quality: number | null;
  score: number | null;
  rim_price: number | null;
  target_price: number | null;
  cup_depth: number | null;
  message: string;
  points: {
    left_rim?: CupHandlePoint;
    cup_base?: CupHandlePoint;
    right_rim?: CupHandlePoint;
    handle_low?: CupHandlePoint;
    breakout_index?: number;
    target_end_index?: number;
  };
  params: Record<string, number | string | boolean>;
};

export type AmdRange = {
  start_index: number;
  end_index: number;
  start_time: string;
  end_time: string;
  high: number;
  low: number;
  midpoint: number;
};

export type AmdSweep = {
  direction: string;
  index: number;
  time: string;
  price: number;
  liquidity_pool: string;
  rejection_pct: number;
};

export type AmdCisd = {
  direction: string;
  index: number | null;
  time: string | null;
  level: number;
  confirmed: boolean;
  range_high: number;
  range_low: number;
};

export type AmdLiquidityLevel = {
  start_index: number;
  end_index: number;
  start_time: string;
  end_time: string;
  price: number;
};

export type AmdKeyOpen = {
  label: string;
  time: string;
  price: number;
};

export type AmdHtfSweep = {
  direction: string;
  time: string;
  level: number;
  swept_price: number;
};

export type AmdModel = {
  status: string;
  model_bias: string;
  phase: string;
  score: number;
  timeframe: string;
  interval: string;
  summary: string;
  accumulation: AmdRange | null;
  manipulation: AmdRange | null;
  distribution: AmdRange | null;
  sweep: AmdSweep | null;
  cisd: AmdCisd | null;
  projections: Record<string, number>;
  htf_sweep: AmdHtfSweep | null;
  equal_highs: AmdLiquidityLevel[];
  equal_lows: AmdLiquidityLevel[];
  key_opens: AmdKeyOpen[];
  alerts: string[];
  params: Record<string, number | string | boolean | number[]>;
};

export type ReportSignal = {
  symbol: string;
  price: number;
  score: number;
  signal_daily: string;
  action: string;
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
  reason_factors: string[];
  score_breakdown: ScoreBreakdown;
  horizon_guidance: HorizonGuidance | null;
  horizon_scores: HorizonScoreSet | null;
  anka_v2: AnkaV2Data | null;
  amd_model: AmdModel | null;
  tradingview_snapshot: TradingViewSnapshot | null;
  cup_handle_quality: CupHandleQuality | null;
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
  ema_fast: number | null;
  ema_signal: number | null;
  ema20: number | null;
  ema50: number | null;
  ema200: number | null;
  bb_upper: number | null;
  bb_lower: number | null;
  bb_width_pct: number | null;
  adx: number | null;
  v_kat: number | null;
  perfect_order: boolean | null;
  squeeze_on: boolean | null;
  squeeze_breakout: boolean | null;
  rsi: number | null;
  anka_body: number | null;
  anka_upper_wing: number | null;
  anka_lower_wing: number | null;
  anka_inner_upper_wing: number | null;
  anka_inner_lower_wing: number | null;
  anka_valley_score: number | null;
  anka_is_ash_phase: boolean | null;
};

export type IntradaySeriesPoint = {
  date: string;
  open: number | null;
  high: number | null;
  low: number | null;
  close: number | null;
  volume: number | null;
  atr: number | null;
  rsi: number | null;
};

export type StockDetailData = {
  generated_at: string;
  market_regime: MarketRegime;
  meta: ReportMeta;
  signal: ReportSignal;
  series: StockSeriesPoint[];
  intraday_series: IntradaySeriesPoint[];
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
