// Narrative scene template — 6 s, 180 frames.
// Props:
//   name: string
//   tier: Tier
//   story: string — one-sentence narrative
//   kb_scale: number 1.0–1.04 — Ken Burns scale
//   kb_x: number — horizontal Ken Burns offset (0–1, normalized to canvas)
//   kb_y: number — vertical Ken Burns offset (0–1, normalized to canvas)
//   scene_alpha: number 0–1 — crossfade in
//   peak_year: number
//   peak_count: number
//   debug_safe?: boolean

import { CANVAS, COLORS, RAMP, TYPE, Tier, TierBadge } from "./shared";

export interface NarrativeProps {
  name: string;
  tier: Tier;
  story: string;
  kb_scale: number;
  kb_x: number;
  kb_y: number;
  scene_alpha: number;
  peak_year: number;
  peak_count: number;
  debug_safe?: boolean;
}

export default function Narrative(props: NarrativeProps) {
  const {
    name,
    tier,
    story,
    kb_scale,
    scene_alpha,
    peak_year,
    peak_count,
    debug_safe = false,
  } = props;

  return (
    <div
      style={{
        width: CANVAS.w,
        height: CANVAS.h,
        backgroundColor: COLORS.bg,
        opacity: scene_alpha,
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        alignItems: "flex-start",
        paddingTop: CANVAS.safe.top,
        paddingBottom: CANVAS.safe.bottom,
        paddingLeft: CANVAS.safe.x,
        paddingRight: CANVAS.safe.x,
        position: "relative",
        // Ken Burns via scale transform on the inner container.
      }}
    >
      {debug_safe && (
        <>
          <div style={{ position: "absolute", top: 0, left: 0, width: CANVAS.w, height: CANVAS.safe.top, backgroundColor: "rgba(255,0,0,0.35)", display: "flex" }} />
          <div style={{ position: "absolute", bottom: 0, left: 0, width: CANVAS.w, height: CANVAS.safe.bottom, backgroundColor: "rgba(255,0,0,0.35)", display: "flex" }} />
        </>
      )}

      {/* Ken Burns wrapper — subtle scale */}
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          transform: `scale(${kb_scale})`,
          transformOrigin: "center center",
          width: "100%",
        }}
      >
        {/* Tier badge */}
        <div style={{ display: "flex", marginBottom: 48 }}>
          <TierBadge tier={tier} />
        </div>

        {/* Name */}
        <div
          style={{
            fontFamily: TYPE.display.family,
            fontWeight: TYPE.display.weight,
            fontSize: RAMP.display[1],
            color: COLORS.ink,
            marginBottom: 16,
            display: "flex",
          }}
        >
          {name}
        </div>

        {/* Peak stat line */}
        <div
          style={{
            display: "flex",
            flexDirection: "row",
            alignItems: "center",
            marginBottom: 56,
            gap: 24,
          }}
        >
          <span style={{ fontFamily: TYPE.display.family, fontWeight: TYPE.display.weight, fontSize: RAMP.body[0], color: COLORS.crimson, lineHeight: 1.05, fontVariantNumeric: "tabular-nums", display: "flex" }}>
            {peak_count.toLocaleString("en-US")}
          </span>
          <span style={{ fontFamily: TYPE.body.family, fontSize: RAMP.body[2], color: COLORS.fade, fontVariantNumeric: "tabular-nums", display: "flex" }}>
            peak in {peak_year}
          </span>
        </div>

        {/* Hairline divider */}
        <div style={{ width: "100%", height: 1, backgroundColor: COLORS.rule, marginBottom: 48, display: "flex" }} />

        {/* Story sentence */}
        <div
          style={{
            fontFamily: TYPE.body.family,
            fontWeight: TYPE.body.weight,
            fontSize: RAMP.body[1],
            color: COLORS.ink,
            lineHeight: 1.55,
            maxWidth: CANVAS.w - CANVAS.safe.x * 2,
            display: "flex",
          }}
        >
          {story}
        </div>
      </div>
    </div>
  );
}
