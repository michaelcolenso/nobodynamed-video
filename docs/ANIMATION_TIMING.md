# Animation and timing system

The video is not four hard-cut scenes. It is one continuous 30 fps composition sampled by
Python and painted by Satori. The scene names remain as editorial buckets, but every visible
property comes from the shared hyperframe program in `render/programs.py`.

## Motion thesis

The design uses **editorial motion**, not decorative motion. Every transition answers one of
five viewer questions in order:

1. **What is this?** The name and diagnosis are readable on frame zero.
2. **What happened?** The historical curve travels from 1880 to the current year.
3. **Where did it land?** The tracer transfers into a colored landing dot and count.
4. **Why should I believe it?** Evidence cards and narrative recompose into the lower canvas.
5. **What next?** The footer resolves, then the final 750 ms returns to the opening hook.

Movement is restrained to opacity, position, scale, line growth, and breathing radii. The
system deliberately avoids random particles, elastic text, simulated camera shake, and other
effects that would weaken the archival/data-first voice.

## Authored 11-second beat sheet

Approved stories between 9 and 14 seconds are time-warped onto this canonical timeline, so
the relative choreography remains stable.

| Time | Beat | Motion |
|---:|---|---|
| 0.00 s | Cover / hook | Header and diagnosis are fully opaque; diagnosis begins a 10 px upward settle so the opening is alive without weakening thumbnail contrast. |
| 0.00–0.85 s | Focus pull | The diagnosis settles, chart rises 24 px into place, and grid resolves fractionally behind the container. |
| 0.30–6.00 s | Historical journey | The curve draws with a time-domain speed map; a breathing tracer and milestone-aware decade label make elapsed history legible. |
| ~peak | Peak proof | The peak label scales from 92% while fading in, attached to the tracer's remapped segment rather than a naïve year fraction. |
| 5.85–6.45 s | Landing handoff | The live tracer cross-fades into the terminal dot; count-up, one-shot ring, then low-amplitude halo establish the current value. |
| 6.10–6.90 s | Recompose | Chart contracts downward, diagnosis recedes slightly, and space opens for proof. |
| 6.70–7.80 s | Evidence cascade | Three cards rise 22 px, scale 94→100%, and arrive 150 ms apart. |
| 8.00–9.30 s | Narrative | The narrative rises while its horizontal rule draws left-to-right; supporting copy follows rather than competing for attention. |
| 9.50–10.10 s | CTA | Footer fades in and its fixed-center status dot breathes continuously. |
| final 0.75 s | Loop bridge | A background wipe restores the opening hook over the stable final composition, producing a readable seamless loop. |

## Curve pacing

The Python layer may insert render-only sub-year samples around a one-hit spike. Those samples
ease both the rise and collapse and add a brief peak hold without changing the underlying SSA
record. The TypeScript layer then computes a content-aware time map:

- long pre-appearance flatlines receive a capped fast-travel budget;
- first appearance, peak, steepest collapse, and recent history receive landmark weight;
- slope contributes time, but normalization prevents one extreme segment from owning the cut;
- dense one-hit samples receive an authored beat budget;
- the resulting cumulative position is Gaussian-smoothed at 120 Hz before 30 fps sampling.

This is intentionally **not constant-speed path drawing**. Constant speed makes a century of
zeros consume the same attention as the event that defines the story. It is also not a chain
of per-year easings, which introduces a visible velocity corner at every annual boundary.

## Continuity rules

- Any element that appears on screen must have bounded frame-to-frame alpha and geometry deltas.
- A geometry reset is permitted only while its corresponding alpha is effectively zero.
- The tracer and terminal dot must overlap during handoff.
- Breathing loops use raised cosines, never triangle waves, so velocity and acceleration remain
  continuous at extrema.
- Recomposition uses `smootherstep`, giving zero velocity and acceleration at both ends.
- Frame zero must remain a strong standalone cover while differing visibly from frames one and
  two; hidden-property changes do not count.
- The last story frame must restore the opening composition without mutating the stable canvas
  beneath it.

## Testing strategy

`tests/test_program_smoothness.py` samples every scalar channel at the actual 30 fps cadence and
asserts per-frame bounds. It also asserts semantic beat ordering, an opaque-but-moving opening,
the tracer/dot overlap, monotonic count-up, and staggered card settlement. The Node tests guard
the curve cache identity, milestone labels, and one-hit tracer velocity. Golden PNG hashes remain
the final visual contract after an intentional review and regeneration.

When editing timing, change the authored tracks first, run Python and Node continuity tests, then
render keyframes at approximately 0.0, 0.8, 3.0, 6.2, 7.8, 9.8, and the final frame. Never tune
only one screenshot: motion quality lives in the derivatives between frames.
