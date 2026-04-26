"use client";

import type { AmdLiquidityLevel, AmdRange, StockDetailData } from "@/lib/types/report";

type Props = {
  detail: StockDetailData;
};

const WIDTH = 1180;
const HEIGHT = 620;
const LEFT = 54;
const RIGHT = 250;
const TOP = 34;
const BOTTOM = 560;

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

function rangeBox(
  range: AmdRange | null,
  color: string,
  label: string,
  xFor: (index: number) => number,
  yFor: (value: number) => number,
) {
  if (!range) return null;
  const x = xFor(range.start_index);
  const width = Math.max(8, xFor(range.end_index) - x);
  const y = yFor(range.high);
  const height = Math.max(4, yFor(range.low) - y);
  return (
    <g>
      <rect x={x} y={y} width={width} height={height} fill={color} opacity="0.16" stroke={color} strokeWidth="1.2" />
      <text x={x + 6} y={y + 16} fill={color} fontSize="11" fontWeight="700">{label}</text>
    </g>
  );
}

function liquidityLines(
  levels: AmdLiquidityLevel[],
  label: string,
  color: string,
  xFor: (index: number) => number,
  yFor: (value: number) => number,
) {
  return levels.map((level) => {
    const y = yFor(level.price);
    return (
      <g key={`${label}-${level.start_time}-${level.end_time}`}>
        <line x1={xFor(level.start_index)} x2={xFor(level.end_index)} y1={y} y2={y} stroke={color} strokeDasharray="4 6" strokeWidth="1" />
        <text x={xFor(level.end_index) + 4} y={y - 3} fill={color} fontSize="9">{label}</text>
      </g>
    );
  });
}

export function AmdModelChart({ detail }: Props) {
  const amd = detail.signal.amd_model;
  const data = detail.intraday_series.slice(-90);
  const values = data.flatMap((point) => [point.high, point.low, point.open, point.close]).filter((value): value is number => n(value) !== null);
  Object.values(amd?.projections ?? {}).forEach((value) => values.push(value));
  if (amd?.cisd) {
    values.push(amd.cisd.level);
  }
  if (values.length === 0) {
    return (
      <div className="flex min-h-[420px] items-center justify-center rounded-[8px] border border-slate-800 bg-black text-sm text-slate-500">
        AMD intraday grafik verisi bulunamadı.
      </div>
    );
  }
  const min = Math.min(...values);
  const max = Math.max(...values);
  const pad = Math.max((max - min) * 0.08, 0.01);
  const yFor = scale(min - pad, max + pad, TOP, BOTTOM);
  const xFor = (index: number) => LEFT + (index / Math.max(data.length - 1, 1)) * (WIDTH - LEFT - RIGHT);
  const candleWidth = Math.max(3, Math.min(9, (WIDTH - LEFT - RIGHT) / Math.max(data.length, 1) * 0.54));
  const priceTicks = Array.from({ length: 6 }, (_, index) => min + ((max - min) / 5) * index);

  return (
    <div className="overflow-hidden rounded-[8px] border border-slate-800 bg-black shadow-2xl shadow-black/60">
      <div className="flex items-center justify-between border-b border-slate-900 bg-black px-3 py-2">
        <div>
          <div className="text-xs font-semibold text-slate-200">{detail.signal.symbol} · AMD Model · Accumulation / Manipulation / Distribution</div>
          <div className="text-[10px] text-slate-500">Intraday {amd?.interval ?? "60m"} · CISD · HTF sweep · EQH/EQL · fib projections</div>
        </div>
        <div className="text-right text-[10px] text-slate-500">
          <div>Bias: <span className="text-cyan-200">{amd?.model_bias ?? "NEUTRAL"}</span></div>
          <div>Faz: <span className="text-yellow-100">{amd?.phase ?? "NONE"}</span></div>
        </div>
      </div>
      <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} className="block h-[620px] w-full bg-black">
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
        {rangeBox(amd?.accumulation ?? null, "#38bdf8", "A", xFor, yFor)}
        {rangeBox(amd?.manipulation ?? null, "#fb7185", "M", xFor, yFor)}
        {rangeBox(amd?.distribution ?? null, "#34d399", "D", xFor, yFor)}
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
        {amd?.cisd ? (
          <g>
            <line x1={LEFT} x2={WIDTH - RIGHT + 20} y1={yFor(amd.cisd.level)} y2={yFor(amd.cisd.level)} stroke="#facc15" strokeWidth="1.4" strokeDasharray="8 6" />
            <text x={WIDTH - RIGHT + 28} y={yFor(amd.cisd.level) - 6} fill="#facc15" fontSize="10">CISD {fmt(amd.cisd.level)}</text>
          </g>
        ) : null}
        {Object.entries(amd?.projections ?? {}).map(([multiple, level]) => (
          <g key={multiple}>
            <line x1={LEFT} x2={WIDTH - RIGHT + 20} y1={yFor(level)} y2={yFor(level)} stroke="#22c55e" strokeWidth="1" strokeDasharray="2 8" />
            <text x={WIDTH - RIGHT + 28} y={yFor(level) + 4} fill="#86efac" fontSize="10">{multiple}x {fmt(level)}</text>
          </g>
        ))}
        {liquidityLines(amd?.equal_highs ?? [], "EQH", "#f97316", xFor, yFor)}
        {liquidityLines(amd?.equal_lows ?? [], "EQL", "#a78bfa", xFor, yFor)}
        <foreignObject x={WIDTH - RIGHT + 24} y={TOP + 22} width={210} height={230}>
          <div className="rounded border border-cyan-500/30 bg-slate-950/95 p-2 text-[10px] text-slate-200">
            <div className="mb-1 bg-cyan-400 px-1 py-0.5 text-center font-black text-black">AMD PANEL</div>
            <div className="flex justify-between border-b border-slate-700 py-1"><span>Skor</span><b>{amd?.score.toFixed(1) ?? "0.0"}</b></div>
            <div className="flex justify-between border-b border-slate-700 py-1"><span>Sweep</span><b>{amd?.sweep?.direction ?? "-"}</b></div>
            <div className="flex justify-between border-b border-slate-700 py-1"><span>CISD</span><b>{amd?.cisd?.confirmed ? "Onaylı" : "Bekliyor"}</b></div>
            <div className="flex justify-between border-b border-slate-700 py-1"><span>HTF Sweep</span><b>{amd?.htf_sweep?.direction ?? "-"}</b></div>
            <div className="pt-2 leading-4 text-slate-300">{amd?.summary ?? "AMD verisi yok."}</div>
          </div>
        </foreignObject>
      </svg>
    </div>
  );
}
