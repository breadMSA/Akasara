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
    "capabilityUnderGrant",
    "FEATURE_SPACE", "CHANNELS", "DIM", "WINDOW_MS", "STRIDE_MS", "NOMINAL_RATE", "FULL_SCALE",
    "recognise", "motionEnergy", "EVENT_SPACE", "T0", "T0_EVENTS", "T0_ENTER", "T0_EXIT",
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

/** Found on a real phone: a grant with `include t_wall_ms` left unchecked
 *  exported frames with no wall time under a descriptor still declaring
 *  rtc:true, and the suite failed the capture on R-5.1. Withholding a field is
 *  the gate working; producing an inconsistent capture is not. */
test("a grant withholding t_wall_ms still exports a conformant capture (R-5.1)", () => {
  const state = makeState({ bridgeUri: "ws://127.0.0.1:8765" });
  const grant = { fields: { t_wall_ms: false, quality: true, session_id: true } };
  const cap = app.capabilityUnderGrant(state, grant);
  assert.equal(cap.clock.rtc, false, "descriptor must not claim an RTC whose output is withheld");

  const frames = makeFrames(app.buildCapability(state)).map(({ t_wall_ms, ...f }) => f);
  const { code, out } = runSuite(cap, frames, app.runSelftest(cap.signal.sample_rate_hz));
  assert.equal(code, 0, `withholding wall time must not make the capture non-conformant:\n${out}`);

  // And the inverse must still be caught: keeping the field means declaring it.
  const kept = app.capabilityUnderGrant(state, { fields: { t_wall_ms: true } });
  assert.equal(kept.clock.rtc, true);
  const stripped = runSuite(kept, frames, app.runSelftest(kept.signal.sample_rate_hz));
  assert.equal(stripped.code, 1);
  assert.match(stripped.out, /R-5\.1/);
});

/* ------------------------------------------------------------------ §3 T0 --
 * The tier that had no implementation and, as it turned out, no wire format.
 * These drive the recogniser over a synthetic still→move→still trace, then put
 * the resulting mixed capture through the real suite.
 */

/** rest, then movement, then rest — in the units the recogniser sees. */
function makeMixedCapture(cap, { restFrames = 6, moveFrames = 10 } = {}) {
  const rec = { seq: 0, moving: false, startNs: 0, shortRuns: 0 };
  const records = [];
  const events = [];
  const plan = [
    ...new Array(restFrames).fill(0.005),                 // below T0_EXIT
    ...new Array(moveFrames).fill(0.35),                  // above T0_ENTER
    ...new Array(restFrames).fill(0.005),
  ];
  plan.forEach((rms, i) => {
    const values = new Array(cap.t1.dim);
    for (let c = 0; c < cap.signal.channels; c++) {
      values[2 * c] = rms;          // channel-major: [RMS, WL] per channel
      values[2 * c + 1] = rms / 2;
    }
    const frame = {
      tier: "t1",
      t_mono_ns: (i + 1) * cap.t1.stride_ms * 1e6,
      t_wall_ms: 1785000000000 + i * cap.t1.stride_ms,
      session_id: "s-test0001",
      seq: i,
      feature_space: cap.t1.feature_space,
      values,
      quality: new Array(cap.signal.channels).fill(0.97),
    };
    records.push(frame);
    for (const ev of app.recognise(rec, frame)) { records.push(ev); events.push(ev); }
  });
  return { records, events, rec };
}

test("the recogniser fires one onset and one offset, with a real duration", () => {
  const cap = app.buildCapability(makeState({ bridgeUri: "ws://127.0.0.1:8765" }));
  const { events } = makeMixedCapture(cap);
  assert.equal(events.length, 2, "hysteresis must not chatter on a clean step");
  assert.equal(events[0].code, app.T0.MOVEMENT_ONSET);
  assert.equal(events[1].code, app.T0.MOVEMENT_OFFSET);
  // 10 move frames at 100 ms stride, offset fires on the first frame back at rest.
  assert.ok(events[1].duration_ms >= 1000 && events[1].duration_ms <= 1200,
    `duration ${events[1].duration_ms} ms is not the movement it measured`);
  // R-3.2.1: the T0 counter is its own.
  assert.deepEqual(events.map((e) => e.seq), [0, 1]);
  // R-3.2.1: a threshold detector declares no posterior rather than inventing 1.0.
  assert.ok(events.every((e) => e.confidence === undefined));
  assert.equal(cap.t0.confidence, false);
});

