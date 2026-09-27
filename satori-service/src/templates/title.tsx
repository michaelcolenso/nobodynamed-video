// Title card for long-form episodes: the narrated intro and outro that bracket
// the chapter canvases. Every animated value arrives pre-sampled from Python
// (longform/bookends.py); this template only paints one frame.

import { CANVAS, COLORS, RAMP, TYPE } from "./shared";

export interface RosterRow {
  name: string;
  detail: string;
  value: string;
  alpha: number;
  offset_x: number;
  rule_progress: number;
}

export interface TotalBar {
  label: string;
  value: string;
  fraction: number;
  tone: "amber" | "crimson";
  alpha: number;
}

export interface TitleProps {
  kicker: string;
  headline: string;
  subhead: string;
  accent_progress: number;
  headline_alpha: number;
  headline_offset_y: number;
  subhead_alpha: number;
  rule_progress: number;
  roster: RosterRow[];
  totals?: TotalBar[];
  captions?: { alpha: number; text: string };
  footer: { alpha: number; site: string; cta: string; disclosure: string };
  debug_safe?: boolean;
}

const CONTENT_W = CANVAS.w - CANVAS.safe.x * 2;

export default function Title(props: TitleProps) {
  const {
    kicker,
    headline,
    subhead,
    accent_progress,
    headline_alpha,
    headline_offset_y,
    subhead_alpha,
    rule_progress,
    roster,
    totals = [],
    captions,
    footer,
    debug_safe = false,
  } = props;

  return (
    <div
      style={{
        width: CANVAS.w,
        height: CANVAS.h,
        backgroundColor: COLORS.bg,
        display: "flex",
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

      <div
        style={{
          position: "absolute",
          top: 118,
          left: CANVAS.safe.x,
          width: CONTENT_W,
          display: "flex",
          flexDirection: "column",
        }}
      >
        <div
          style={{
            position: "absolute",
            left: -24,
            top: 4,
            width: 6,
            height: 126 * accent_progress,
            backgroundColor: COLORS.crimson,
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
          {kicker}
        </div>
        <div
          style={{
            marginTop: 18,
            fontFamily: TYPE.display.family,
            fontWeight: TYPE.display.weight,
            fontSize: RAMP.display[3],
            lineHeight: 1.06,
            color: COLORS.ink,
            opacity: headline_alpha,
            transform: `translateY(${headline_offset_y}px)`,
            display: "flex",
          }}
        >
          {headline}
        </div>
        <div
          style={{
            marginTop: 28,
            width: CONTENT_W * rule_progress,
            height: 2,
            backgroundColor: COLORS.crimson,
            display: "flex",
          }}
        />
        <div
          style={{
            marginTop: 28,
            fontFamily: TYPE.body.family,
            fontSize: RAMP.body[2],
            lineHeight: 1.35,
            color: COLORS.fade,
            opacity: subhead_alpha,
            display: "flex",
          }}
        >
          {subhead}
        </div>
      </div>

      {roster.length > 0 && (
        <div
          style={{
            position: "absolute",
            top: 540,
            left: CANVAS.safe.x,
            width: CONTENT_W,
            display: "flex",
            flexDirection: "column",
          }}
        >
          {roster.map((row) => (
            <div
              key={row.name}
              style={{
                display: "flex",
                flexDirection: "column",
                paddingTop: 18,
                opacity: row.alpha,
                transform: `translateX(${row.offset_x}px)`,
              }}
            >
              <div
                style={{
                  display: "flex",
                  flexDirection: "row",
                  alignItems: "center",
                  justifyContent: "space-between",
                }}
              >
                <div style={{ display: "flex", flexDirection: "column" }}>
                  <span
                    style={{
                      fontFamily: TYPE.display.family,
                      fontWeight: TYPE.display.weight,
                      fontSize: RAMP.body[1],
                      color: COLORS.ink,
                      lineHeight: 1.1,
                      display: "flex",
                    }}
                  >
                    {row.name}
                  </span>
                  <span
                    style={{
                      fontFamily: TYPE.body.family,
                      fontSize: RAMP.body[4],
                      color: COLORS.fade,
                      marginTop: 4,
                      display: "flex",
                    }}
                  >
                    {row.detail}
                  </span>
                </div>
                <span
                  style={{
                    fontFamily: TYPE.display.family,
                    fontWeight: TYPE.display.weight,
                    fontSize: RAMP.body[1],
                    color: COLORS.crimson,
                    display: "flex",
                  }}
                >
                  {row.value}
                </span>
              </div>
              <div
                style={{
                  marginTop: 18,
                  width: CONTENT_W * row.rule_progress,
                  height: 1,
                  backgroundColor: COLORS.rule,
                  display: "flex",
                }}
              />
            </div>
          ))}
        </div>
      )}

      {totals.length > 0 && (
        <div
          style={{
            position: "absolute",
            top: 600,
            left: CANVAS.safe.x,
            width: CONTENT_W,
            display: "flex",
            flexDirection: "column",
          }}
        >
          {totals.map((bar) => (
            <div
              key={bar.label}
              style={{
                display: "flex",
                flexDirection: "column",
                marginBottom: 56,
                opacity: bar.alpha,
              }}
            >
              <div
                style={{
                  display: "flex",
                  flexDirection: "row",
                  justifyContent: "space-between",
                  alignItems: "flex-end",
                  marginBottom: 16,
                }}
              >
                <span
                  style={{
                    fontFamily: TYPE.body.family,
                    fontSize: RAMP.body[2],
                    color: COLORS.fade,
                    letterSpacing: 2,
                    display: "flex",
                  }}
                >
                  {bar.label}
                </span>
                <span
                  style={{
                    fontFamily: TYPE.display.family,
                    fontWeight: TYPE.display.weight,
                    fontSize: RAMP.display[3],
                    color: bar.tone === "crimson" ? COLORS.crimson : COLORS.amber,
                    lineHeight: 1,
                    display: "flex",
                  }}
                >
                  {bar.value}
                </span>
              </div>
              <div
                style={{
                  width: CONTENT_W,
                  height: 64,
                  backgroundColor: COLORS.rule,
                  display: "flex",
                }}
              >
                <div
                  style={{
                    width: Math.max(CONTENT_W * bar.fraction, 2),
                    height: 64,
                    backgroundColor: bar.tone === "crimson" ? COLORS.crimson : COLORS.amber,
                    display: "flex",
                  }}
                />
              </div>
            </div>
          ))}
        </div>
      )}

      {captions && captions.alpha > 0 && captions.text && (
        <div
          style={{
            position: "absolute",
            top: 1510,
            left: CANVAS.safe.x,
            width: CONTENT_W,
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
              borderColor: COLORS.crimson,
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
          top: 1640,
          left: CANVAS.safe.x,
          width: CONTENT_W,
          opacity: footer.alpha,
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
            display: "flex",
          }}
        >
          {footer.cta}
        </span>
      </div>

      {footer.disclosure && (
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
          {footer.disclosure}
        </div>
      )}
    </div>
  );
}
