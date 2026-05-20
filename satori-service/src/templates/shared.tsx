// Brand tokens — canonical source of truth. Do not modify without updating AGENTS.md.

export const COLORS = {
  bg:      "#14110E",
  ink:     "#E8E0D4",
  fade:    "#B5B0A0",
  crimson: "#A21F1F",
  emerald: "#059669",
  rule:    "#2A2622",
} as const;

export const TYPE = {
  display: { family: "Source Serif 4 Black", weight: 900 },
  body:    { family: "Source Serif 4",        weight: 400 },
} as const;

export const RAMP = {
  display: [128, 96, 72, 56],
  body:    [48, 36, 28, 22, 18],
} as const;

// 1080×1920 canvas; safe area avoids TikTok UI overlays.
export const CANVAS = {
  w: 1080,
  h: 1920,
  safe: { top: 220, bottom: 280, x: 80 },
} as const;

// ── Tier badge ────────────────────────────────────────────────────────────────

export type Tier =
  | "extinct"
  | "critical"
  | "declining"
  | "stable"
  | "rising"
  | "resurrected";

const TIER_COLORS: Record<Tier, { bg: string; text: string }> = {
  extinct:     { bg: COLORS.crimson, text: COLORS.ink },
  critical:    { bg: COLORS.crimson, text: COLORS.ink },
  declining:   { bg: "#7C3A00",      text: COLORS.ink },
  stable:      { bg: "#2A2622",      text: COLORS.fade },
  rising:      { bg: COLORS.emerald, text: COLORS.ink },
  resurrected: { bg: COLORS.emerald, text: COLORS.ink },
};

export function TierBadge({ tier }: { tier: Tier }) {
  const { bg, text } = TIER_COLORS[tier];
  const label = tier.toUpperCase();
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        backgroundColor: bg,
        borderRadius: 8,
        paddingTop: 10,
        paddingBottom: 10,
        paddingLeft: 24,
        paddingRight: 24,
      }}
    >
      <span
        style={{
          fontFamily: TYPE.display.family,
          fontWeight: TYPE.display.weight,
          fontSize: RAMP.body[3],
          color: text,
          letterSpacing: 3,
        }}
      >
        {label}
      </span>
    </div>
  );
}