test("hysteresis is what stops the chatter, and a single threshold would not", () => {
  // A signal sitting between the two thresholds must produce NOTHING after the
  // first transition — that is the whole reason there are two numbers.
  const cap = app.buildCapability(makeState());
  const rec = { seq: 0, moving: false, startNs: 0, shortRuns: 0 };
  const between = (app.T0_ENTER + app.T0_EXIT) / 2;
  let fired = 0;
  for (let i = 0; i < 30; i++) {
    const values = new Array(cap.t1.dim).fill(0);
    for (let c = 0; c < cap.signal.channels; c++) values[2 * c] = between;
    fired += app.recognise(rec, {
      t_mono_ns: (i + 1) * 1e8, t_wall_ms: 1785000000000 + i, session_id: "s", seq: i,
      values, quality: [1, 1, 1, 1, 1, 1],
    }).length;
  }
  assert.equal(fired, 0, "a level inside the hysteresis band must not emit events");
  assert.equal(rec.moving, false);
});

test("a mixed T1+T0 capture is CONFORMANT and the citations resolve (R-3.2.2)", () => {
  const cap = app.buildCapability(makeState({ bridgeUri: "ws://127.0.0.1:8765" }));
  const { records } = makeMixedCapture(cap);
  const { code, out } = runSuite(cap, records, app.runSelftest(cap.signal.sample_rate_hz));
  assert.equal(code, 0, `mixed capture must be conformant:\n${out}`);
  assert.match(out, /PASS\s+R-3\.2\.2/);
  assert.match(out, /PASS\s+R-3\.2\s/);
});

test("an event citing a frame that is not in the capture FAILS R-3.2.2", () => {
  const cap = app.buildCapability(makeState({ bridgeUri: "ws://127.0.0.1:8765" }));
  const { records } = makeMixedCapture(cap);
  const ev = records.find((r) => r.tier === "t0");
  ev.t1_seq = 9999;                                  // a decision with no evidence
  const { code, out } = runSuite(cap, records, app.runSelftest(cap.signal.sample_rate_hz));
  assert.equal(code, 1);
  assert.match(out, /FAIL\s+R-3\.2\.2/);
});

test("an event citing a frame that ends after it FAILS R-3.2.2", () => {
  const cap = app.buildCapability(makeState({ bridgeUri: "ws://127.0.0.1:8765" }));
  const { records } = makeMixedCapture(cap);
  const t1 = records.filter((r) => r.tier === "t1");
  const ev = records.find((r) => r.tier === "t0");
  ev.t1_seq = t1[t1.length - 1].seq;                 // the future, cited as evidence
  const { code, out } = runSuite(cap, records, app.runSelftest(cap.signal.sample_rate_hz));
  assert.equal(code, 1);
  assert.match(out, /FAIL\s+R-3\.2\.2/);
});

test("an unregistered event code FAILS R-3.2.1", () => {
  const cap = app.buildCapability(makeState({ bridgeUri: "ws://127.0.0.1:8765" }));
  const { records } = makeMixedCapture(cap);
  records.find((r) => r.tier === "t0").code = 4242;
  const { code, out } = runSuite(cap, records, app.runSelftest(cap.signal.sample_rate_hz));
  assert.equal(code, 1);
  assert.match(out, /FAIL\s+R-3\.2\.1/);
});

test("quality is per channel, not per feature dimension (R-5.6)", () => {
  const cap = app.buildCapability(makeState({ bridgeUri: "ws://127.0.0.1:8765" }));
  const frames = makeFrames(cap);
  frames[0].quality = new Array(cap.t1.dim).fill(0.9);   // the mistake the clause exists for
  const { code, out } = runSuite(cap, frames, app.runSelftest(cap.signal.sample_rate_hz));
  assert.equal(code, 1);
  assert.match(out, /R-5\.6/);
});
