/**
 * The cued protocol: the thing that makes two devices' captures comparable.
 *
 * The claim under test is not that the UI works — it is that the cue a capture
 * carries means what a consumer will assume it means. Two properties do all the
 * work: a window is labelled only when it lies entirely inside a hold, and the
 * label leaves the device only under a grant that says it may.
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

const here = dirname(fileURLToPath(import.meta.url));
const APP = join(here, "..", "index.html");
const CHECK = join(here, "..", "..", "..", "spec", "conformance", "check.mjs");

/** Lift named top-level declarations out of the app. Same principle as
 *  artifacts.test.mjs: the real source runs, so a change to it that breaks
 *  these properties breaks the test rather than drifting past a copy. */
function lift(names, exportNames) {
  const html = readFileSync(APP, "utf8");
  const parts = names.map((n) => {
    const re = new RegExp(`^(?:const ${n} = \\[[\\s\\S]*?^\\];|function ${n}\\([\\s\\S]*?^\\})`, "m");
    const m = html.match(re);
    assert.ok(m, `index.html no longer declares ${n} at top level`);
    return m[0];
  });
  return new Function(`${parts.join("\n")}\nreturn {${exportNames.join(",")}};`)();
}

const app = lift(
  ["CUES", "cueForWindow", "buildSchedule", "pseudonym", "applyGrant"],
  ["CUES", "cueForWindow", "buildSchedule", "applyGrant"]
);

test("the schedule is decided up front and its holds never overlap", () => {
  const plan = app.buildSchedule(3000, 2000, 3, 1000);
  assert.equal(plan.length, app.CUES.length * 3);
  assert.ok(plan[0].from >= 1000 + 2000,
    "the first hold starts before the person has had a rest to read the instruction");
  for (let i = 1; i < plan.length; i++) {
    assert.ok(plan[i].from >= plan[i - 1].to,
      `hold ${i} starts before hold ${i - 1} ends`);
  }
  const ids = new Set(plan.map((p) => p.id));
  assert.equal(ids.size, app.CUES.length, "every cue appears in every rep");
});

test("a window is labelled only when it lies ENTIRELY inside the hold", () => {
  const cue = { id: 4, name: "x", from: 1000, to: 4000 };
  assert.ok(app.cueForWindow(cue, 1000, 1200), "fully inside, at the boundary");
  assert.ok(app.cueForWindow(cue, 3800, 4000), "fully inside, at the far boundary");
  assert.equal(app.cueForWindow(cue, 900, 1100), null, "straddles the start");
  assert.equal(app.cueForWindow(cue, 3900, 4100), null, "straddles the end");
  assert.equal(app.cueForWindow(null, 1000, 1200), null, "no cue running");
});

test("the cue leaves only under a grant that says it may", () => {
  const frames = [{
    tier: "t1", t_mono_ns: 1e8, t_wall_ms: 1785000000000,
    session_id: "s-1", seq: 0, feature_space: "f", values: [1], quality: [1],
    "akasara.cue": 7, "akasara.cue_name": "move left, then hold",
  }];
  const base = {
    max_frames: 10, released: 0, salt: "s",
    fields: { quality: true, session_id: true, t_wall_ms: true },
  };

  const withheld = app.applyGrant(frames, { ...base, fields: { ...base.fields, cue: false } });
  assert.equal(withheld[0]["akasara.cue"], undefined);
  assert.equal(withheld[0]["akasara.cue_name"], undefined);

  const granted = app.applyGrant(frames, { ...base, fields: { ...base.fields, cue: true } });
  assert.equal(granted[0]["akasara.cue"], 7);
  assert.equal(granted[0]["akasara.cue_name"], "move left, then hold");
});

test("withholding the cue cannot make the capture non-conformant", () => {
  // The lesson from the t_wall_ms defect: a privacy control that manufactures a
  // broken export is a bug in the gate, not a choice the user made. The cue is a
  // vendor extension, so this must hold by construction — the test is here to
  // keep it holding.
  const cap = JSON.parse(readFileSync(
    join(here, "..", "..", "..", "spec", "conformance", "vectors", "good.capability.json"), "utf8"));
  const raw = readFileSync(
    join(here, "..", "..", "..", "spec", "conformance", "vectors", "good.frames.jsonl"), "utf8")
    .trim().split("\n").map((l) => JSON.parse(l));

  for (const cue of [true, false]) {
    const frames = raw.map((f, i) =>
      cue ? { ...f, "akasara.cue": (i % 10) + 1, "akasara.cue_name": "x" } : f);
    const dir = mkdtempSync(join(tmpdir(), "gate-cue-"));
    const capPath = join(dir, "capability.json");
    const fPath = join(dir, "frames.jsonl");
    writeFileSync(capPath, JSON.stringify(cap));
    writeFileSync(fPath, frames.map((f) => JSON.stringify(f)).join("\n") + "\n");
    const r = spawnSync(process.execPath, [CHECK, capPath, fPath], { encoding: "utf8" });
    assert.equal(r.status, 0,
      `capture with cue=${cue} was rejected:\n${r.stdout}${r.stderr}`);
  }
});
