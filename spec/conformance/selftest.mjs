#!/usr/bin/env node
/**
 * ase.selftest.v1 — the fixed synthetic input of ASE-0.1 R-5.7.
 *
 * Generates the exact signal a device must run its production T1 transform
 * over. Deterministic, dependency-free, and reproducible in any language from
 * the definition in §5: a vendor implementing this on-device does not need
 * this file, only the formula.
 *
 * Usage:
 *   node selftest.mjs <channels> <sample_rate_hz>          # -> JSON [ch][n]
 *   node selftest.mjs <channels> <sample_rate_hz> --csv    # -> CSV, n per row
 *
 * Duration is fixed at 2.000 s.
 */

import { pathToFileURL } from "node:url";

export const DURATION_S = 2.0;

/** xorshift32, seeded per channel with c+1. Output scaled to [-1, 1]. */
function* xorshift32(seed) {
  let x = seed >>> 0;
  for (;;) {
    x ^= (x << 13) >>> 0;
    x >>>= 0;
    x ^= x >>> 17;
    x ^= (x << 5) >>> 0;
    x >>>= 0;
    yield (x / 0xffffffff) * 2 - 1;
  }
}

/**
 * @param {number} channels
 * @param {number} fs sample rate, Hz
 * @returns {number[][]} [channel][sample], full-scale units
 */
export function selftestInput(channels, fs) {
  const n = Math.round(DURATION_S * fs);
  const out = [];
  for (let c = 0; c < channels; c++) {
    const rng = xorshift32(c + 1);
    const row = new Array(n);
    for (let i = 0; i < n; i++) {
      const r = rng.next().value;
      row[i] =
        0.5 * Math.sin((2 * Math.PI * (20 + 7 * c) * i) / fs) +
        0.2 * Math.sin((2 * Math.PI * (150 + 11 * c) * i) / fs) +
        0.05 * r;
    }
    out.push(row);
  }
  return out;
}

/** Compare a device's reported self-test output against the descriptor. */
export function compareSelftest(actual, expected, tolerance) {
  if (!Array.isArray(actual) || actual.length !== expected.length) {
    return { ok: false, reason: `length ${actual?.length} vs expected ${expected.length}` };
  }
  let worst = 0, at = -1;
  for (let i = 0; i < expected.length; i++) {
    const d = Math.abs(actual[i] - expected[i]);
    if (d > worst) { worst = d; at = i; }
  }
  return worst <= tolerance
    ? { ok: true, worst }
    : { ok: false, worst, at, reason: `dim ${at} differs by ${worst.toExponential(3)} > tolerance ${tolerance}` };
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const [chArg, fsArg, fmt] = process.argv.slice(2);
  if (!chArg || !fsArg) {
    console.error("usage: node selftest.mjs <channels> <sample_rate_hz> [--csv]");
    process.exit(2);
  }
  const data = selftestInput(Number(chArg), Number(fsArg));
  if (fmt === "--csv") {
    const n = data[0].length;
    for (let i = 0; i < n; i++) console.log(data.map((row) => row[i].toFixed(6)).join(","));
  } else {
    console.log(JSON.stringify(data));
  }
}
