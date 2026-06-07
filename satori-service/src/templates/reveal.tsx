// Reveal scene template — 6 s, 180 frames.
// Props:
//   name: string
//   tier: Tier
//   series: Array<{year: number, count: number}>
//   chart_draw_progress: number 0–1 — how far the line is drawn (0.0–4.0s)
//   chart_alpha: number 0–1 — fade-in of the entire chart area (0.0–0.4s)
//   tracer_glow_alpha: number 0–1 — pulse opacity around the moving tracer
//   tracer_glow_radius: number px — pulse radius around the moving tracer
//   dot_visible: boolean — crimson dot at current year
//   dot_alpha: number 0–1 — landing opacity for the current-year dot
//   dot_radius: number px — landing radius, overshoots then settles
//   dot_ring_alpha: number 0–1 — expanding ring after the dot lands
//   dot_ring_radius: number px — expanding ring after the dot lands
//   count_value: number — animated count displayed below dot
//   count_alpha: number 0–1 — fade-in for the numeric readout
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
  chart_alpha: number;
  tracer_glow_alpha: number;
  tracer_glow_radius: number;
  dot_visible: boolean;
  dot_alpha: number;
  dot_radius: number;
  dot_ring_alpha: number;
  dot_ring_radius: number;
  count_value: number;
  count_alpha: number;
  current_year: number;
  peak_year: number;
  peak_count: number;
  debug_safe?: boolean;
}

const CHART_W = CANVAS.w - CANVAS.safe.x * 2;
const CHART_H = 600;
const LINE_WEIGHT = 3;
const TRACER_R = 5;

