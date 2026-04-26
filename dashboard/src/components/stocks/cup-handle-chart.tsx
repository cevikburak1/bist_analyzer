"use client";

import type { CupHandleQuality, StockDetailData } from "@/lib/types/report";

type Props = {
  detail: StockDetailData;
};

const WIDTH = 1180;
const HEIGHT = 620;
const LEFT = 56;
const RIGHT = 245;
const TOP = 38;
const BOTTOM = 560;

function n(value: number | null | undefined) {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function fmt(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  return new Intl.NumberFormat("tr-TR", {
    maximumFractionDigits: value >= 10 ? 2 : 3,
    minimumFractionDigits: value >= 10 ? 2 : 3,
  }).format(value);
}

function scale(min: number, max: number, top: number, bottom: number) {
  const span = max - min || 1;
  return (value: number) => bottom - ((value - min) / span) * (bottom - top);
}

function curvePath(points: Array<[number, number]>) {
  if (points.length === 0) return "";
  return points.map(([x, y], index) => `${index === 0 ? "M" : "L"}${x.toFixed(2)} ${y.toFixed(2)}`).join(" ");
}

function scoreColor(score: number | null | undefined) {
  if (score === null || score === undefined) return "text-slate-400";
  if (score >= 80) return "text-emerald-300";
  if (score >= 65) return "text-yellow-200";
  return "text-rose-300";
}

function PanelRow({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div className="grid grid-cols-[1fr_72px] border-b border-slate-700 last:border-b-0">
      <div className="px-2 py-1.5 text-[11px] text-slate-400">{label}</div>
      <div className={`px-2 py-1.5 text-right text-[11px] font-bold ${tone ?? "text-slate-100"}`}>{value}</div>
    </div>
  );
}

function buildCupCurve(
  cup: CupHandleQuality,
  xFromIndex: (index: number) => number,
  yFor: (value: number) => number,
) {
  const left = cup.points.left_rim;
  const base = cup.points.cup_base;
  const right = cup.points.right_rim;
  if (!left || !base || !right || cup.rim_price === null || cup.rim_price === undefined) return "";
  const points: Array<[number, number]> = [];
  const steps = 28;
  const cupStart = left.index;
  const cupWidth = Math.max(right.index - left.index, 1);
  const bottom = base.price;
  const rim = cup.rim_price;
  for (let step = 0; step <= steps; step += 1) {
    const t = step / steps;
    const x = xFromIndex(cupStart + cupWidth * t);
    const curve = Math.abs(2 * t - 1) ** 2;
    const y = yFor(bottom + (rim - bottom) * curve);
    points.push([x, y]);
  }
  return curvePath(points);
}

function buildHandleCurve(
  cup: CupHandleQuality,
  xFromIndex: (index: number) => number,
  yFor: (value: number) => number,
) {
  const right = cup.points.right_rim;
  const handle = cup.points.handle_low;
  if (!right || !handle || cup.rim_price === null || cup.rim_price === undefined) return "";
  const points: Array<[number, number]> = [];
  const steps = 14;
  const width = Math.max(handle.index - right.index, 4);
  const low = handle.price;
  const rim = cup.rim_price;
  for (let step = 0; step <= steps; step += 1) {
    const t = step / steps;
    const x = xFromIndex(right.index + width * t);
    const depthShape = t <= 0.5 ? (1 - t * 2) ** 2 : ((t - 0.5) * 2) ** 0.75 * 0.72;
    const y = yFor(low + (rim - low) * depthShape);
    points.push([x, y]);
  }
  return curvePath(points);
}

export function CupHandleChart({ detail }: Props) {
  const series = detail.series;
  const visible = series.slice(-160);
  const cup = detail.signal.cup_handle_quality;
  const startIndex = Math.max(0, series.length - visible.length);
  const priceValues = visible.flatMap((point) => [point.high, point.low]).filter((value): value is number => n(value) !== null);
  if (cup?.target_price) priceValues.push(cup.target_price);
  if (cup?.rim_price) priceValues.push(cup.rim_price);
  const min = Math.min(...priceValues);
  const max = Math.max(...priceValues);
  const pad = Math.max((max - min) * 0.12, 0.01);
  const yFor = scale(min - pad, max + pad, TOP, BOTTOM);
  const xForVisible = (index: number) => LEFT + (index / Math.max(visible.length - 1, 1)) * (WIDTH - LEFT - RIGHT);
  const xFromGlobalIndex = (globalIndex: number) => xForVisible(globalIndex - startIndex);
  const candleWidth = Math.max(3, Math.min(8, (WIDTH - LEFT - RIGHT) / Math.max(visible.length, 1) * 0.52));
  const ticks = Array.from({ length: 6 }, (_, index) => min + ((max - min) / 5) * index);
  const hasCup = !!cup?.is_detected && !!cup.points.left_rim && !!cup.points.cup_base && !!cup.points.right_rim && !!cup.points.handle_low;

  return (
    <div className="overflow-hidden rounded-[10px] border border-slate-800 bg-black shadow-2xl shadow-black/60">
      <div className="flex items-center justify-between border-b border-slate-900 bg-black px-4 py-2">
        <div>
          <div className="text-sm font-bold text-slate-100">{detail.signal.symbol} · Cup and Handle Quality</div>
          <div className="text-[10px] text-slate-500">Rim recovery · controlled handle depth · breakout participation · measured projection</div>
        </div>
        <div className="text-right text-xs text-slate-500">
          <div>Status: <span className={cup?.is_confirmed ? "text-emerald-300" : "text-yellow-200"}>{cup?.status ?? "NONE"}</span></div>
          <div>Score: <span className={scoreColor(cup?.score)}>{cup?.score ?? "-"}</span></div>
        </div>
      </div>

      <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} className="block h-[620px] w-full bg-black">
        <rect width={WIDTH} height={HEIGHT} fill="#000" />
        {ticks.map((tick) => {
          const y = yFor(tick);
          return (
            <g key={tick}>
              <line x1={LEFT} x2={WIDTH - RIGHT + 32} y1={y} y2={y} stroke="#111827" strokeDasharray="4 8" />
              <text x={WIDTH - RIGHT + 40} y={y + 4} fill="#60a5fa" fontSize="10">{fmt(tick)}</text>
            </g>
          );
        })}

        {visible.map((point, index) => {
          const open = n(point.open);
          const close = n(point.close);
          const high = n(point.high);
          const low = n(point.low);
          if (open === null || close === null || high === null || low === null) return null;
          const x = xForVisible(index);
          const up = close >= open;
          const color = up ? "#22c5a6" : "#f472b6";
          const top = yFor(Math.max(open, close));
          const bottom = yFor(Math.min(open, close));
          return (
            <g key={point.date}>
              <line x1={x} x2={x} y1={yFor(high)} y2={yFor(low)} stroke={color} strokeWidth="1.1" />
              <rect x={x - candleWidth / 2} y={top} width={candleWidth} height={Math.max(2, bottom - top)} fill={color} rx="1" />
            </g>
          );
        })}

        {hasCup && cup ? (
          <>
            <rect
              x={xFromGlobalIndex(cup.points.left_rim!.index)}
              y={yFor(Math.max(cup.points.left_rim!.price, cup.points.right_rim!.price))}
              width={Math.max(8, xFromGlobalIndex(cup.points.right_rim!.index) - xFromGlobalIndex(cup.points.left_rim!.index))}
              height={Math.max(8, yFor(cup.points.cup_base!.price) - yFor(Math.max(cup.points.left_rim!.price, cup.points.right_rim!.price)))}
              fill="#818cf8"
              opacity="0.07"
              stroke="#818cf8"
              strokeOpacity="0.35"
            />
            <rect
              x={xFromGlobalIndex(cup.points.right_rim!.index)}
              y={yFor(cup.rim_price ?? cup.points.right_rim!.price)}
              width={Math.max(8, xFromGlobalIndex(cup.points.handle_low!.index) - xFromGlobalIndex(cup.points.right_rim!.index) + 34)}
              height={Math.max(8, yFor(cup.points.handle_low!.price) - yFor(cup.rim_price ?? cup.points.right_rim!.price))}
              fill="#f5bd5c"
              opacity="0.1"
              stroke="#f5bd5c"
              strokeOpacity="0.45"
            />
            <path d={buildCupCurve(cup, xFromGlobalIndex, yFor)} fill="none" stroke="#818cf8" strokeWidth="5" strokeLinecap="round" />
            <path d={buildHandleCurve(cup, xFromGlobalIndex, yFor)} fill="none" stroke="#f5bd5c" strokeWidth="5" strokeLinecap="round" />
            {cup.rim_price ? <line x1={xFromGlobalIndex(cup.points.left_rim!.index)} x2={WIDTH - RIGHT + 32} y1={yFor(cup.rim_price)} y2={yFor(cup.rim_price)} stroke="#818cf8" strokeWidth="3" /> : null}
            {cup.target_price ? <line x1={xFromGlobalIndex(cup.points.handle_low!.index)} x2={WIDTH - RIGHT + 32} y1={yFor(cup.target_price)} y2={yFor(cup.target_price)} stroke="#22c5a6" strokeWidth="5" opacity="0.85" /> : null}
            {cup.rim_price && cup.cup_depth ? (
              <>
                <line x1={xFromGlobalIndex(cup.points.cup_base!.index)} x2={xFromGlobalIndex(cup.points.cup_base!.index)} y1={yFor(cup.points.cup_base!.price)} y2={yFor(cup.rim_price)} stroke="#a78bfa" strokeWidth="3" markerStart="url(#none)" />
                <text x={xFromGlobalIndex(cup.points.cup_base!.index) + 6} y={(yFor(cup.points.cup_base!.price) + yFor(cup.rim_price)) / 2} fill="#a78bfa" fontSize="11">DEPTH</text>
                <line x1={xFromGlobalIndex(cup.points.handle_low!.index) + 42} x2={xFromGlobalIndex(cup.points.handle_low!.index) + 42} y1={yFor(cup.rim_price)} y2={yFor(cup.target_price ?? cup.rim_price)} stroke="#2dd4bf" strokeWidth="3" />
                <text x={xFromGlobalIndex(cup.points.handle_low!.index) + 48} y={(yFor(cup.rim_price) + yFor(cup.target_price ?? cup.rim_price)) / 2} fill="#2dd4bf" fontSize="11">MOVE</text>
              </>
            ) : null}
            <text x={xFromGlobalIndex(cup.points.cup_base!.index) - 12} y={yFor(cup.points.cup_base!.price) + 24} fill="#f8fafc" fontSize="12" fontWeight="700">CUP</text>
            <text x={xFromGlobalIndex(cup.points.handle_low!.index) - 18} y={yFor(cup.points.handle_low!.price) - 12} fill="#0f172a" fontSize="12" fontWeight="700">HANDLE</text>
          </>
        ) : null}

        <foreignObject x={WIDTH - RIGHT + 20} y={TOP + 10} width={215} height={174}>
          <div className="overflow-hidden rounded border border-slate-700 bg-slate-900 text-[11px]">
            <div className="bg-blue-600 px-2 py-1 text-center font-bold text-slate-50">AG Pro Cup and Handle Quality</div>
            <PanelRow label="Cup Symmetry" value={cup?.cup_symmetry?.toFixed(0) ?? "Waiting"} tone={scoreColor(cup?.cup_symmetry)} />
            <PanelRow label="Handle Depth" value={cup?.handle_depth_pct !== null && cup?.handle_depth_pct !== undefined ? `${cup.handle_depth_pct.toFixed(1)}%` : "Waiting"} />
            <PanelRow label="Breakout Quality" value={cup?.breakout_quality?.toFixed(0) ?? "Waiting"} tone={scoreColor(cup?.breakout_quality)} />
            <PanelRow label="Score" value={cup?.score?.toFixed(0) ?? "Waiting"} tone={scoreColor(cup?.score)} />
          </div>
        </foreignObject>
      </svg>
    </div>
  );
}
