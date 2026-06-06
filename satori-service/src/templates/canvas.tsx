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
          letterSpacing: 1.2,
          textTransform: "uppercase",
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
          lineHeight: 1.05,
          display: "flex",
        }}
      >
        {value}
      </div>
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
  const chartTop = mix(500, 400, chart.layout_progress);
  const chartWidth = mix(CANVAS.w - CANVAS.safe.x * 2, 920, chart.layout_progress);
  const chartHeight = mix(550, 420, chart.layout_progress);

  const toX = (year: number) => Math.round(((year - minYear) / Math.max(maxYear - minYear, 1)) * chartWidth);
  const toY = (count: number) => Math.round(chartHeight - (count / maxCount) * chartHeight);

  const totalPoints = filtered.length;
  const progressPoints = chart.draw_progress * totalPoints;
  const fullSegments = Math.floor(progressPoints);
  const partialT = progressPoints - fullSegments;
  const drawnPoints = filtered.slice(0, fullSegments + 2);

  const segments: Array<{ x: number; y: number; length: number; angle: number }> = [];
  let tracerX = toX(filtered[0]?.year ?? chart.current_year);
  let tracerY = toY(filtered[0]?.count ?? 0);

  for (let i = 1; i < drawnPoints.length; i++) {
    const x1 = toX(drawnPoints[i - 1].year);
    const y1 = toY(drawnPoints[i - 1].count);
    const x2 = toX(drawnPoints[i].year);
    const y2 = toY(drawnPoints[i].count);
    const segmentIndex = i - 1;
    if (segmentIndex < fullSegments) {
      const length = Math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2);
      const angle = Math.atan2(y2 - y1, x2 - x1) * (180 / Math.PI);
      segments.push({ x: x1, y: y1, length, angle });
      tracerX = x2;
      tracerY = y2;
    } else if (segmentIndex === fullSegments && partialT > 0) {
      const ix = Math.round(x1 + (x2 - x1) * partialT);
      const iy = Math.round(y1 + (y2 - y1) * partialT);
      const length = Math.sqrt((ix - x1) ** 2 + (iy - y1) ** 2);
      const angle = Math.atan2(iy - y1, ix - x1) * (180 / Math.PI);
      segments.push({ x: x1, y: y1, length, angle });
      tracerX = ix;
      tracerY = iy;
    }
  }

  const currentPoint = filtered.find((point) => point.year === chart.current_year) ?? filtered[filtered.length - 1];
  const dotX = toX(currentPoint?.year ?? chart.current_year);
  const dotY = toY(currentPoint?.count ?? 0);
  const eventX = chart.event_year != null ? toX(Math.max(minYear, Math.min(maxYear, chart.event_year))) : 0;

  const narrativeTop = mix(1220, 1060, chart.layout_progress);

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
            letterSpacing: 3,
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
            marginTop: 18,
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
        <div
          style={{
            position: "absolute",
            top: Math.round(chartHeight / 2),
            left: 0,
            width: chartWidth,
            height: 1,
            backgroundColor: COLORS.rule,
            display: "flex",
          }}
        />

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
                  display: "flex",
                }}
              >
                {chart.event_label}
              </span>
            </div>
          </>
        )}

        {segments.map((segment, index) => (
          <div
            key={index}
            style={{
              position: "absolute",
              left: segment.x,
              top: segment.y,
              width: Math.max(segment.length, 1),
              height: 3,
              backgroundColor: COLORS.ink,
              transform: `rotate(${segment.angle}deg)`,
              transformOrigin: "0 50%",
              display: "flex",
            }}
          />
        ))}

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
                  border: `2px solid ${COLORS.crimson}`,
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
                backgroundColor: COLORS.crimson,
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
          top: mix(1100, 930, chart.layout_progress),
          left: CANVAS.safe.x,
          opacity: stats.alpha,
          display: "flex",
          flexDirection: "row",
          gap: 16,
        }}
      >
        {stats.cards.slice(0, 3).map((card, index) => (
          <StatCard key={index} label={card.label} value={card.value} tone={card.tone} />
        ))}
      </div>

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
            marginBottom: 34,
            display: "flex",
          }}
        />
        <div
          style={{
            fontFamily: TYPE.display.family,
            fontWeight: TYPE.display.weight,
            fontSize: RAMP.body[1],
            color: COLORS.ink,
            lineHeight: 1.12,
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
              marginTop: 20,
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
            top: 1540,
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
              letterSpacing: 1.5,
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
          bottom: 118,
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
            display: "flex",
          }}
        />
      </div>
    </div>
  );
}
