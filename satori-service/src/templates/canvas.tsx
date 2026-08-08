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
  draw_duration_s: number;
  tracer_alpha?: number;
  tracer_year_alpha?: number;
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
  card_offsets?: number[];
}

interface NarrativeState {
  alpha: number;
  support_alpha: number;
  offset_y?: number;
  support_offset_y?: number;
  text: string;
  supporting_text?: string | null;
}

interface ComparisonState {
  alpha: number;
  offset_y?: number;
  label: string;
  name?: string | null;
}

interface FooterState {
  alpha: number;
  site: string;
  cta: string;
  disclosure?: string;
  dot_alpha?: number;
  dot_radius?: number;
}

interface CaptionState {
  alpha: number;
  text: string;
  current_word: string;
  progress: number;
}

export interface CanvasProps {
  program: string;
  register: string;
  story_kind?: "one_hit" | "cultural_rupture" | "long_decline" | "comeback" | "legacy";
  loop_progress?: number;
  tier: Tier;
  header: HeaderState;
  diagnosis: DiagnosisState;
  chart: ChartState;
  stats: StatsState;
  narrative: NarrativeState;
  comparison: ComparisonState;
  footer: FooterState;
  captions?: CaptionState;
  debug_safe?: boolean;
}

function mix(a: number, b: number, progress: number) {
  return a + (b - a) * progress;
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

// ── Speed-curve cache ──────────────────────────────────────────────────────
// smoothPathD is called once per frame (330× per video). The speed curve
// (the pos[] array and posTotal) depends only on the data points and
// drawDurationS — never on drawProgress. Without memoization, each frame
// recomputes the 120 Hz grid, gaussian kernel, and integration from scratch
// (~14K ops × 330 frames = 4.6M redundant operations). A single-entry cache
// eliminates 99.7% of the work: frames for the same video hit the cache,
// and a new video simply evicts.
interface SpeedCurve {
  pos: number[];
  posTotal: number;
  totalSegments: number;
}
let _speedCacheKey = "";
let _speedCache: SpeedCurve | null = null;

export function speedCurveCacheKey(
  points: Array<{ x: number; y: number }>,
  drawDurationS: number,
): string {
  let seriesHash = 2166136261;
  for (const point of points) {
    const token = `${point.x.toFixed(3)},${point.y.toFixed(3)};`;
    for (let index = 0; index < token.length; index += 1) {
      seriesHash ^= token.charCodeAt(index);
      seriesHash = Math.imul(seriesHash, 16777619);
    }
  }
  return `${points.length}:${seriesHash >>> 0}:${drawDurationS}`;
}

export function selectTracerYearLabel(
  tracerYear: number,
  milestoneYears: number[],
): number {
  const nearestMilestone = milestoneYears.reduce((best, year) =>
    Math.abs(year - tracerYear) < Math.abs(best - tracerYear) ? year : best,
  );
  return Math.abs(nearestMilestone - tracerYear) <= 1
    ? nearestMilestone
    : Math.round(tracerYear / 10) * 10;
}

function computeSpeedCurve(
  points: Array<{ x: number; y: number }>,
  totalSegments: number,
  drawDurationS: number,
): SpeedCurve {
  // Hash every point. Name-series commonly have the same length, baseline
  // endpoints, and duration, so an endpoint-only key can serve one video's
  // timing curve to another when clustered workers receive interleaved jobs.
  const key = speedCurveCacheKey(points, drawDurationS);
  if (_speedCacheKey === key && _speedCache) return _speedCache;
  _speedCacheKey = key;

    // Time-domain speed design. Earlier versions mapped draw progress to
    // segment indices via piecewise-constant per-segment costs — every year
    // boundary was a velocity STEP (~145 hard cuts per video), the draw
    // started and stopped dead, and the flatline→story transition slammed
    // from 100 y/s to near-zero in one frame. Instead, design the tracer's
    // SPEED CURVE directly: per-segment nominal seconds (flatline at
    // FLAT_PACE_YPS years/sec, story slope-weighted) become speeds on a fine
    // time grid, get multiplied by soft start/stop ramps, gaussian-smoothed,
    // then integrated and normalized. Velocity is smooth end to end: the
    // tracer glides up to pace, decelerates into the story over ~0.4s, and
    // lands softly instead of stopping dead.
    const FLAT_PACE_YPS = 100;
    const FLAT_BUDGET_CAP = 0.3;
    const FLAT_COST = 0.35;
    const SLOPE_WEIGHT = 10;
    const SIGMA_S = 0.16;
    const TICKS_PER_S = 120;

    const maxY = Math.max(...points.map((p) => p.y));
    const firstNz = points.findIndex((p) => p.y < maxY - 0.5);
    const storyStart = firstNz === -1 ? 0 : firstNz;

    const flatSeconds =
      storyStart > 0
        ? Math.min(storyStart / FLAT_PACE_YPS, FLAT_BUDGET_CAP * drawDurationS)
        : 0;
    const storySeconds = drawDurationS - flatSeconds;
    const nStory = totalSegments - storyStart;
    const storyDy = points
      .slice(storyStart + 1)
      .map((p, i) => Math.abs(p.y - points[storyStart + i].y));
    const maxDy = Math.max(...storyDy, 1);
    const gaps = points
      .slice(1)
      .map((point, index) => point.x - points[index].x)
      .filter((gap) => gap > 0);
    const sortedGaps = [...gaps].sort((a, b) => a - b);
    const typicalGap = sortedGaps[Math.floor(sortedGaps.length / 2)] ?? 1;
    const peakIndex = points.reduce(
      (best, point, index) => (point.y < points[best].y ? index : best),
      0,
    );
    const steepestFallIndex = points.slice(1).reduce(
      (best, point, index) => {
        const segment = index;
        const fall = point.y - points[segment].y;
        const bestFall = points[best + 1].y - points[best].y;
        return fall > bestFall ? segment : best;
      },
      0,
    );
    const recentStart = Math.max(storyStart, totalSegments - 15);
    const landmarkWeight = (segment: number, center: number, radius: number, boost: number) => {
      const distance = Math.abs(segment - center);
      if (distance >= radius) return 1;
      const u = 1 - distance / radius;
      return 1 + boost * u * u * (3 - 2 * u);
    };
    const costs = storyDy.map((d, storyIndex) => {
      const segment = storyStart + storyIndex;
      const slopeCost = d < 0.5 ? FLAT_COST : 1 + (SLOPE_WEIGHT * d) / maxDy;
      const firstAppearance = landmarkWeight(segment, storyStart, 3, 1.4);
      const peak = landmarkWeight(segment, peakIndex, 4, 3.2);
      const collapse = landmarkWeight(segment, steepestFallIndex, 3, 1.8);
      const recent = segment >= recentStart ? 1.45 : 1;
      // PR #27 adds dense render-only points around one-hit spikes. Treat that
      // dense run as an authored beat, so it receives enough time to read as a
      // climb and hold instead of being compressed into a single gesture.
      const gap = points[segment + 1]?.x - points[segment]?.x;
      const dense = gap !== undefined && gap < typicalGap * 0.5;
      const denseNeighbor = [segment - 1, segment, segment + 1].some((candidate) => {
        const candidateGap = points[candidate + 1]?.x - points[candidate]?.x;
        return candidateGap !== undefined && candidateGap < typicalGap * 0.5;
      });
      const spikeBeat = dense || denseNeighbor ? 8.0 : 1;
      return slopeCost * firstAppearance * peak * collapse * recent * spikeBeat;
    });
    const costSum = costs.reduce((a, b) => a + b, 0);

    const segT = new Array<number>(totalSegments).fill(0);
    for (let i = 0; i < totalSegments; i++) {
      if (i < storyStart) segT[i] = storyStart > 0 ? flatSeconds / storyStart : 0;
      else if (nStory > 0 && costSum > 0)
        segT[i] = (storySeconds * costs[i - storyStart]) / costSum;
    }
    const cumT: number[] = [0];
    for (let i = 0; i < totalSegments; i++) cumT.push(cumT[i] + segT[i]);

    // Sample the authored cumulative-time map directly. Integrating a
    // piecewise speed curve and normalizing afterward can erase the intended
    // budget of a dense spike; direct lookup keeps each landmark's duration.
    const K = Math.max(2, Math.ceil(drawDurationS * TICKS_PER_S));
    const rawPos = new Array<number>(K);
    for (let k = 0; k < K; k++) {
      const tau = (k + 0.5) / TICKS_PER_S;
      let seg = totalSegments - 1;
      for (let i = 0; i < totalSegments; i++) {
        if (cumT[i + 1] > tau) {
          seg = i;
          break;
        }
      }
      const segmentStart = cumT[seg];
      const segmentDuration = segT[seg] || 1;
      rawPos[k] = seg + Math.min(Math.max((tau - segmentStart) / segmentDuration, 0), 1);
    }

    // Smooth position lightly to remove velocity steps at year boundaries,
    // then normalize the endpoints back to the exact chart domain.
    const sigma = SIGMA_S * TICKS_PER_S;
    const kr = Math.ceil(3 * sigma);
    const kernel: number[] = [];
    let kSum = 0;
    for (let j = -kr; j <= kr; j++) {
      const wgt = Math.exp(-0.5 * (j / sigma) ** 2);
      kernel.push(wgt);
      kSum += wgt;
    }
    const smoothedPos = new Array<number>(K);
    for (let k = 0; k < K; k++) {
      let acc = 0;
      for (let j = -kr; j <= kr; j++) {
        const idx = Math.min(Math.max(k + j, 0), K - 1);
        acc += kernel[j + kr] * rawPos[idx];
      }
      smoothedPos[k] = acc / kSum;
    }
    const startPos = smoothedPos[0] ?? 0;
    const endPos = smoothedPos[K - 1] ?? totalSegments;
    const span = Math.max(endPos - startPos, 1e-9);
    const pos = smoothedPos.map((value) => ((value - startPos) / span) * totalSegments);
    const posTotal = totalSegments;

    _speedCache = { pos, posTotal, totalSegments };
    return _speedCache;
  }

  function smoothPathD(
    points: Array<{ x: number; y: number }>,
    drawProgress: number,
    drawDurationS: number = 4.2,
  ): { pathD: string; tracerX: number; tracerY: number; tracerSegment: number } {
    if (points.length === 0)
      return { pathD: "", tracerX: 0, tracerY: 0, tracerSegment: 0 };
    if (points.length === 1)
      return {
        pathD: `M ${points[0].x} ${points[0].y}`,
        tracerX: points[0].x,
        tracerY: points[0].y,
        tracerSegment: 0,
      };

    // Standard Catmull-Rom → cubic bezier conversion.
    // For segment i→i+1, control points are:
    //   cp1 = Pi + (Pi+1 - Pi-1) / 6
    //   cp2 = Pi+1 - (Pi+2 - Pi) / 6
    // Edge segments mirror the previous/next point.

    const totalSegments = points.length - 1;

    // Speed curve is identical across all frames of a video — memoize.
    const { pos, posTotal } = computeSpeedCurve(points, totalSegments, drawDurationS);

    // Look up the tracer's segment-space position at this frame's time.
    const TICKS_PER_S = 120;
    const clamp01 = (x: number) => Math.min(Math.max(x, 0), 1);
    const tauNow = clamp01(drawProgress) * drawDurationS;
    const K = pos.length;
    const fTick = Math.min(Math.max(tauNow * TICKS_PER_S - 0.5, 0), K - 1);
    const tk0 = Math.floor(fTick);
    const tk1 = Math.min(tk0 + 1, K - 1);
    const segPos =
      ((pos[tk0] + (pos[tk1] - pos[tk0]) * (fTick - tk0)) / posTotal) *
      totalSegments;

    let fullSegments = totalSegments;
    let partialT = 0;
    if (segPos < totalSegments) {
      fullSegments = Math.max(0, Math.floor(segPos));
      partialT = Math.min(segPos - fullSegments, 1);
    }

    let pathD = "";
    let tracerX = points[0].x;
    let tracerY = points[0].y;

    // Catmull-Rom overshoots at a floor of repeated values: a name whose count
    // hits the zero baseline (SSA suppression / extinction) got a visible curl
    // *below* the axis. The baseline is the largest y (y is inverted), so clamp
    // every control point to it.
    const floorY = Math.max(...points.map((p) => p.y));
    const clampY = (y: number) => Math.min(y, floorY);

    for (let seg = 0; seg < fullSegments; seg++) {
      const p0 = points[Math.max(0, seg - 1)];
      const p1 = points[seg];
      const p2 = points[seg + 1];
      const p3 = points[Math.min(points.length - 1, seg + 2)];

      const cp1 = { x: p1.x + (p2.x - p0.x) / 6, y: clampY(p1.y + (p2.y - p0.y) / 6) };
      const cp2 = { x: p2.x - (p3.x - p1.x) / 6, y: clampY(p2.y - (p3.y - p1.y) / 6) };

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

      const cp1 = { x: p1.x + (p2.x - p0.x) / 6, y: clampY(p1.y + (p2.y - p0.y) / 6) };
      const cp2 = { x: p2.x - (p3.x - p1.x) / 6, y: clampY(p2.y - (p3.y - p1.y) / 6) };

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

    return { pathD, tracerX, tracerY, tracerSegment: segPos };
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

function DisclosureBadge({ text }: { text: string }) {
  return (
    <div
      style={{
        position: "absolute",
        top: 124,
        right: CANVAS.safe.x,
        borderWidth: 1,
        borderStyle: "solid",
        borderColor: COLORS.rule,
        color: COLORS.fade,
        fontFamily: TYPE.body.family,
        fontSize: 18,
        letterSpacing: 2,
        paddingTop: 8,
        paddingBottom: 8,
        paddingLeft: 12,
        paddingRight: 12,
        display: "flex",
      }}
    >
      {text}
    </div>
  );
}

function OpeningOverlay({
  alpha,
  accentColor,
  tier,
  header,
  diagnosis,
}: {
  alpha: number;
  accentColor: string;
  tier: Tier;
  header: HeaderState;
  diagnosis: DiagnosisState;
}) {
  if (alpha <= 0) return null;
  // Bring the returning hook to readable contrast slightly faster than the
  // background wipe. A linear 50/50 crossfade made the midpoint muddy.
  const contentAlpha = alpha * (2 - alpha);
  return (
    <>
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          width: CANVAS.w,
          height: CANVAS.h,
          backgroundColor: COLORS.bg,
          opacity: alpha,
          display: "flex",
        }}
      />
      <div
        style={{
          position: "absolute",
          top: 118,
          left: CANVAS.safe.x,
          width: CANVAS.w - CANVAS.safe.x * 2,
          opacity: contentAlpha,
          flexDirection: "column",
          display: "flex",
        }}
      >
        <div
          style={{
            position: "absolute",
            left: -24,
            top: 4,
            width: 6,
            height: 126,
            backgroundColor: accentColor,
            display: "flex",
          }}
        />
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
            marginTop: 18,
            alignItems: "center",
            justifyContent: "space-between",
            display: "flex",
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
          width: CANVAS.w - CANVAS.safe.x * 2,
          opacity: contentAlpha,
          flexDirection: "column",
          display: "flex",
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
    </>
  );
}

export default function Canvas(props: CanvasProps) {
  const {
    tier,
    header,
    diagnosis,
    chart,
    stats,
    narrative,
    comparison,
    footer,
    captions,
    story_kind = "legacy",
    loop_progress = 0,
    debug_safe = false,
  } = props;

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
  const { pathD, tracerX, tracerY, tracerSegment } = smoothPathD(
    curvePoints,
    chart.draw_progress,
    chart.draw_duration_s,
  );

  // Area fill — closes the path with a clean line to baseline, then smooth bezier back.
  const pathAreaD = pathD
    ? `M ${curvePoints[0]?.x ?? 0} ${chartHeight} ${pathD.replace(/^M /, "L ")} L ${tracerX} ${chartHeight} Z`
    : "";

  const currentPoint = filtered.find((point) => point.year === chart.current_year) ?? filtered[filtered.length - 1];
  const dotX = toX(currentPoint?.year ?? chart.current_year);
  const dotY = toY(currentPoint?.count ?? 0);
  const eventX = chart.event_year != null ? toX(Math.max(minYear, Math.min(maxYear, chart.event_year))) : 0;

  const narrativeTop = mix(1250, 1340, chart.layout_progress) + (narrative.offset_y ?? 0);
  // The comparison row lives in the gap between the stat cards (~1230) and
  // the narrative rule (1340) — at 1420 it sat on top of the narrative's
  // supporting line. It is only visible post-recompose (alpha follows
  // SUPPORT_ALPHA), so the expanded-layout value never renders.
  const comparisonTop = mix(1640, 1262, chart.layout_progress) + (comparison.offset_y ?? 0);
  const accentColor =
    story_kind === "comeback"
      ? COLORS.emerald
      : story_kind === "one_hit" || story_kind === "long_decline"
        ? COLORS.amber
        : story_kind === "cultural_rupture"
          ? COLORS.crimson
          : tier === "rising" || tier === "resurrected"
            ? COLORS.emerald
            : COLORS.crimson;
  const curveColor = story_kind === "legacy" ? COLORS.ink : accentColor;
  const dotColor = accentColor;
  const peakX = toX(chart.peak_year);
  // Year the tracer is currently passing through — toX is linear in year, so
  // the inverse mapping from tracerX recovers it exactly.
  const tracerYear = Math.round(
    minYear + (tracerX / Math.max(chartWidth, 1)) * (maxYear - minYear),
  );
  const firstAppearanceYear =
    filtered.find((point) => point.count > 0)?.year ?? minYear;
  const steepestFallYear = filtered.slice(1).reduce(
    (bestYear, point, index) => {
      const fall = filtered[index].count - point.count;
      const bestIndex = Math.max(
        1,
        filtered.findIndex((candidate) => candidate.year === bestYear),
      );
      const bestFall = filtered[bestIndex - 1].count - filtered[bestIndex].count;
      return fall > bestFall ? point.year : bestYear;
    },
    filtered[1]?.year ?? minYear,
  );
  const milestoneYears = [
    firstAppearanceYear,
    chart.peak_year,
    steepestFallYear,
    chart.current_year,
  ];
  const tracerYearLabel = selectTracerYearLabel(tracerYear, milestoneYears);
  // Smoothstep ramp over 12% of draw progress — softer than the old 5% linear
  // snap, which popped the year readout in almost immediately. The gentler
  // ramp lets the tracer dot establish itself before the year label appears.
  const _tracerAlphaU = Math.min(Math.max(chart.draw_progress / 0.12, 0), 1);
  const tracerYearAlpha = 0.95 * _tracerAlphaU * _tracerAlphaU * (3 - 2 * _tracerAlphaU);
  // Fall back to the old hard on/off when the prop is absent (older payloads).
  const tracerAlpha =
    chart.tracer_alpha ?? (chart.draw_progress > 0 && chart.draw_progress < 1 ? 1 : 0);
  // The year readout has its own, earlier exit so it never prints under the
  // landing callout that occupies the same corner.
  const tracerYearOut = chart.tracer_year_alpha ?? tracerAlpha;
  // Peak-year x-label: fade it across the last 60px at either edge instead of
  // switching it off at a threshold — during the recompose chartWidth animates
  // through that threshold and the label blinked out mid-move.
  const peakLabelAlpha =
    0.5 * Math.min(Math.max(peakX / 60, 0), 1) * Math.min(Math.max((chartWidth - peakX) / 60, 0), 1);
  const peakIndex = Math.max(
    0,
    filtered.findIndex((point) => point.year === chart.peak_year),
  );
  // Trigger from the tracer's actual remapped position, not the peak's linear
  // year fraction. This keeps the callout attached to the moment of arrival.
  const peakRevealU = Math.min(Math.max((tracerSegment - peakIndex) / 2.5, 0), 1);
  const peakAnnotationAlpha =
    peakRevealU * peakRevealU * (3 - 2 * peakRevealU) * (1 - chart.layout_progress);

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
        {story_kind !== "legacy" && (
          <div
            style={{
              position: "absolute",
              left: -24,
              top: 4,
              width: 6,
              height: 126,
              backgroundColor: accentColor,
              display: "flex",
            }}
          />
        )}
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
            fontSize: 22,
            color: COLORS.fade,
            opacity: 0.5,
            display: "flex",
          }}
        >
          {String(minYear)}
        </div>
        {peakLabelAlpha > 0.01 && (
          <div
            style={{
              position: "absolute",
              left: peakX - 16,
              top: chartHeight + 8,
              fontFamily: TYPE.body.family,
              fontSize: 22,
              color: COLORS.fade,
              opacity: peakLabelAlpha,
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
            fontSize: 22,
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
              <stop offset="100%" stopColor={accentColor} stopOpacity={0.16} />
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

          {/* Chart line — wide soft halo behind the crisp 3px stroke for
              depth. Two stacked paths: a 10px semi-transparent stroke acts
              as a glow, then the 3px ink stroke sits on top. No SVG filters
              (resvg-safe), just paint order. */}
          <path
            d={pathD}
            fill="none"
            stroke={curveColor}
            strokeWidth={10}
            strokeLinecap="round"
            strokeLinejoin="round"
            opacity={0.08}
          />
          {/* Chart line — crisp 3px stroke on top of the halo */}
          <path
            d={pathD}
            fill="none"
            stroke={curveColor}
            strokeWidth={4}
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>

        {peakAnnotationAlpha > 0 && (
          <>
            <div
              style={{
                position: "absolute",
                left: peakX - 5,
                top: toY(chart.peak_count) - 5,
                width: 10,
                height: 10,
                borderRadius: 5,
                backgroundColor: COLORS.ink,
                opacity: peakAnnotationAlpha * 0.85,
                display: "flex",
              }}
            />
            <div
              style={{
                position: "absolute",
                left: peakX - 1,
                top: toY(chart.peak_count) + 12,
                width: 2,
                height: 32,
                backgroundColor: COLORS.ink,
                opacity: peakAnnotationAlpha * 0.4,
                display: "flex",
              }}
            />
            {/* Wide box + nowrap: the label must never wrap onto two lines
                under the curve apex (it collides with its own stem). */}
            <div
              style={{
                position: "absolute",
                left: Math.max(0, Math.min(chartWidth - 320, peakX - 160)),
                top: toY(chart.peak_count) + 50,
                width: 320,
                opacity: peakAnnotationAlpha,
                display: "flex",
                justifyContent: "center",
              }}
            >
              <span
                style={{
                  fontFamily: TYPE.display.family,
                  fontWeight: TYPE.display.weight,
                  fontSize: RAMP.body[2],
                  color: COLORS.ink,
                  letterSpacing: 2,
                  textTransform: "uppercase",
                  whiteSpace: "nowrap",
                  display: "flex",
                }}
              >
                PEAK · {chart.peak_year}
              </span>
            </div>
          </>
        )}

        {/* The tracer cross-fades into the landing dot rather than being
            switched off on the frame the draw completes: at draw_progress === 1
            the tracer sits exactly on the landing point, so a short overlap
            (tracer_alpha 1 → 0 while dot_alpha 0 → 1) reads as one mark
            arriving, not one disappearing and another appearing. */}
        {tracerAlpha > 0 && (
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
                opacity: chart.tracer_glow_alpha * tracerAlpha,
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
                opacity: tracerAlpha,
                display: "flex",
              }}
            />
            {/* Year readout riding above the tracer — the draw reads as time
                passing, not just a line appearing. Display-black ink at body[2],
                matching the peak annotation, so it survives phone-scale viewing.
                Clamped inside the chart so it never clips at either edge. */}
            <div
              style={{
                position: "absolute",
                left: Math.max(0, Math.min(chartWidth - 140, tracerX - 70)),
                top: Math.max(-24, tracerY - 76),
                width: 140,
                justifyContent: "center",
                fontFamily: TYPE.display.family,
                fontWeight: TYPE.display.weight,
                fontSize: RAMP.body[2],
                color: COLORS.ink,
                letterSpacing: 2,
                fontVariantNumeric: "tabular-nums",
                opacity:
                  tracerYearAlpha * tracerYearOut * (1 - peakAnnotationAlpha),
                display: "flex",
              }}
            >
              {String(tracerYearLabel)}
            </div>
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
          <div
            key={index}
            style={{
              opacity: stats.card_alphas?.[index] ?? stats.alpha,
              marginTop: stats.card_offsets?.[index] ?? 0,
              display: "flex",
            }}
          >
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
              marginTop: 24 + (narrative.support_offset_y ?? 0),
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

      {captions && captions.alpha > 0 && captions.text && (
        <div
          style={{
            position: "absolute",
            top: 1510,
            left: CANVAS.safe.x,
            width: CANVAS.w - CANVAS.safe.x * 2,
            opacity: captions.alpha,
            alignItems: "center",
            justifyContent: "center",
            display: "flex",
          }}
        >
          <div
            style={{
              backgroundColor: "rgba(20,17,14,0.90)",
              borderWidth: 1,
              borderStyle: "solid",
              borderColor: accentColor,
              paddingTop: 16,
              paddingBottom: 18,
              paddingLeft: 26,
              paddingRight: 26,
              fontFamily: TYPE.display.family,
              fontWeight: TYPE.display.weight,
              fontSize: RAMP.body[2],
              lineHeight: 1.18,
              color: COLORS.ink,
              textAlign: "center",
              display: "flex",
            }}
          >
            {captions.text}
          </div>
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
        {/* Fixed 24×24 box so the breathing dot grows from its centre without
            shifting the footer row's layout. */}
        <div
          style={{
            width: 24,
            height: 24,
            alignItems: "center",
            justifyContent: "center",
            display: "flex",
          }}
        >
          <div
            style={{
              width: (footer.dot_radius ?? 10) * 2,
              height: (footer.dot_radius ?? 10) * 2,
              borderRadius: footer.dot_radius ?? 10,
              backgroundColor: accentColor,
              opacity: footer.dot_alpha ?? 1.0,
              display: "flex",
            }}
          />
        </div>
      </div>

      <OpeningOverlay
        alpha={loop_progress}
        accentColor={accentColor}
        tier={tier}
        header={header}
        diagnosis={diagnosis}
      />
      {footer.disclosure && <DisclosureBadge text={footer.disclosure} />}
    </div>
  );
}
