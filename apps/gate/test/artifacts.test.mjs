/**
 * The claim under test: the artefacts this app exports pass the spec's own
 * conformance suite. Not a mock of them — the pure half of index.html is lifted
 * out of the file and executed, so a change to the transform or the descriptor
 * that breaks conformance breaks this test.
 *
 * Run:  node --test apps/gate/test/
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, writeFileSync, mkdtempSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { selftestInput } from "../../../spec/conformance/selftest.mjs";

const here = dirname(fileURLToPath(import.meta.url));
const APP = join(here, "..", "index.html");
const CHECK = join(here, "..", "..", "..", "spec", "conformance", "check.mjs");

/** Lift the DOM-free region of the app: everything from the self-test port down
 *  to the build id. Anything below that touches the page and is not under test
 *  here. */
function loadPureModule() {
  const html = readFileSync(APP, "utf8");
  const START = "const DURATION_S = 2.0;";
  const END = 'const BUILD = "0.1.0";';
  const a = html.indexOf(START);
  const b = html.indexOf(END);
  assert.ok(a > 0 && b > a, "index.html no longer contains the expected pure region");
  const src = html.slice(a, b + END.length);
  const exportNames = [
    "DURATION_S", "selftestInput", "t1Transform", "runSelftest", "buildCapability",
    "FEATURE_SPACE", "CHANNELS", "DIM", "WINDOW_MS", "STRIDE_MS", "NOMINAL_RATE", "FULL_SCALE",
  ];
  return new Function(`${src}\nreturn {${exportNames.join(",")}};`)();
}

const app = loadPureModule();

function makeState(overrides = {}) {
  return {
    sourceKind: "sim",
    donCount: 3,
    measuredRate: 99.4,
    bridgeUri: null,
    ...overrides,
  };
}

/** Frames shaped exactly as emitFrame() produces them. */
function makeFrames(cap, n = 40) {
  const input = selftestInput(cap.signal.channels, cap.signal.sample_rate_hz);
  const per = Math.floor(input[0].length / n);
  const frames = [];
  for (let i = 0; i < n; i++) {
    const slice = input.map((row) => row.slice(i * per, (i + 1) * per));
    frames.push({
      tier: "t1",
      t_mono_ns: (i + 1) * cap.t1.stride_ms * 1e6,
      t_wall_ms: 1785000000000 + i * cap.t1.stride_ms,
      session_id: "s-test0001",
      seq: i,
      feature_space: cap.t1.feature_space,
      values: app.t1Transform(slice).map((v) => Number(v.toFixed(6))),
      quality: new Array(cap.signal.channels).fill(0.97),
    });
  }
  return frames;
}

function runSuite(cap, frames, selftestOut) {
  const dir = mkdtempSync(join(tmpdir(), "gate-"));
  const capPath = join(dir, "capability.json");
  const framesPath = join(dir, "frames.jsonl");
  const stPath = join(dir, "selftest.json");
  writeFileSync(capPath, JSON.stringify(cap, null, 2));
  writeFileSync(framesPath, frames.map((f) => JSON.stringify(f)).join("\n") + "\n");
  writeFileSync(stPath, JSON.stringify(selftestOut));
  const r = spawnSync(process.execPath, [CHECK, capPath, framesPath, stPath], { encoding: "utf8" });
  return { code: r.status, out: r.stdout + r.stderr };
}

test("the T1 transform is deterministic and shaped as declared", () => {
  const a = app.runSelftest(100);
  const b = app.runSelftest(100);
  assert.deepEqual(a, b, "same input, same output — R-5.4 pins nothing otherwise");
  assert.equal(a.length, app.DIM);
  assert.ok(a.every(Number.isFinite));
  // A different sample rate is a different acquisition, so a different vector.
  assert.notDeepEqual(a, app.runSelftest(60));
});

test("the self-test vector matches the descriptor it publishes (R-5.7)", () => {
  const cap = app.buildCapability(makeState());
  const actual = app.runSelftest(cap.signal.sample_rate_hz);
  assert.equal(actual.length, cap.t1.dim);
  const worst = Math.max(...actual.map((v, i) => Math.abs(v - cap.selftest.expected[i])));
  assert.ok(worst <= cap.selftest.tolerance, `worst |Δ| ${worst} exceeds ${cap.selftest.tolerance}`);
});

test("with the loopback bridge connected, the capture is CONFORMANT", () => {
  const cap = app.buildCapability(makeState({ bridgeUri: "ws://127.0.0.1:8765" }));
  const frames = makeFrames(cap);
  const { code, out } = runSuite(cap, frames, app.runSelftest(cap.signal.sample_rate_hz));
  assert.equal(code, 0, `suite reported failures:\n${out}`);
  assert.match(out, /CONFORMANT/);
});

test("without the bridge it fails R-7.1 and nothing else", () => {
  const cap = app.buildCapability(makeState());
  const frames = makeFrames(cap);
  const { code, out } = runSuite(cap, frames, app.runSelftest(cap.signal.sample_rate_hz));
  assert.equal(code, 1, "a browser with no loopback listener must not be reported conformant");
  const failed = out.split("\n").filter((l) => l.trim().startsWith("FAIL"));
  assert.equal(failed.length, 1, `expected exactly one failure, got:\n${failed.join("\n")}`);
  assert.match(failed[0], /R-7\.1/);
});

test("the simulated source is labelled in the descriptor and cannot pass as a capture", () => {
  const sim = app.buildCapability(makeState({ sourceKind: "sim" }));
  const imu = app.buildCapability(makeState({ sourceKind: "imu" }));
  assert.equal(sim["akasara.source"], "simulated");
  assert.equal(imu["akasara.source"], "device-imu");
  assert.notEqual(sim.model, imu.model);
});

test("quality is per channel, not per feature dimension (R-5.6)", () => {
  const cap = app.buildCapability(makeState({ bridgeUri: "ws://127.0.0.1:8765" }));
  const frames = makeFrames(cap);
  frames[0].quality = new Array(cap.t1.dim).fill(0.9);   // the mistake the clause exists for
  const { code, out } = runSuite(cap, frames, app.runSelftest(cap.signal.sample_rate_hz));
  assert.equal(code, 1);
  assert.match(out, /R-5\.6/);
});
