"use client";

import type { StockDetailData, StockSeriesPoint } from "@/lib/types/report";

type Props = {
  detail: StockDetailData;
};

const WIDTH = 1180;
const HEIGHT = 620;
const LEFT = 54;
const RIGHT = 250;
const TOP = 38;
const PRICE_BOTTOM = 455;
const ENGINE_TOP = 485;
const ENGINE_BOTTOM = 590;

function n(value: number | null | undefined) {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function fmt(value: number) {
  return new Intl.NumberFormat("tr-TR", {
    maximumFractionDigits: value >= 10 ? 2 : 3,
    minimumFractionDigits: value >= 10 ? 2 : 3,
  }).format(value);
}

function scale(min: number, max: number, top: number, bottom: number) {
  const span = max - min || 1;
  return (value: number) => bottom - ((value - min) / span) * (bottom - top);
}

function path(points: Array<[number, number]>) {
  return points.map(([x, y], index) => `${index === 0 ? "M" : "L"}${x.toFixed(2)} ${y.toFixed(2)}`).join(" ");
}

function line(data: StockSeriesPoint[], xFor: (index: number) => number, yFor: (value: number) => number, key: keyof StockSeriesPoint) {
  const points: Array<[number, number]> = [];
  data.forEach((point, index) => {
    const value = n(point[key] as number | null);
    if (value !== null) {
      points.push([xFor(index), yFor(value)]);
    }
  });
  return path(points);
}

function band(data: StockSeriesPoint[], xFor: (index: number) => number, yFor: (value: number) => number) {
  const upper: Array<[number, number]> = [];
  const lower: Array<[number, number]> = [];
  data.forEach((point, index) => {
    const up = n(point.anka_upper_wing);
    const low = n(point.anka_lower_wing);
    if (up !== null && low !== null) {
      upper.push([xFor(index), yFor(up)]);
      lower.unshift([xFor(index), yFor(low)]);
    }
  });
  return `${path(upper)} ${path(lower)} Z`;
}

export function AnkaEngineChart({ detail }: Props) {
  const data = detail.series.slice(-120);
  const anka = detail.signal.anka_v2;
  const values = data.flatMap((point) => [point.high, point.low, point.anka_upper_wing, point.anka_lower_wing]).filter((value): value is number => n(value) !== null);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const pad = Math.max((max - min) * 0.08, 0.01);
  const yFor = scale(min - pad, max + pad, TOP, PRICE_BOTTOM);
  const engineY = scale(0, 100, ENGINE_TOP, ENGINE_BOTTOM);
  const xFor = (index: number) => LEFT + (index / Math.max(data.length - 1, 1)) * (WIDTH - LEFT - RIGHT);
  const candleWidth = Math.max(3, Math.min(8, (WIDTH - LEFT - RIGHT) / Math.max(data.length, 1) * 0.52));
  const priceTicks = Array.from({ length: 6 }, (_, index) => min + ((max - min) / 5) * index);
  const layerScores = anka ? [
    { label: "K", value: anka.layer_engine.score, color: "#22c55e" },
    { label: "LR", value: anka.lr_engine.score, color: "#38bdf8" },
    { label: "kNN", value: anka.knn_pattern.score, color: "#facc15" },
    { label: "S", value: anka.synthesis_score, color: "#f97316" },
  ] : [];

  return (
    <div className="overflow-hidden rounded-[8px] border border-slate-800 bg-black shadow-2xl shadow-black/60">
      <div className="flex items-center justify-between border-b border-slate-900 bg-black px-3 py-2">
        <div>
          <div className="text-xs font-semibold text-slate-200">{detail.signal.symbol} · ANKA Motor Grafiği · LR + K1-K5 + kNN</div>
          <div className="text-[10px] text-slate-500">N=8 · ND=6 · NY=3 · spacing=25 · ATR_N=14 · Sentez: K%40 / LR%30 / kNN%30</div>
        </div>
        <div className="text-right text-[10px] text-slate-500">
          <div>Sentez: <span className="text-orange-200">{anka?.synthesis_decision}</span></div>
          <div>K.Zincir: <span className="text-cyan-200">{anka?.layer_engine.chain}</span></div>
        </div>
      </div>
      <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} className="block h-[620px] w-full bg-black">
        <defs>
          <linearGradient id="engineBand" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="#16a34a" stopOpacity="0.44" />
            <stop offset="48%" stopColor="#0891b2" stopOpacity="0.24" />
            <stop offset="100%" stopColor="#7e22ce" stopOpacity="0.35" />
          </linearGradient>
        </defs>
        <rect width={WIDTH} height={HEIGHT} fill="#000" />
        {priceTicks.map((tick) => {
          const y = yFor(tick);
          return (
            <g key={tick}>
              <line x1={LEFT} x2={WIDTH - RIGHT + 20} y1={y} y2={y} stroke="#111827" strokeDasharray="3 8" />
              <text x={WIDTH - RIGHT + 28} y={y + 4} fill="#60a5fa" fontSize="10">{fmt(tick)}</text>
            </g>
          );
        })}
        {data.map((point, index) => {
          if (!point.anka_is_ash_phase) return null;
          const x = xFor(index);
          return <rect key={point.date} x={x - candleWidth} y={TOP} width={candleWidth * 2.2} height={PRICE_BOTTOM - TOP} fill="#94a3b8" opacity="0.13" />;
        })}
        <path d={band(data, xFor, yFor)} fill="url(#engineBand)" stroke="#0f766e" strokeWidth="1.2" />
        <path d={line(data, xFor, yFor, "anka_body")} fill="none" stroke="#facc15" strokeWidth="2" />
        {data.map((point, index) => {
          const open = n(point.open);
          const close = n(point.close);
          const high = n(point.high);
          const low = n(point.low);
          if (open === null || close === null || high === null || low === null) return null;
          const x = xFor(index);
          const up = close >= open;
          const color = up ? "#22d3c5" : "#fb7185";
          const top = yFor(Math.max(open, close));
          const bottom = yFor(Math.min(open, close));
          return (
            <g key={point.date}>
              <line x1={x} x2={x} y1={yFor(high)} y2={yFor(low)} stroke={color} strokeWidth="1.1" />
              <rect x={x - candleWidth / 2} y={top} width={candleWidth} height={Math.max(2, bottom - top)} fill={color} rx="1" />
            </g>
          );
        })}
        <line x1={LEFT} x2={WIDTH - RIGHT + 20} y1={ENGINE_TOP} y2={ENGINE_TOP} stroke="#1e293b" />
        {[25, 50, 75].map((level) => (
          <line key={level} x1={LEFT} x2={WIDTH - RIGHT + 20} y1={engineY(level)} y2={engineY(level)} stroke="#111827" strokeDasharray="4 8" />
        ))}
        {layerScores.map((item, itemIndex) => {
          const x = WIDTH - RIGHT + 65 + itemIndex * 38;
          const y = engineY(item.value);
          return (
            <g key={item.label}>
              <line x1={x} x2={x} y1={ENGINE_BOTTOM} y2={y} stroke={item.color} strokeWidth="8" opacity="0.65" />
              <circle cx={x} cy={y} r="6" fill={item.color} />
              <text x={x - 10} y={ENGINE_BOTTOM + 16} fill="#94a3b8" fontSize="10">{item.label}</text>
              <text x={x - 12} y={y - 10} fill={item.color} fontSize="10">{item.value.toFixed(1)}</text>
            </g>
          );
        })}
        <path d={line(data, xFor, engineY, "anka_valley_score")} fill="none" stroke="#facc15" strokeWidth="1.8" opacity="0.95" />
        <text x={LEFT} y={ENGINE_TOP - 10} fill="#94a3b8" fontSize="10">Alt panel: Yedi Vadi çizgisi + motor skor kolonları</text>
        <foreignObject x={WIDTH - RIGHT + 20} y={TOP + 20} width={210} height={220}>
          <div className="rounded border border-yellow-500/40 bg-[#061405]/95 p-2 text-[10px] text-slate-200">
            <div className="mb-1 bg-yellow-400 px-1 py-0.5 text-center font-black text-black">MOTOR PANELİ</div>
            <div className="flex justify-between border-b border-slate-700 py-1"><span>K.Motor</span><b>{anka?.layer_engine.score.toFixed(1)}</b></div>
            <div className="flex justify-between border-b border-slate-700 py-1"><span>K.Güven</span><b>{"★".repeat(anka?.layer_engine.confidence_stars ?? 1)}</b></div>
            <div className="flex justify-between border-b border-slate-700 py-1"><span>LR</span><b>{anka?.lr_engine.direction}</b></div>
            <div className="flex justify-between border-b border-slate-700 py-1"><span>kNN</span><b>{anka?.knn_pattern.prediction}</b></div>
            <div className="flex justify-between border-b border-slate-700 py-1"><span>Sentez</span><b>{anka?.synthesis_score.toFixed(1)}</b></div>
            <div className="pt-1 text-yellow-100">{anka?.layer_engine.recommendation}</div>
          </div>
        </foreignObject>
      </svg>
    </div>
  );
}
