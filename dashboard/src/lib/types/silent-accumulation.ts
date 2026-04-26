export type SilentAccumulationItem = {
  symbol: string;
  price: number;
  group: number;
  score: number;
  rsi_divergence: boolean;
  volume_accumulation: boolean;
  relative_strength: boolean;
  cmf_positive: boolean;
  before_breakout: boolean;
  bottom_distance_pct: number;
  range_pct: number;
  relative_strength_pct: number;
  rsi: number;
  obv_position: string;
  cmf: number;
  label: string;
  reason: string;
};

export type SilentAccumulationSummary = {
  requested_symbols: number;
  successful_symbols: number;
  flawless: number;
  strong: number;
  watch: number;
  groups: Record<string, string[]>;
};

export type SilentAccumulationResponse = {
  generated_at: string;
  summary: SilentAccumulationSummary;
  items: SilentAccumulationItem[];
};
