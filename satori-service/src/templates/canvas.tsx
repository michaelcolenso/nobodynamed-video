import { CANVAS, COLORS, RAMP, TYPE, Tier, TierBadge } from "./shared";

interface HeaderState {
  alpha: number;
  label: string;
  name: string;
  status: string;
}

interface DiagnosisState {
  alpha: number;
  headline: string;
  subhead: string;
}

interface ChartState {
  alpha: number;
  draw_progress: number;
  tracer_glow_alpha: number;
  tracer_glow_radius: number;
  dot_visible: boolean;
  dot_alpha: number;
  dot_radius: number;
  dot_ring_alpha: number;
  dot_ring_radius: number;
  layout_progress: number;
  event_alpha: number;
  event_year?: number | null;
  event_label?: string | null;
  series: Array<{ year: number; count: number }>;
  current_year: number;
  peak_year: number;
  peak_count: number;
  count_value: number;
}

interface StatsState {
  alpha: number;
  cards: Array<{ label: string; value: string; tone: string }>;
  card_alphas: number[];
}

interface NarrativeState {
  alpha: number;
  support_alpha: number;
  text: string;
  supporting_text?: string | null;
}

interface ComparisonState {
  alpha: number;
  label: string;
  name?: string | null;
}

interface FooterState {
  alpha: number;
  site: string;
  cta: string;
  dot_alpha?: number;
}

export interface CanvasProps {
  program: string;
  register: string;
  tier: Tier;
  header: HeaderState;
  diagnosis: DiagnosisState;
  chart: ChartState;
  stats: StatsState;
  narrative: NarrativeState;
  comparison: ComparisonState;
  footer: FooterState;
  debug_safe?: boolean;
}

function mix(a: number, b: number, progress: number) {
  return a + (b - a) * progress;
}

function smoothCurveParts(pts: Array<[number, number]>): string {
  let d = "";
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[Math.max(0, i - 1)];
    const p1 = pts[i];
    const p2 = pts[i + 1];
    const p3 = pts[Math.min(pts.length - 1, i + 2)];
    const cp1x = p1[0] + (p2[0] - p0[0]) / 6;
    const cp1y = p1[1] + (p2[1] - p0[1]) / 6;
    const cp2x = p2[0] - (p3[0] - p1[0]) / 6;
    const cp2y = p2[1] - (p3[1] - p1[1]) / 6;
    d += ` C ${cp1x} ${cp1y}, ${cp2x} ${cp2y}, ${p2[0]} ${p2[1]}`;
  }
  return d;
}

function StatCard({ label, value, tone }: { label: string; value: string; tone: string }) {
  const valueColor = tone === "crimson" ? COLORS.crimson : tone === "emerald" ? COLORS.emerald : COLORS.ink;
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        paddingTop: 22,
        paddingBottom: 22,
        paddingLeft: 24,
        paddingRight: 24,
        borderWidth: 1,
        borderStyle: "solid",
        borderColor: COLORS.rule,
        backgroundColor: "#191613",
        width: 286,
      }}
    >
      <div
        style={{
          fontFamily: TYPE.body.family,
          fontSize: RAMP.body[4],
          color: COLORS.fade,
          letterSpacing: 2,
          textTransform: "uppercase",
          fontVariantNumeric: "tabular-nums",
          display: "flex",
        }}
      >
        {label}
      </div>
      <div
        style={{
          fontFamily: TYPE.display.family,
          fontWeight: TYPE.display.weight,
          fontSize: RAMP.body[1],
          color: valueColor,
          marginTop: 10,
          lineHeight: 1.15,
          fontVariantNumeric: "tabular-nums",
          display: "flex",
        }}
      >
        {value}
      </div>
    </div>
  );
}

