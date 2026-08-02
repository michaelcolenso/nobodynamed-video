import assert from "node:assert/strict";
import test from "node:test";

import { selectTracerYearLabel, speedCurveCacheKey } from "./canvas";

test("speed cache identity includes interior series points", () => {
  const first = [
    { x: 0, y: 100 },
    { x: 50, y: 10 },
    { x: 100, y: 100 },
  ];
  const second = [
    { x: 0, y: 100 },
    { x: 50, y: 80 },
    { x: 100, y: 100 },
  ];

  assert.notEqual(speedCurveCacheKey(first, 4.2), speedCurveCacheKey(second, 4.2));
});

test("year readout uses decades during fast travel", () => {
  assert.equal(selectTracerYearLabel(1936, [1977, 1989, 1991, 2024]), 1940);
});

test("year readout locks to story milestones", () => {
  assert.equal(selectTracerYearLabel(1988, [1977, 1989, 1991, 2024]), 1989);
  assert.equal(selectTracerYearLabel(2024, [1977, 1989, 1991, 2024]), 2024);
});
