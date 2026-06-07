// Hook scene template — 3 s, 90 frames.
// Props:
//   name: string — the baby name
//   tier: Tier
//   headline_chars_visible: number — chars of name revealed so far
//   subhead_alpha: number 0–1 — fade-in of provocation line
//   subhead_text: string — e.g. "Nobody named their baby this in 2024."
//   debug_safe: boolean — overlay safe-area guides

import { CANVAS, COLORS, RAMP, TYPE, Tier, TierBadge } from "./shared";

export interface HookProps {
  name: string;
  tier: Tier;
  headline_chars_visible: number;
  subhead_alpha: number;
  subhead_text: string;
  debug_safe?: boolean;
}

export default function Hook(props: HookProps) {
  const {
    name,
    tier,
    headline_chars_visible,
    subhead_alpha,
    subhead_text,
    debug_safe = false,
  } = props;

  const visibleName = name.slice(0, Math.max(0, headline_chars_visible));

  return (
    <div
      style={{
        width: CANVAS.w,
        height: CANVAS.h,
        backgroundColor: COLORS.bg,
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        alignItems: "flex-start",
        paddingTop: CANVAS.safe.top,
        paddingBottom: CANVAS.safe.bottom,
        paddingLeft: CANVAS.safe.x,
        paddingRight: CANVAS.safe.x,
        position: "relative",
      }}
    >
      {/* Safe-area debug overlay */}
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

      {/* Tier badge */}
      <div style={{ display: "flex", marginBottom: 48 }}>
        <TierBadge tier={tier} />
      </div>

      {/* Name headline — type-on effect */}
      <div
        style={{
          fontFamily: TYPE.display.family,
          fontWeight: TYPE.display.weight,
          fontSize: RAMP.display[0],
          color: COLORS.ink,
          lineHeight: 1.05,
          marginBottom: 48,
          display: "flex",
        }}
      >
        {visibleName}
      </div>

      {/* Provocative subhead — fades in */}
      <div
        style={{
          fontFamily: TYPE.body.family,
          fontWeight: TYPE.body.weight,
          fontSize: RAMP.body[1],
          color: COLORS.fade,
          opacity: subhead_alpha,
          maxWidth: CANVAS.w - CANVAS.safe.x * 2,
          lineHeight: 1.4,
          fontVariantNumeric: "tabular-nums",
          display: "flex",
        }}
      >
        {subhead_text}
      </div>
    </div>
  );
}
