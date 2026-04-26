"use client";

import type { StockDetailData, StockSeriesPoint } from "@/lib/types/report";

type AnkaV2ChartProps = {
  detail: StockDetailData;
};

const WIDTH = 1180;
const HEIGHT = 640;
const LEFT = 52;
const RIGHT = 88;
const TOP = 40;
const PRICE_BOTTOM = 500;
const VOLUME_TOP = 525;
const VOLUME_BOTTOM = 608;

function fmt(value: number) {
  return new Intl.NumberFormat("tr-TR", {
    maximumFractionDigits: value >= 10 ? 2 : 3,
    minimumFractionDigits: value >= 10 ? 2 : 3,
  }).format(value);
}

function numeric(value: number | null | undefined) {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function createScale(domainMin: number, domainMax: number, rangeMin: number, rangeMax: number) {
  const span = domainMax - domainMin || 1;
  return (value: number) => rangeMax - ((value - domainMin) / span) * (rangeMax - rangeMin);
}

function pathFromPoints(points: Array<[number, number]>) {
  if (points.length === 0) {
    return "";
  }
  return points.map(([x, y], index) => `${index === 0 ? "M" : "L"}${x.toFixed(2)} ${y.toFixed(2)}`).join(" ");
}

function bandPath(
  data: StockSeriesPoint[],
  xFor: (index: number) => number,
  yFor: (value: number) => number,
  upperKey: keyof StockSeriesPoint,
  lowerKey: keyof StockSeriesPoint,
) {
  const upper: Array<[number, number]> = [];
  const lower: Array<[number, number]> = [];
  data.forEach((point, index) => {
    const upperValue = numeric(point[upperKey] as number | null);
    const lowerValue = numeric(point[lowerKey] as number | null);
    if (upperValue === null || lowerValue === null) {
      return;
    }
    upper.push([xFor(index), yFor(upperValue)]);
    lower.unshift([xFor(index), yFor(lowerValue)]);
  });
  return `${pathFromPoints(upper)} ${pathFromPoints(lower)} Z`;
}

function linePath(data: StockSeriesPoint[], xFor: (index: number) => number, yFor: (value: number) => number, key: keyof StockSeriesPoint) {
  const points: Array<[number, number]> = [];
  data.forEach((point, index) => {
    const value = numeric(point[key] as number | null);
    if (value !== null) {
      points.push([xFor(index), yFor(value)]);
    }
  });
  return pathFromPoints(points);
}

export function AnkaV2Chart({ detail }: AnkaV2ChartProps) {
  const data = detail.series.slice(-120);
  const fibLevels = Object.entries(detail.signal.fibonacci.retracement_levels)
    .map(([ratio, value]) => ({ label: `F${(Number(ratio) * 100).toFixed(1)}%`, value }))
    .filter((item) => Number.isFinite(item.value));

  const priceValues = data.flatMap((point) => [
    point.high,
    point.low,
    point.anka_upper_wing,
    point.anka_lower_wing,
    point.anka_inner_upper_wing,
    point.anka_inner_lower_wing,
  ]).filter((value): value is number => numeric(value) !== null);
  fibLevels.forEach((level) => priceValues.push(level.value));

  const minPrice = Math.min(...priceValues);
  const maxPrice = Math.max(...priceValues);
  const pad = Math.max((maxPrice - minPrice) * 0.08, 0.01);
  const yFor = createScale(minPrice - pad, maxPrice + pad, TOP, PRICE_BOTTOM);
  const maxVolume = Math.max(...data.map((point) => numeric(point.volume) ?? 0), 1);
  const volumeY = createScale(0, maxVolume, VOLUME_TOP, VOLUME_BOTTOM);
  const xFor = (index: number) => LEFT + (index / Math.max(data.length - 1, 1)) * (WIDTH - LEFT - RIGHT);
  const candleWidth = Math.max(3, Math.min(9, (WIDTH - LEFT - RIGHT) / Math.max(data.length, 1) * 0.58));
  const last = data[data.length - 1];

  const ticks = Array.from({ length: 6 }, (_, index) => minPrice + ((maxPrice - minPrice) / 5) * index);
  const dateTicks = data.filter((_, index) => index % Math.max(1, Math.floor(data.length / 9)) === 0);

  return (
    <div className="grid min-w-0 gap-4">
      <div className="overflow-hidden rounded-[10px] border border-slate-800 bg-black shadow-2xl shadow-black/50">
        <div className="flex items-center justify-between border-b border-slate-900 px-4 py-2 text-xs">
          <div>
            <div className="font-semibold text-slate-200">
              {detail.signal.symbol} · 1G · BIST · ANKA v2 Adaptif Trend Kanalı
            </div>
            <div className="mt-1 text-slate-500">TradingView benzeri doğrulama ekranı · Son {data.length} bar</div>
          </div>
          <div className="text-right text-slate-500">
            <div>Son: <span className="text-cyan-200">{fmt(detail.signal.price)}</span></div>
            <div>Vadi: <span className="text-amber-200">{detail.signal.anka_v2?.valley.name}</span></div>
          </div>
        </div>

        <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} className="block h-[640px] w-full bg-black">
          <defs>
            <linearGradient id="outerWing" x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" stopColor="#059669" stopOpacity="0.48" />
              <stop offset="50%" stopColor="#0f766e" stopOpacity="0.28" />
              <stop offset="100%" stopColor="#7c3aed" stopOpacity="0.34" />
            </linearGradient>
            <linearGradient id="innerWing" x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" stopColor="#16a34a" stopOpacity="0.24" />
              <stop offset="100%" stopColor="#be185d" stopOpacity="0.22" />
            </linearGradient>
          </defs>

          <rect x="0" y="0" width={WIDTH} height={HEIGHT} fill="#000000" />

          {ticks.map((tick) => {
            const y = yFor(tick);
            return (
              <g key={tick}>
                <line x1={LEFT} x2={WIDTH - RIGHT + 52} y1={y} y2={y} stroke="#111827" strokeDasharray="4 8" />
                <text x={WIDTH - RIGHT + 58} y={y + 4} fill="#60a5fa" fontSize="11">{fmt(tick)}</text>
              </g>
            );
          })}

          {dateTicks.map((point, index) => {
            const x = xFor(data.indexOf(point));
            return (
              <g key={`${point.date}-${index}`}>
                <line x1={x} x2={x} y1={TOP} y2={VOLUME_BOTTOM} stroke="#0f172a" strokeDasharray="2 8" />
                <text x={x - 14} y={626} fill="#64748b" fontSize="10">{point.date.slice(5)}</text>
              </g>
            );
          })}

          {data.map((point, index) => {
            if (!point.anka_is_ash_phase) {
              return null;
            }
            const x = xFor(index);
            const nextX = index < data.length - 1 ? xFor(index + 1) : x + candleWidth;
            return <rect key={`ash-${point.date}`} x={x - candleWidth / 2} y={TOP} width={Math.max(4, nextX - x)} height={PRICE_BOTTOM - TOP} fill="#94a3b8" opacity="0.12" />;
          })}

          <path d={bandPath(data, xFor, yFor, "anka_upper_wing", "anka_lower_wing")} fill="url(#outerWing)" stroke="#0f766e" strokeWidth="1.4" opacity="0.95" />
          <path d={bandPath(data, xFor, yFor, "anka_inner_upper_wing", "anka_inner_lower_wing")} fill="url(#innerWing)" stroke="#475569" strokeWidth="0.8" opacity="0.95" />

          {fibLevels.map((level) => {
            const y = yFor(level.value);
            return (
              <g key={level.label}>
                <line x1={LEFT} x2={WIDTH - RIGHT + 38} y1={y} y2={y} stroke="#60a5fa" strokeDasharray="8 8" opacity="0.55" />
                <text x={WIDTH - RIGHT + 44} y={y - 3} fill="#93c5fd" fontSize="10">{level.label}</text>
                <text x={WIDTH - RIGHT + 44} y={y + 10} fill="#60a5fa" fontSize="9">{fmt(level.value)}</text>
              </g>
            );
          })}

          {data.map((point, index) => {
            const open = numeric(point.open);
            const high = numeric(point.high);
            const low = numeric(point.low);
            const close = numeric(point.close);
            const volume = numeric(point.volume) ?? 0;
            if (open === null || high === null || low === null || close === null) {
              return null;
            }
            const x = xFor(index);
            const up = close >= open;
            const color = up ? "#22d3c5" : "#fb5b76";
            const bodyTop = yFor(Math.max(open, close));
            const bodyBottom = yFor(Math.min(open, close));
            return (
              <g key={point.date}>
                <rect x={x - candleWidth / 2} y={volumeY(volume)} width={candleWidth} height={VOLUME_BOTTOM - volumeY(volume)} fill="#1e293b" opacity="0.55" />
                <line x1={x} x2={x} y1={yFor(high)} y2={yFor(low)} stroke={color} strokeWidth="1.2" />
                <rect x={x - candleWidth / 2} y={bodyTop} width={candleWidth} height={Math.max(2, bodyBottom - bodyTop)} fill={color} rx="1.5" />
              </g>
            );
          })}

          <path d={linePath(data, xFor, yFor, "anka_body")} fill="none" stroke="#facc15" strokeWidth="2.2" />
          <path d={linePath(data, xFor, yFor, "close")} fill="none" stroke="#06b6d4" strokeWidth="1.2" opacity="0.55" />

          {data.map((point, index) => {
            const previous = data[index - 1];
            const close = numeric(point.close);
            const innerUpper = numeric(point.anka_inner_upper_wing);
            const prevClose = numeric(previous?.close);
            const prevInnerUpper = numeric(previous?.anka_inner_upper_wing);
            if (close === null || innerUpper === null || prevClose === null || prevInnerUpper === null) {
              return null;
            }
            if (!(close > innerUpper && prevClose <= prevInnerUpper)) {
              return null;
            }
            const x = xFor(index);
            const y = yFor(close) + 18;
            return <path key={`sig-${point.date}`} d={`M${x} ${y - 12} L${x - 6} ${y} L${x + 6} ${y} Z`} fill="#facc15" stroke="#000" strokeWidth="0.6" />;
          })}

          <line x1={LEFT} x2={WIDTH - RIGHT + 52} y1={VOLUME_TOP} y2={VOLUME_TOP} stroke="#0f172a" />
          <text x={LEFT} y={24} fill="#94a3b8" fontSize="11">SASA örneği gibi koyu grafik, adaptif kanatlar, Fibo çizgileri ve sinyal işaretleri</text>
          {last ? <text x={WIDTH - RIGHT + 58} y={yFor(numeric(last.close) ?? detail.signal.price) + 4} fill="#22d3ee" fontSize="11">{fmt(numeric(last.close) ?? detail.signal.price)}</text> : null}
        </svg>
      </div>

      <div className="overflow-hidden rounded-[10px] border border-slate-800 bg-black p-4">
        <div className="mb-3 flex items-center justify-between">
          <div>
            <h2 className="text-sm font-semibold text-slate-100">Yedi Vadi Osilatörü</h2>
            <p className="text-xs text-slate-500">Sarı çizgi vadi puanı, gri kolonlar Kül Fazı sıkışmasıdır.</p>
          </div>
          <div className="rounded bg-yellow-400 px-3 py-1 text-xs font-bold text-black">{detail.signal.anka_v2?.valley.score.toFixed(1)}</div>
        </div>
        <svg viewBox={`0 0 ${WIDTH} 220`} className="block h-[220px] w-full bg-black">
          {Array.from({ length: 6 }, (_, index) => index * 20).map((tick) => {
            const y = createScale(0, 100, 20, 185)(tick);
            return (
              <g key={tick}>
                <line x1={LEFT} x2={WIDTH - RIGHT + 52} y1={y} y2={y} stroke="#111827" strokeDasharray="4 8" />
                <text x={WIDTH - RIGHT + 58} y={y + 4} fill="#60a5fa" fontSize="10">{tick}</text>
              </g>
            );
          })}
          {data.map((point, index) => {
            if (!point.anka_is_ash_phase) {
              return null;
            }
            const x = xFor(index);
            return <rect key={`osc-ash-${point.date}`} x={x - candleWidth / 2} y={20} width={candleWidth * 1.8} height={165} fill="#94a3b8" opacity="0.18" />;
          })}
          <path
            d={linePath(data, xFor, createScale(0, 100, 20, 185), "anka_valley_score")}
            fill="none"
            stroke="#facc15"
            strokeWidth="2.4"
          />
        </svg>
      </div>
    </div>
  );
}
