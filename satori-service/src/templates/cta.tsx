// CTA scene template — 3 s, 90 frames.
// Props:
//   logo_alpha: number 0–1 — fade-in of site URL
//   dot_alpha: number 0–1 — pulsing crimson dot
//   tier: Tier
//   debug_safe?: boolean

import { CANVAS, COLORS, RAMP, TYPE, Tier, TierBadge } from "./shared";

export interface CtaProps {
  tier: Tier;
  logo_alpha: number;
  dot_alpha: number;
  debug_safe?: boolean;
}

export default function Cta(props: CtaProps) {
  const { tier, logo_alpha, dot_alpha, debug_safe = false } = props;

  return (
    <div
      style={{
        width: CANVAS.w,
        height: CANVAS.h,
        backgroundColor: COLORS.bg,
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        alignItems: "center",
        position: "relative",
      }}
    >
      {debug_safe && (
        <>
          <div style={{ position: "absolute", top: 0, left: 0, width: CANVAS.w, height: CANVAS.safe.top, backgroundColor: "rgba(255,0,0,0.35)", display: "flex" }} />
          <div style={{ position: "absolute", bottom: 0, left: 0, width: CANVAS.w, height: CANVAS.safe.bottom, backgroundColor: "rgba(255,0,0,0.35)", display: "flex" }} />
        </>
      )}

      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          opacity: logo_alpha,
          gap: 32,
        }}
      >
        {/* Pulsing crimson dot */}
        <div
          style={{
            width: 32,
            height: 32,
            borderRadius: 16,
            backgroundColor: COLORS.crimson,
            opacity: dot_alpha,
            display: "flex",
          }}
        />

        {/* Tier badge */}
        <TierBadge tier={tier} />

        {/* Site URL */}
        <div
          style={{
            fontFamily: TYPE.display.family,
            fontWeight: TYPE.display.weight,
            fontSize: RAMP.display[2],
            color: COLORS.ink,
            letterSpacing: 2,
            display: "flex",
          }}
        >
          nobodynamed.com
        </div>

        {/* Tagline */}
        <div
          style={{
            fontFamily: TYPE.body.family,
            fontWeight: TYPE.body.weight,
            fontSize: RAMP.body[2],
            color: COLORS.fade,
            display: "flex",
          }}
        >
          The names that time forgot.
        </div>
      </div>
    </div>
  );
}