function smoothPathD(
  points: Array<{ x: number; y: number }>,
  drawProgress: number,
): { pathD: string; tracerX: number; tracerY: number } {
  if (points.length === 0) return { pathD: "", tracerX: 0, tracerY: 0 };
  if (points.length === 1) return { pathD: `M ${points[0].x} ${points[0].y}`, tracerX: points[0].x, tracerY: points[0].y };

  // Standard Catmull-Rom → cubic bezier conversion.
  // For segment i→i+1, control points are:
  //   cp1 = Pi + (Pi+1 - Pi-1) / 6
  //   cp2 = Pi+1 - (Pi+2 - Pi) / 6
  // Edge segments mirror the previous/next point.

  const totalSegments = points.length - 1;
  const fullSegments = Math.min(Math.floor(drawProgress * totalSegments), totalSegments);
  const partialT = drawProgress * totalSegments - fullSegments;

  let pathD = "";
  let tracerX = points[0].x;
  let tracerY = points[0].y;

  const cp = (i: number, isEnd: boolean): { x: number; y: number } => {
    const pi = points[i];
    const pj = points[isEnd ? i + 1 : i - 1];
    const dx = (pj.x - pi.x) / 6;
    const dy = (pj.y - pi.y) / 6;
    return { x: pi.x + dx, y: pi.y + dy };
  };

  for (let seg = 0; seg < fullSegments; seg++) {
    const p0 = points[Math.max(0, seg - 1)];
    const p1 = points[seg];
    const p2 = points[seg + 1];
    const p3 = points[Math.min(points.length - 1, seg + 2)];

    const cp1 = { x: p1.x + (p2.x - p0.x) / 6, y: p1.y + (p2.y - p0.y) / 6 };
    const cp2 = { x: p2.x - (p3.x - p1.x) / 6, y: p2.y - (p3.y - p1.y) / 6 };

    const cmd = seg === 0 ? `M ${p1.x} ${p1.y} C ${cp1.x} ${cp1.y}, ${cp2.x} ${cp2.y}, ${p2.x} ${p2.y}` : ` C ${cp1.x} ${cp1.y}, ${cp2.x} ${cp2.y}, ${p2.x} ${p2.y}`;
    pathD += cmd;
    tracerX = p2.x;
    tracerY = p2.y;
  }

  // Partial segment — use De Casteljau to split the bezier at partialT
  if (fullSegments < totalSegments && partialT > 0) {
    const seg = fullSegments;
    const p0 = points[Math.max(0, seg - 1)];
    const p1 = points[seg];
    const p2 = points[seg + 1];
    const p3 = points[Math.min(points.length - 1, seg + 2)];

    const cp1 = { x: p1.x + (p2.x - p0.x) / 6, y: p1.y + (p2.y - p0.y) / 6 };
    const cp2 = { x: p2.x - (p3.x - p1.x) / 6, y: p2.y - (p3.y - p1.y) / 6 };

    // De Casteljau at partialT — first cubic segment
    const q0 = mix(p1.x, cp1.x, partialT); const r0 = mix(p1.y, cp1.y, partialT);
    const q1 = mix(cp1.x, cp2.x, partialT); const r1 = mix(cp1.y, cp2.y, partialT);
    const q2 = mix(cp2.x, p2.x, partialT); const r2 = mix(cp2.y, p2.y, partialT);
    const s0 = mix(q0, q1, partialT); const t0 = mix(r0, r1, partialT);
    const s1 = mix(q1, q2, partialT); const t1 = mix(r1, r2, partialT);
    const endX = mix(s0, s1, partialT); const endY = mix(t0, t1, partialT);

    const cmd = seg === 0
      ? `M ${p1.x} ${p1.y} C ${q0} ${r0}, ${s0} ${t0}, ${endX} ${endY}`
      : ` C ${q0} ${r0}, ${s0} ${t0}, ${endX} ${endY}`;
    pathD += cmd;
    tracerX = endX;
    tracerY = endY;
  }

  return { pathD, tracerX, tracerY };
}


function formatYLabel(val: number): string {
  if (val >= 1000000) {
    return parseFloat((val / 1000000).toFixed(1)) + "M";
  }
  if (val >= 1000) {
    return parseFloat((val / 1000).toFixed(1)) + "K";
  }
  return Math.round(val).toString();
}

function AxisLabel({ top, text }: { top: number; text: string }) {
  return (
    <div
      style={{
        position: "absolute",
        left: 12,
        top: top,
        fontFamily: TYPE.body.family,
        fontSize: RAMP.body[4],
        color: COLORS.fade,
        opacity: 0.5,
        fontVariantNumeric: "tabular-nums",
        display: "flex",
      }}
    >
      {text}
    </div>
  );
}

