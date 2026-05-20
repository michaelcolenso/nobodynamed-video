// Reveal scene template — 6 s, 180 frames.
// Props:
//   name: string
//   tier: Tier
//   series: Array<{year: number, count: number}>
//   chart_draw_progress: number 0–1 — how far the line is drawn
//   dot_visible: boolean — crimson dot at current year
//   count_value: number — animated count displayed below dot
//   current_year: number
//   peak_year: number
//   peak_count: number
//   debug_safe?: boolean

import { CANVAS, COLORS, RAMP, TYPE, Tier, TierBadge } from "./shared";

export interface RevealProps {
  name: string;
  tier: Tier;
  series: Array<{ year: number; count: number }>;
  chart_draw_progress: number;
  dot_visible: boolean;
  count_value: number;
  current_year: number;
  peak_year: number;
  peak_count: number;
  debug_safe?: boolean;
}

const CHART_W = CANVAS.w - CANVAS.safe.x * 2;
const CHART_H = 600;

export default function Reveal(props: RevealProps) {
  const {
    name,
    tier,
    series,
    chart_draw_progress,
    dot_visible,
    count_value,
    current_year,
    peak_year,
    peak_count,
    debug_safe = false,
  } = props;

  // Only draw years with count >= 0 for the x-axis.
  const filtered = series.filter((p) => p.count >= 0);
  if (filtered.length === 0) {
    return <div style={{ width: CANVAS.w, height: CANVAS.h, backgroundColor: COLORS.bg, display: "flex" }} />;
  }

  const minYear = filtered[0].year;
  const maxYear = filtered[filtered.length - 1].year;
  const maxCount = Math.max(...filtered.map((p) => p.count), 1);

  const toX = (year: number) =>
    Math.round(((year - minYear) / Math.max(maxYear - minYear, 1)) * CHART_W);
  const toY = (count: number) =>
    Math.round(CHART_H - (count / maxCount) * CHART_H);

  // How many points to draw based on progress.
  const totalPoints = filtered.length;
  const visibleCount = Math.max(1, Math.round(chart_draw_progress * totalPoints));
  const visible = filtered.slice(0, visibleCount);

  // Build a simple polyline as a series of absolute-positioned rectangles
  // (Satori doesn't support SVG, so we approximate with line segments).
  const segments: Array<{ x: number; y: number; w: number; h: number; angle: number }> = [];
  for (let i = 1; i < visible.length; i++) {
    const x1 = toX(visible[i - 1].year);
    const y1 = toY(visible[i - 1].count);
    const x2 = toX(visible[i].year);
    const y2 = toY(visible[i].count);
    segments.push({ x: x1, y: y1, w: x2 - x1, h: y2 - y1, angle: 0 });
  }

  // Crimson dot position.
  const dotPoint = filtered.find((p) => p.year === current_year) ?? filtered[filtered.length - 1];
  const dotX = toX(dotPoint.year);
  const dotY = toY(dotPoint.count);

  return (
    <div
      style={{
        width: CANVAS.w,
        height: CANVAS.h,
        backgroundColor: COLORS.bg,
        display: "flex",
        flexDirection: "column",
        justifyContent: "flex-start",
        alignItems: "flex-start",
        paddingTop: CANVAS.safe.top,
        paddingBottom: CANVAS.safe.bottom,
        paddingLeft: CANVAS.safe.x,
        paddingRight: CANVAS.safe.x,
        position: "relative",
      }}
    >
      {debug_safe && (
        <>
          <div style={{ position: "absolute", top: 0, left: 0, width: CANVAS.w, height: CANVAS.safe.top, backgroundColor: "rgba(255,0,0,0.35)", display: "flex" }} />
          <div style={{ position: "absolute", bottom: 0, left: 0, width: CANVAS.w, height: CANVAS.safe.bottom, backgroundColor: "rgba(255,0,0,0.35)", display: "flex" }} />
        </>
      )}

      {/* Header row */}
      <div style={{ display: "flex", flexDirection: "row", alignItems: "center", marginBottom: 32, width: "100%" }}>
        <div
          style={{
            fontFamily: TYPE.display.family,
            fontWeight: TYPE.display.weight,
            fontSize: RAMP.display[2],
            color: COLORS.ink,
            flex: 1,
            display: "flex",
          }}
        >
          {name}
        </div>
        <TierBadge tier={tier} />
      </div>

      {/* Chart area */}
      <div
        style={{
          position: "relative",
          width: CHART_W,
          height: CHART_H,
          display: "flex",
        }}
      >
        {/* Axis baseline */}
        <div
          style={{
            position: "absolute",
            bottom: 0,
            left: 0,
            width: CHART_W,
            height: 2,
            backgroundColor: COLORS.rule,
            display: "flex",
          }}
        />

        {/* Chart line segments — rendered as thin rectangles */}
        {segments.map((seg, i) => {
          const length = Math.sqrt(seg.w * seg.w + seg.h * seg.h);
          const angle = Math.atan2(seg.h, seg.w) * (180 / Math.PI);
          return (
            <div
              key={i}
              style={{
                position: "absolute",
                left: seg.x,
                top: seg.y,
                width: Math.max(length, 1),
                height: 3,
                backgroundColor: COLORS.ink,
                transformOrigin: "0 50%",
                transform: `rotate(${angle}deg)`,
                display: "flex",
              }}
            />
          );
        })}

        {/* Crimson dot at current year */}
        {dot_visible && (
          <div
            style={{
              position: "absolute",
              left: dotX - 12,
              top: dotY - 12,
              width: 24,
              height: 24,
              borderRadius: 12,
              backgroundColor: COLORS.crimson,
              display: "flex",
            }}
          />
        )}
      </div>

      {/* Axis labels */}
      <div
        style={{
          display: "flex",
          flexDirection: "row",
          justifyContent: "space-between",
          width: CHART_W,
          marginTop: 16,
        }}
      >
        <span style={{ fontFamily: TYPE.body.family, fontSize: RAMP.body[4], color: COLORS.fade }}>
          {minYear}
        </span>
        <span style={{ fontFamily: TYPE.body.family, fontSize: RAMP.body[4], color: COLORS.fade }}>
          {maxYear}
        </span>
      </div>

      {/* Count-up display */}
      {dot_visible && (
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            marginTop: 48,
          }}
        >
          <span
            style={{
              fontFamily: TYPE.display.family,
              fontWeight: TYPE.display.weight,
              fontSize: RAMP.display[1],
              color: COLORS.crimson,
              display: "flex",
            }}
          >
            {count_value.toLocaleString("en-US")}
          </span>
          <span
            style={{
              fontFamily: TYPE.body.family,
              fontSize: RAMP.body[2],
              color: COLORS.fade,
              marginTop: 8,
              display: "flex",
            }}
          >
            babies named {name} in {current_year}
          </span>
        </div>
      )}
    </div>
  );
}