export default function Reveal(props: RevealProps) {
  const {
    name,
    tier,
    series,
    chart_draw_progress,
    chart_alpha,
    tracer_glow_alpha,
    tracer_glow_radius,
    dot_visible,
    dot_alpha,
    dot_radius,
    dot_ring_alpha,
    dot_ring_radius,
    count_value,
    count_alpha,
    current_year,
    peak_year,
    peak_count,
    debug_safe = false,
  } = props;

  const filtered = series.filter((p) => p.count >= 0);
  if (filtered.length === 0) {
    return (
      <div
        style={{
          width: CANVAS.w,
          height: CANVAS.h,
          backgroundColor: COLORS.bg,
          display: "flex",
        }}
      />
    );
  }

  const minYear = filtered[0].year;
  const maxYear = filtered[filtered.length - 1].year;
  const maxCount = Math.max(...filtered.map((p) => p.count), 1);

  const toX = (year: number) =>
    Math.round(((year - minYear) / Math.max(maxYear - minYear, 1)) * CHART_W);
  const toY = (count: number) =>
    Math.round(CHART_H - (count / maxCount) * CHART_H);

  // Smooth line drawing: compute how many full segments + partial.
  const totalPoints = filtered.length;
  const progressPoints = chart_draw_progress * totalPoints;
  const fullSegments = Math.floor(progressPoints);
  const partialT = progressPoints - fullSegments; // 0–1 for the in-progress segment

  // Take all points needed: fullSegments complete + maybe the next one.
  const drawnPoints = filtered.slice(0, fullSegments + 2);

  let tracerX = toX(filtered[0].year);
  let tracerY = toY(filtered[0].count);

  // Build SVG path string for smooth continuous line.
  let pathD = "";
  if (drawnPoints.length > 0) {
    pathD = `M ${toX(drawnPoints[0].year)} ${toY(drawnPoints[0].count)}`;
    for (let i = 1; i < drawnPoints.length; i++) {
      const x1 = toX(drawnPoints[i - 1].year);
      const y1 = toY(drawnPoints[i - 1].count);
      const x2 = toX(drawnPoints[i].year);
      const y2 = toY(drawnPoints[i].count);
      const segIndex = i - 1;
      if (segIndex < fullSegments) {
        pathD += ` L ${x2} ${y2}`;
        tracerX = x2;
        tracerY = y2;
      } else if (segIndex === fullSegments && partialT > 0) {
        const ix = x1 + (x2 - x1) * partialT;
        const iy = y1 + (y2 - y1) * partialT;
        pathD += ` L ${ix} ${iy}`;
        tracerX = ix;
        tracerY = iy;
      }
    }
  }

  // If no progress yet, tracer sits at the first point.
  if (fullSegments === 0 && partialT === 0) {
    tracerX = toX(filtered[0].year);
    tracerY = toY(filtered[0].count);
  }

  // Crimson dot position (only after full draw completes).
  const dotPoint =
    filtered.find((p) => p.year === current_year) ??
    filtered[filtered.length - 1];
  const dotX = toX(dotPoint.year);
  const dotY = toY(dotPoint.count);

  // Y-axis labels.
  const midCount = Math.round(maxCount / 2);
  const midY = toY(midCount);

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
          <div
            style={{
              position: "absolute",
              top: 0,
              left: 0,
              width: CANVAS.w,
              height: CANVAS.safe.top,
              backgroundColor: "rgba(255,0,0,0.35)",
              display: "flex",
            }}
          />
          <div
            style={{
              position: "absolute",
              bottom: 0,
              left: 0,
              width: CANVAS.w,
              height: CANVAS.safe.bottom,
              backgroundColor: "rgba(255,0,0,0.35)",
              display: "flex",
            }}
          />
        </>
      )}

      {/* Header row — name + tier badge */}
      <div
        style={{
          display: "flex",
          flexDirection: "row",
          alignItems: "center",
          marginBottom: 32,
          width: "100%",
        }}
      >
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

      {/* Chart area — fades in as a group */}
      <div
        style={{
          position: "relative",
          width: CHART_W,
          height: CHART_H,
          opacity: chart_alpha,
          display: "flex",
        }}
      >
        {/* Y-axis: max count label (top-left) */}
        <div
          style={{
            position: "absolute",
            top: -18,
            left: -8,
            display: "flex",
          }}
        >
          <span
            style={{
              fontFamily: TYPE.body.family,
              fontSize: RAMP.body[4],
              color: COLORS.fade,
              fontVariantNumeric: "tabular-nums",
            }}
          >
            {maxCount.toLocaleString("en-US")}
          </span>
        </div>

        {/* Y-axis: midpoint label */}
        <div
          style={{
            position: "absolute",
            top: midY - 10,
            left: -8,
            display: "flex",
          }}
        >
          <span
            style={{
              fontFamily: TYPE.body.family,
              fontSize: RAMP.body[4],
              color: COLORS.fade,
              fontVariantNumeric: "tabular-nums",
            }}
          >
            {midCount.toLocaleString("en-US")}
          </span>
        </div>

        {/* Midpoint gridline (subtle) */}
        <div
          style={{
            position: "absolute",
            top: midY,
            left: 0,
            width: CHART_W,
            height: 1,
            backgroundColor: COLORS.rule,
            display: "flex",
          }}
        />

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

        {/* Chart line */}
        <svg
          width={CHART_W}
          height={CHART_H}
          viewBox={`0 0 ${CHART_W} ${CHART_H}`}
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            overflow: "visible",
          }}
        >
          <path
            d={pathD}
            fill="none"
            stroke={COLORS.ink}
            strokeWidth={LINE_WEIGHT}
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>

        {/* Tracer dot — leads the line draw */}
        {chart_draw_progress > 0 && chart_draw_progress < 1 && (
          <>
            <div
              style={{
                position: "absolute",
                left: tracerX - tracer_glow_radius,
                top: tracerY - tracer_glow_radius,
                width: tracer_glow_radius * 2,
                height: tracer_glow_radius * 2,
                borderRadius: tracer_glow_radius,
                backgroundColor: COLORS.ink,
                opacity: tracer_glow_alpha,
                display: "flex",
              }}
            />
            <div
              style={{
                position: "absolute",
                left: tracerX - TRACER_R,
                top: tracerY - TRACER_R,
                width: TRACER_R * 2,
                height: TRACER_R * 2,
                borderRadius: TRACER_R,
                backgroundColor: COLORS.ink,
                display: "flex",
              }}
            />
          </>
        )}

        {/* Crimson dot at current year — lands at t=4.0s */}
        {dot_visible && (
          <>
            {dot_ring_alpha > 0 && (
              <div
                style={{
                  position: "absolute",
                  left: dotX - dot_ring_radius,
                  top: dotY - dot_ring_radius,
                  width: dot_ring_radius * 2,
                  height: dot_ring_radius * 2,
                  borderRadius: dot_ring_radius,
                  border: `2px solid ${COLORS.crimson}`,
                  opacity: dot_ring_alpha,
                  display: "flex",
                }}
              />
            )}
            <div
              style={{
                position: "absolute",
                left: dotX - dot_radius,
                top: dotY - dot_radius,
                width: dot_radius * 2,
                height: dot_radius * 2,
                borderRadius: dot_radius,
                backgroundColor: COLORS.crimson,
                opacity: dot_alpha,
                display: "flex",
              }}
            />
          </>
        )}
      </div>

      {/* X-axis labels */}
      <div
        style={{
          display: "flex",
          flexDirection: "row",
          justifyContent: "space-between",
          width: CHART_W,
          marginTop: 16,
          opacity: chart_alpha,
        }}
      >
        <span
          style={{
            fontFamily: TYPE.body.family,
            fontSize: RAMP.body[4],
            color: COLORS.fade,
            fontVariantNumeric: "tabular-nums",
          }}
        >
          {minYear}
        </span>
        <span
          style={{
            fontFamily: TYPE.body.family,
            fontSize: RAMP.body[4],
            color: COLORS.fade,
            fontVariantNumeric: "tabular-nums",
          }}
        >
          {maxYear}
        </span>
      </div>

      {/* Count-up display — appears after dot lands */}
      {dot_visible && (
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            marginTop: 48,
            opacity: count_alpha,
          }}
        >
          <span
            style={{
              fontFamily: TYPE.display.family,
              fontWeight: TYPE.display.weight,
              fontSize: RAMP.display[1],
              color: COLORS.crimson,
              lineHeight: 1.05,
              fontVariantNumeric: "tabular-nums",
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
              fontVariantNumeric: "tabular-nums",
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