export default function Canvas(props: CanvasProps) {
  const { tier, header, diagnosis, chart, stats, narrative, comparison, footer, debug_safe = false } = props;

  const filtered = chart.series.filter((point) => point.count >= 0);
  const minYear = filtered[0]?.year ?? chart.current_year;
  const maxYear = filtered[filtered.length - 1]?.year ?? chart.current_year;
  const maxCount = Math.max(...filtered.map((point) => point.count), 1);

  const chartLeft = CANVAS.safe.x;
  // Keep the chart top fixed at 560 across the recompose: the top y-axis label sits at
  // top:-26 (y≈534), which clears the diagnosis subhead (ends ~489). Collapsing toward 470
  // pushed the "5K" label and curve peak up into the "N born last year." subhead. Instead,
  // grow the chart *downward* on recompose (taller collapsed height) so it anchors the
  // middle of the canvas; the stats/narrative blocks below are pushed down to match, which
  // distributes content over the full height instead of leaving a void above the footer.
  const chartTop = 560;
  const chartWidth = mix(CANVAS.w - CANVAS.safe.x * 2, 920, chart.layout_progress);
  const chartHeight = mix(760, 450, chart.layout_progress);

  const toX = (year: number) => ((year - minYear) / Math.max(maxYear - minYear, 1)) * chartWidth;
  const toY = (count: number) => chartHeight - (count / maxCount) * chartHeight;

  const curvePoints = filtered.map((p) => ({ x: toX(p.year), y: toY(p.count) }));
  const { pathD, tracerX, tracerY } = smoothPathD(curvePoints, chart.draw_progress);

  // Area fill — closes the path with a clean line to baseline, then smooth bezier back.
  const pathAreaD = pathD
    ? `M ${curvePoints[0]?.x ?? 0} ${chartHeight} ${pathD.replace(/^M /, "L ")} L ${tracerX} ${chartHeight} Z`
    : "";

  const currentPoint = filtered.find((point) => point.year === chart.current_year) ?? filtered[filtered.length - 1];
  const dotX = toX(currentPoint?.year ?? chart.current_year);
  const dotY = toY(currentPoint?.count ?? 0);
  const eventX = chart.event_year != null ? toX(Math.max(minYear, Math.min(maxYear, chart.event_year))) : 0;

  const narrativeTop = mix(1250, 1340, chart.layout_progress);
  const comparisonTop = mix(1640, 1420, chart.layout_progress);
  const dotColor =
    tier === "rising" || tier === "resurrected" ? COLORS.emerald : COLORS.crimson;
  const peakX = toX(chart.peak_year);

  return (
    <div
      style={{
        width: CANVAS.w,
        height: CANVAS.h,
        backgroundColor: COLORS.bg,
        position: "relative",
        display: "flex",
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

      <div
        style={{
          position: "absolute",
          top: 118,
          left: CANVAS.safe.x,
          opacity: header.alpha,
          display: "flex",
          flexDirection: "column",
          width: CANVAS.w - CANVAS.safe.x * 2,
        }}
      >
        <div
          style={{
            fontFamily: TYPE.body.family,
            fontSize: RAMP.body[4],
            color: COLORS.fade,
            letterSpacing: 2,
            textTransform: "uppercase",
            display: "flex",
          }}
        >
          {header.label}
        </div>
        <div
          style={{
            display: "flex",
            flexDirection: "row",
            alignItems: "center",
            justifyContent: "space-between",
            marginTop: 18,
          }}
        >
          <div
            style={{
              fontFamily: TYPE.display.family,
              fontWeight: TYPE.display.weight,
              fontSize: RAMP.display[1],
              color: COLORS.ink,
              display: "flex",
            }}
          >
            {header.name}
          </div>
          <TierBadge tier={tier} />
        </div>
      </div>

      <div
        style={{
          position: "absolute",
          top: 330,
          left: CANVAS.safe.x,
          opacity: diagnosis.alpha,
          display: "flex",
          flexDirection: "column",
          width: CANVAS.w - CANVAS.safe.x * 2,
        }}
      >
        <div
          style={{
            fontFamily: TYPE.display.family,
            fontWeight: TYPE.display.weight,
            fontSize: RAMP.body[0],
            color: COLORS.ink,
            lineHeight: 1.08,
            fontVariantNumeric: "tabular-nums",
            display: "flex",
          }}
        >
          {diagnosis.headline}
        </div>
        <div
          style={{
            fontFamily: TYPE.body.family,
            fontSize: RAMP.body[3],
            color: COLORS.fade,
            lineHeight: 1.5,
            marginTop: 22,
            fontVariantNumeric: "tabular-nums",
            display: "flex",
          }}
        >
          {diagnosis.subhead}
        </div>
      </div>

      <div
        style={{
          position: "absolute",
          top: chartTop,
          left: chartLeft,
          width: chartWidth,
          height: chartHeight,
          opacity: chart.alpha,
          display: "flex",
        }}
      >
        {/* Horizontal solid rule at the bottom x-axis */}
        <div
          style={{
            position: "absolute",
            bottom: 0,
            left: 0,
            width: chartWidth,
            height: 2,
            backgroundColor: COLORS.rule,
            display: "flex",
          }}
        />

        {/* Y-axis labels */}
        <AxisLabel top={-26} text={formatYLabel(maxCount)} />
        <AxisLabel top={chartHeight * 0.25 - 26} text={formatYLabel(maxCount * 0.75)} />
        <AxisLabel top={chartHeight * 0.5 - 26} text={formatYLabel(maxCount * 0.5)} />
        <AxisLabel top={chartHeight * 0.75 - 26} text={formatYLabel(maxCount * 0.25)} />
        <AxisLabel top={chartHeight - 26} text="0" />

        {/* X-axis year labels */}
        <div
          style={{
            position: "absolute",
            left: 0,
            top: chartHeight + 8,
            fontFamily: TYPE.body.family,
            fontSize: 18,
            color: COLORS.fade,
            opacity: 0.5,
            display: "flex",
          }}
        >
          {String(minYear)}
        </div>
        {peakX > 60 && peakX < chartWidth - 60 && (
          <div
            style={{
              position: "absolute",
              left: peakX - 16,
              top: chartHeight + 8,
              fontFamily: TYPE.body.family,
              fontSize: 18,
              color: COLORS.fade,
              opacity: 0.5,
              display: "flex",
            }}
          >
            {String(chart.peak_year)}
          </div>
        )}
        <div
          style={{
            position: "absolute",
            right: 0,
            top: chartHeight + 8,
            fontFamily: TYPE.body.family,
            fontSize: 18,
            color: COLORS.fade,
            opacity: 0.5,
            display: "flex",
          }}
        >
          {String(maxYear)}
        </div>

        {chart.event_alpha > 0 && chart.event_year != null && chart.event_label && (
          <>
            <div
              style={{
                position: "absolute",
                left: eventX,
                top: 0,
                width: 1,
                height: chartHeight,
                backgroundColor: COLORS.crimson,
                opacity: chart.event_alpha,
                display: "flex",
              }}
            />
            <div
              style={{
                position: "absolute",
                left: Math.max(0, eventX - 80),
                top: -42,
                backgroundColor: COLORS.crimson,
                color: COLORS.ink,
                opacity: chart.event_alpha,
                paddingTop: 8,
                paddingBottom: 8,
                paddingLeft: 14,
                paddingRight: 14,
                display: "flex",
              }}
            >
              <span
                style={{
                  fontFamily: TYPE.body.family,
                  fontSize: RAMP.body[4],
                  fontVariantNumeric: "tabular-nums",
                  display: "flex",
                }}
              >
                {chart.event_label}
              </span>
            </div>
          </>
        )}

        <svg
          width={chartWidth}
          height={chartHeight}
          viewBox={`0 0 ${chartWidth} ${chartHeight}`}
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            overflow: "visible",
          }}
        >
          <defs>
            <linearGradient id="chartAreaGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={COLORS.ink} stopOpacity={0.3} />
              <stop offset="70%" stopColor={COLORS.ink} stopOpacity={0.05} />
              <stop offset="100%" stopColor={COLORS.crimson} stopOpacity={0.1} />
            </linearGradient>
          </defs>

          {/* Grid lines */}
          <line
            x1={0}
            y1={chartHeight * 0.25}
            x2={chartWidth}
            y2={chartHeight * 0.25}
            stroke={COLORS.rule}
            strokeWidth={1}
            strokeDasharray="4 4"
          />
          <line
            x1={0}
            y1={chartHeight * 0.5}
            x2={chartWidth}
            y2={chartHeight * 0.5}
            stroke={COLORS.rule}
            strokeWidth={1}
            strokeDasharray="4 4"
          />
          <line
            x1={0}
            y1={chartHeight * 0.75}
            x2={chartWidth}
            y2={chartHeight * 0.75}
            stroke={COLORS.rule}
            strokeWidth={1}
            strokeDasharray="4 4"
          />
          <line
            x1={0}
            y1={0}
            x2={chartWidth}
            y2={0}
            stroke={COLORS.rule}
            strokeWidth={1}
            strokeDasharray="4 4"
          />

          {/* Fading gradient area under the chart line */}
          {pathAreaD && (
            <path
              d={pathAreaD}
              fill="url(#chartAreaGrad)"
            />
          )}

          {/* Chart line */}
          <path
            d={pathD}
            fill="none"
            stroke={COLORS.ink}
            strokeWidth={3}
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>

        {chart.draw_progress > 0 && chart.draw_progress < 1 && (
          <>
            <div
              style={{
                position: "absolute",
                left: tracerX - chart.tracer_glow_radius,
                top: tracerY - chart.tracer_glow_radius,
                width: chart.tracer_glow_radius * 2,
                height: chart.tracer_glow_radius * 2,
                borderRadius: chart.tracer_glow_radius,
                backgroundColor: COLORS.ink,
                opacity: chart.tracer_glow_alpha,
                display: "flex",
              }}
            />
            <div
              style={{
                position: "absolute",
                left: tracerX - 5,
                top: tracerY - 5,
                width: 10,
                height: 10,
                borderRadius: 5,
                backgroundColor: COLORS.ink,
                display: "flex",
              }}
            />
          </>
        )}

        {chart.dot_visible && (
          <>
            {chart.dot_ring_alpha > 0 && (
              <div
                style={{
                  position: "absolute",
                  left: dotX - chart.dot_ring_radius,
                  top: dotY - chart.dot_ring_radius,
                  width: chart.dot_ring_radius * 2,
                  height: chart.dot_ring_radius * 2,
                  borderRadius: chart.dot_ring_radius,
                  border: `2px solid ${dotColor}`,
                  opacity: chart.dot_ring_alpha,
                  display: "flex",
                }}
              />
            )}
            <div
              style={{
                position: "absolute",
                left: dotX - chart.dot_radius,
                top: dotY - chart.dot_radius,
                width: chart.dot_radius * 2,
                height: chart.dot_radius * 2,
                borderRadius: chart.dot_radius,
                backgroundColor: dotColor,
                opacity: chart.dot_alpha,
                display: "flex",
              }}
            />
          </>
        )}
      </div>

      <div
        style={{
          position: "absolute",
          top: mix(1370, 1100, chart.layout_progress),
          left: CANVAS.safe.x,
          display: "flex",
          flexDirection: "row",
          gap: 16,
        }}
      >
        {stats.cards.slice(0, 3).map((card, index) => (
          <div key={index} style={{ opacity: stats.card_alphas?.[index] ?? stats.alpha, display: "flex" }}>
            <StatCard label={card.label} value={card.value} tone={card.tone} />
          </div>
        ))}
      </div>

      {chart.dot_visible && (
        <div
          style={{
            position: "absolute",
            // Anchor the callout just above-and-left of the landing dot (chartTop/chartLeft +
            // dotY/dotX, which track the collapse) so it never overlaps the crimson dot.
            top: chartTop + dotY - 112,
            right: CANVAS.w - (chartLeft + dotX) + 36,
            display: "flex",
            flexDirection: "column",
            alignItems: "flex-end",
            opacity: chart.dot_alpha,
          }}
        >
          <span
            style={{
              fontFamily: TYPE.display.family,
              fontWeight: TYPE.display.weight,
              fontSize: RAMP.body[0],
              color: dotColor,
              lineHeight: 1.05,
              fontVariantNumeric: "tabular-nums",
              display: "flex",
            }}
          >
            {chart.count_value.toLocaleString("en-US")}
          </span>
          <span
            style={{
              fontFamily: TYPE.body.family,
              fontSize: RAMP.body[4],
              color: COLORS.fade,
              marginTop: 6,
              fontVariantNumeric: "tabular-nums",
              display: "flex",
            }}
          >
            births in {chart.current_year}
          </span>
        </div>
      )}

      <div
        style={{
          position: "absolute",
          top: narrativeTop,
          left: CANVAS.safe.x,
          width: CANVAS.w - CANVAS.safe.x * 2,
          opacity: narrative.alpha,
          display: "flex",
          flexDirection: "column",
        }}
      >
        <div
          style={{
            width: CANVAS.w - CANVAS.safe.x * 2,
            height: 1,
            backgroundColor: COLORS.rule,
            marginBottom: 26,
            display: "flex",
          }}
        />
        <div
          style={{
            fontFamily: TYPE.display.family,
            fontWeight: TYPE.display.weight,
            fontSize: RAMP.body[1],
            color: COLORS.ink,
            lineHeight: 1.2,
            maxWidth: 840,
            display: "flex",
          }}
        >
          {narrative.text}
        </div>
        {narrative.supporting_text && (
          <div
            style={{
              fontFamily: TYPE.body.family,
              fontSize: RAMP.body[3],
              color: COLORS.fade,
              lineHeight: 1.45,
              marginTop: 24,
              opacity: narrative.support_alpha,
              maxWidth: 820,
              display: "flex",
            }}
          >
            {narrative.supporting_text}
          </div>
        )}
      </div>

      {comparison.name && comparison.alpha > 0 && (
        <div
          style={{
            position: "absolute",
            top: comparisonTop,
            left: CANVAS.safe.x,
            opacity: comparison.alpha,
            display: "flex",
            flexDirection: "row",
            alignItems: "center",
            gap: 12,
          }}
        >
          <span
            style={{
              fontFamily: TYPE.body.family,
              fontSize: RAMP.body[4],
              color: COLORS.fade,
              letterSpacing: 2,
              textTransform: "uppercase",
              display: "flex",
            }}
          >
            {comparison.label}
          </span>
          <span
            style={{
              fontFamily: TYPE.display.family,
              fontWeight: TYPE.display.weight,
              fontSize: RAMP.body[2],
              color: COLORS.ink,
              fontVariantNumeric: "tabular-nums",
              display: "flex",
            }}
          >
            {comparison.name}
          </span>
        </div>
      )}

      <div
        style={{
          position: "absolute",
          bottom: 320,
          left: CANVAS.safe.x,
          opacity: footer.alpha,
          display: "flex",
          flexDirection: "row",
          alignItems: "center",
          justifyContent: "space-between",
          width: CANVAS.w - CANVAS.safe.x * 2,
        }}
      >
        <div
          style={{
            display: "flex",
            flexDirection: "column",
          }}
        >
          <span
            style={{
              fontFamily: TYPE.display.family,
              fontWeight: TYPE.display.weight,
              fontSize: RAMP.body[2],
              color: COLORS.ink,
              letterSpacing: 2,
              lineHeight: 1.05,
              display: "flex",
            }}
          >
            {footer.site}
          </span>
          <span
            style={{
              fontFamily: TYPE.body.family,
              fontSize: RAMP.body[4],
              color: COLORS.fade,
              marginTop: 6,
              lineHeight: 1.4,
              display: "flex",
            }}
          >
            {footer.cta}
          </span>
        </div>
        <div
          style={{
            width: 20,
            height: 20,
            borderRadius: 10,
            backgroundColor: COLORS.crimson,
            opacity: footer.dot_alpha ?? 1.0,
            display: "flex",
          }}
        />
      </div>
    </div>
  );
}
