import assert from "node:assert/strict";
import test from "node:test";

import { selectTracerYearLabel, smoothPathD, speedCurveCacheKey } from "./canvas";

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

// [year, count] pairs — the exact output of _prepare_render_series
// (programs.py) for a Kunta-shaped one-hit spike (peak 215 in 1977, ~gone by
// 1980, zero-filled 1880-2024): flatline, eased rise into the peak, a brief
// hold, an eased fall back down, then flatline again. Captured directly from
// the real Python function rather than hand-reconstructed in TS, so this
// fixture can't silently drift from what production actually renders.
// Regenerate with:
//   uv run python3 -c "
//   from nobodynamed_video.models import YearCount
//   from nobodynamed_video.render.programs import _prepare_render_series
//   raw = [YearCount(year=y, count=0) for y in range(1880, 1976)]
//   raw += [YearCount(year=1976, count=8), YearCount(year=1977, count=215),
//           YearCount(year=1978, count=34), YearCount(year=1979, count=16),
//           YearCount(year=1980, count=6)]
//   raw += [YearCount(year=y, count=0) for y in range(1981, 2025)]
//   expanded = _prepare_render_series(raw, peak_year=1977, peak_count=215)
//   print([[round(p.year, 4), round(p.count, 4)] for p in expanded])"
// prettier-ignore
const ONE_HIT_SPIKE_SERIES: Array<[number, number]> = [
  [1880, 0], [1881, 0], [1882, 0], [1883, 0], [1884, 0], [1885, 0], [1886, 0], [1887, 0], [1888, 0], [1889, 0],
  [1890, 0], [1891, 0], [1892, 0], [1893, 0], [1894, 0], [1895, 0], [1896, 0], [1897, 0], [1898, 0], [1899, 0],
  [1900, 0], [1901, 0], [1902, 0], [1903, 0], [1904, 0], [1905, 0], [1906, 0], [1907, 0], [1908, 0], [1909, 0],
  [1910, 0], [1911, 0], [1912, 0], [1913, 0], [1914, 0], [1915, 0], [1916, 0], [1917, 0], [1918, 0], [1919, 0],
  [1920, 0], [1921, 0], [1922, 0], [1923, 0], [1924, 0], [1925, 0], [1926, 0], [1927, 0], [1928, 0], [1929, 0],
  [1930, 0], [1931, 0], [1932, 0], [1933, 0], [1934, 0], [1935, 0], [1936, 0], [1937, 0], [1938, 0], [1939, 0],
  [1940, 0], [1941, 0], [1942, 0], [1943, 0], [1944, 0], [1945, 0], [1946, 0], [1947, 0], [1948, 0], [1949, 0],
  [1950, 0], [1951, 0], [1952, 0], [1953, 0], [1954, 0], [1955, 0], [1956, 0], [1957, 0], [1958, 0], [1959, 0],
  [1960, 0], [1961, 0], [1962, 0], [1963, 0], [1964, 0], [1965, 0], [1966, 0], [1967, 0], [1968, 0], [1969, 0],
  [1970, 0], [1971, 0], [1972, 0], [1973, 0], [1974, 0], [1975, 0],
  [1976, 8], [1976.0833, 9.0532], [1976.1667, 15.3472], [1976.25, 29.4277], [1976.3333, 51.4444],
  [1976.4167, 79.7502], [1976.5, 111.5], [1976.5833, 143.2498], [1976.6667, 171.5556],
  [1976.75, 193.5723], [1976.8333, 207.6528], [1976.9167, 213.9468], [1977, 215],
  [1977.0333, 215], [1977.0667, 215], [1977.1, 215], [1977.1333, 215], [1977.1667, 215], [1977.2, 215],
  [1977.3, 212.0945], [1977.4, 196.2637], [1977.5, 165.1874], [1977.6, 124.5], [1977.7, 83.8126],
  [1977.8, 52.7363], [1977.9, 36.9055], [1978, 34], [1979, 16], [1980, 6],
  [1981, 0], [1982, 0], [1983, 0], [1984, 0], [1985, 0], [1986, 0], [1987, 0], [1988, 0], [1989, 0], [1990, 0],
  [1991, 0], [1992, 0], [1993, 0], [1994, 0], [1995, 0], [1996, 0], [1997, 0], [1998, 0], [1999, 0], [2000, 0],
  [2001, 0], [2002, 0], [2003, 0], [2004, 0], [2005, 0], [2006, 0], [2007, 0], [2008, 0], [2009, 0], [2010, 0],
  [2011, 0], [2012, 0], [2013, 0], [2014, 0], [2015, 0], [2016, 0], [2017, 0], [2018, 0], [2019, 0], [2020, 0],
  [2021, 0], [2022, 0], [2023, 0], [2024, 0],
];

function buildOneHitLikeSeries(): Array<{ x: number; y: number }> {
  const CHART_WIDTH = 920;
  const CHART_HEIGHT = 760;
  const minYear = ONE_HIT_SPIKE_SERIES[0][0];
  const maxYear = ONE_HIT_SPIKE_SERIES[ONE_HIT_SPIKE_SERIES.length - 1][0];
  const maxCount = Math.max(...ONE_HIT_SPIKE_SERIES.map(([, count]) => count));
  const toX = (year: number) => ((year - minYear) / (maxYear - minYear)) * CHART_WIDTH;
  const toY = (count: number) => CHART_HEIGHT - (count / maxCount) * CHART_HEIGHT;
  return ONE_HIT_SPIKE_SERIES.map(([year, count]) => ({ x: toX(year), y: toY(count) }));
}

test("one-hit spike tracer motion has no single-frame velocity spike", () => {
  const points = buildOneHitLikeSeries();
  const drawDurationS = 4.2;
  const fps = 30;
  const totalFrames = Math.round(drawDurationS * fps);

  const speeds: number[] = [];
  let prev = smoothPathD(points, 0, drawDurationS);
  for (let f = 1; f <= totalFrames; f++) {
    const cur = smoothPathD(points, f / totalFrames, drawDurationS);
    speeds.push(Math.hypot(cur.tracerX - prev.tracerX, cur.tracerY - prev.tracerY));
    prev = cur;
  }

  const maxSpeed = Math.max(...speeds);
  const jerks = speeds.slice(1).map((s, i) => Math.abs(s - speeds[i]));
  const maxJerk = Math.max(...jerks);

  // A "freeze then snap": one segment claims a wildly disproportionate share
  // of the draw (canvas.tsx#computeSpeedCurve's spike/collapse/slope cost
  // weights stacking on a single raw segment) reads on screen as a jerk
  // approaching, or exceeding, the peak speed itself. Measured on this exact
  // fixture (real _prepare_render_series output, full 1880-2024 annual
  // series): un-eased fall (pre-fix) = 56.0% of peak speed, eased fall
  // (current) = 43.8%. 50% sits between the two with margin on both sides —
  // loose enough not to flake on legitimate data, tight enough to catch a
  // regression back to an un-eased fall.
  assert.ok(
    maxJerk < maxSpeed * 0.5,
    `max single-frame jerk ${maxJerk.toFixed(1)}px exceeds 50% of peak speed ${maxSpeed.toFixed(1)}px/frame — the tracer is stalling then snapping`,
  );
});
