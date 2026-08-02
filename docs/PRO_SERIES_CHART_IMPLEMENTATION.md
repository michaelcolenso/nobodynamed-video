# Pro-Series Chart Animation Implementation Brief

## Objective

Make the chart feel editorially directed rather than merely smooth. The animation should spend time on story landmarks, reduce transient label noise, keep annotations attached to the tracer, and preserve deterministic rendering.

## Phase 1 — focused improvements

1. Hash the complete chart series for speed-curve cache identity. Endpoint-only keys can collide for names with the same domain and final count.
2. Return the tracer's segment-space position from `smoothPathD` so annotations use the same remapped timing as the rendered path.
3. Replace rapidly changing annual tracer labels with decade labels during fast travel and exact labels near first appearance, peak, steepest decline, and current year.
4. Trigger peak annotation from actual tracer arrival instead of linear year fraction.
5. Keep these changes isolated from renderer clustering, D1 retry behavior, batch cache semantics, QC threshold changes, and golden-frame updates.

## Phase 2 — editorial choreography

1. Introduce a preprocessing-layer `ChartLandmarks` model containing first appearance, breakout, peak, steepest decline, revival, and current year.
2. Define motion presets for one-hit wonder, long decline, resurrection, stable classic, and modern ascent.
3. Allocate draw time by semantic landmark rather than slope alone.
4. Add declared authored holds so QC distinguishes intentional pauses from accidental frozen frames.
5. Delay area fill until the line has nearly completed or the current-year dot lands.
6. Add nice-number y-axis ticks and reserve a gutter outside the plot for labels.
7. Preserve horizontal chronology during recompose; avoid remapping x positions while the chart changes layout.
8. Add contact-sheet and compressed-output review fixtures for each archetype.

## Acceptance criteria

- Speed curves cannot leak between distinct series.
- Tracer labels change at a readable cadence and show exact landmark years.
- Peak callout begins only when the tracer reaches the peak.
- Existing 11-second duration and deterministic frame planning remain unchanged.
- No renderer clustering or data-source behavior changes are included.
- TypeScript tests cover cache identity and tracer-year selection.
- Existing Python motion continuity tests remain green.

## Follow-up validation set

Render and inspect at least one fixture from each shape:

- sudden spike and collapse
- gradual long decline
- resurrection
- stable classic
- recent rapid rise

Inspect frames near first appearance, peak, collapse, current-year landing, recompose, and endcard. Compare both master frames and a realistic social-media transcode.