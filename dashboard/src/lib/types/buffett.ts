/**
 * Buffett (Temel Analiz) hattı için tip tanımları.
 * Python tarafındaki reports/buffett_snapshot.py JSON şemasıyla birebir.
 */

export type BuffettSector = {
  kind: string;          // BANKA / GYO / SIGORTA / HOLDING / SANAYI / DIGER
  label: string;
  source: string;
};

export type BuffettKeyMetrics = {
  pe: number | null;
  pb: number | null;
  p_fcf: number | null;
  roe_avg_5y: number | null;
  net_margin_avg_5y: number | null;
  net_income_cagr: number | null;
  debt_to_equity: number | string | null;
  dividend_yield: number | null;
};

export type BuffettListItem = {
  symbol: string;
  name: string;
  sector: BuffettSector;
  label_key: string;
  label: string;
  color: string;
  score: number;
  data_quality_pct: number;
  current_price: number | null;
  intrinsic_value: number | null;
  fair_value: number | null;
  fair_value_margin_pct: number | null;
  fair_value_confidence: string | null;
  margin_of_safety: number | null;
  holding_recommendation: string;
  warnings_count: number;
  classification_reason?: string;
  key_metrics: BuffettKeyMetrics;
  horizon_short?: string | null;
  horizon_medium?: string | null;
  horizon_long?: string | null;
};

export type BuffettListSummary = {
  total: number;
  by_label: Record<string, number>;
};

export type BuffettListResponse = {
  generated_at: string;
  summary: BuffettListSummary;
  items: BuffettListItem[];
};

export type BuffettCategoryDetail = {
  earned: number;
  possible: number;
  is_na: boolean;
  details: Record<string, number | string | null | boolean>;
};

export type BuffettScoreBlock = {
  moat: BuffettCategoryDetail;
  financial_health: BuffettCategoryDetail;
  valuation: BuffettCategoryDetail;
  shareholder_policy: BuffettCategoryDetail;
  total_score: number;
  data_quality_pct: number;
  has_minimum_data: boolean;
};

export type BuffettIntrinsic = {
  intrinsic_value_per_share: number | null;
  enterprise_value: number | null;
  base_fcf: number | null;
  growth_used: number | null;
  discount_rate: number;
  terminal_growth: number;
  projection_years: number;
  shares_outstanding: number | null;
  margin_of_safety: number | null;
  current_price: number | null;
  is_na: boolean;
  reason: string;
};

export type FairValueMethod = {
  label: string;
  value: number | null;
  source: string;
  weight: number;
};

export type FairValueFinancialRow = {
  period: string | null;
  net_earnings: number | null;
  revenue: number | null;
  ebit: number | null;
  ebitda: number | null;
  fcf: number | null;
  roe: number | null;
};

export type FairValueBlock = {
  fair_value: number | null;
  current_price: number | null;
  margin_pct: number | null;
  aggregation_method: string;
  confidence_label: string;
  confidence_cv: number | null;
  valid_methods: number;
  market: string;
  currency: string;
  bond_benchmark: string;
  inflation_region: string;
  high_inflation_warning: boolean;
  sector_key: string;
  sector_label: string;
  forward_eps_source: string;
  methods: Record<string, FairValueMethod>;
  financials_table: FairValueFinancialRow[];
  alerts: string[];
};

export type BuffettClassificationFactor = {
  rule: string;
  status: string;
  detail: string;
};

export type BuffettHorizonVerdict = {
  verdict: string;
  label: string;
  color: string;
  reason: string;
  factors: string[];
};

export type BuffettHorizonGuidance = {
  short: BuffettHorizonVerdict;
  medium: BuffettHorizonVerdict;
  long: BuffettHorizonVerdict;
  overall: string;
};

export type BuffettSignalBlock = {
  symbol: string;
  label_key: string;
  label: string;
  color: string;
  total_score: number;
  margin_of_safety: number | null;
  holding_recommendation: string;
  warnings: string[];
  classification_reason: string;
  classification_factors: BuffettClassificationFactor[];
  horizon_guidance: BuffettHorizonGuidance | null;
};

export type BuffettHistoryPoint = {
  period: string | null;
  value?: number | null;
  roe?: number | null;
  dividend?: number | null;
};

export type BuffettHistory = {
  roe: BuffettHistoryPoint[];
  revenue: BuffettHistoryPoint[];
  net_income: BuffettHistoryPoint[];
  free_cash_flow: BuffettHistoryPoint[];
  debt_to_equity: BuffettHistoryPoint[];
  dividends: BuffettHistoryPoint[];
};

export type BuffettStockDetail = {
  generated_at: string;
  symbol: string;
  name: string;
  sector: BuffettSector;
  info: Record<string, number | string | null>;
  signal: BuffettSignalBlock;
  score: BuffettScoreBlock;
  intrinsic: BuffettIntrinsic;
  fair_value: FairValueBlock | null;
  history: BuffettHistory;
  fetch_errors: string[];
  fetched_at: string;
};
