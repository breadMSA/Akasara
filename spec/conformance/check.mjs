#!/usr/bin/env node
/**
 * ASE-0.1 reference conformance suite.
 *
 * Usage:  node check.mjs <capability.json> <frames.jsonl>
 *
 * Zero dependencies, Node >= 18. Checks are keyed to the clause numbers in
 * ASE-0.1.md so a failure names the requirement it violates. Every check is
 * decidable from the two artefacts a vendor already has; nothing here needs
 * the device present, an account, or our permission.
 *
 * Exit 0 = conformant, 1 = non-conformant, 2 = could not run.
 */

import { readFileSync } from "node:fs";
import { compareSelftest } from "./selftest.mjs";

const results = [];
const pass = (id, msg) => results.push({ ok: true, id, msg });
const fail = (id, msg) => results.push({ ok: false, id, msg });
const warn = (id, msg) => results.push({ ok: null, id, msg });

function loadCapability(path) {
  const cap = JSON.parse(readFileSync(path, "utf8"));
  if (cap.ase_version !== "0.1") {
    console.error(`capability declares ase_version ${cap.ase_version}; this suite tests 0.1`);
    process.exit(2);
  }
  return cap;
}

function loadFrames(path) {
  return readFileSync(path, "utf8")
    .split("\n")
    .map((l) => l.trim())
    .filter(Boolean)
    .map((l, i) => {
      try {
        return JSON.parse(l);
      } catch {
        console.error(`frames line ${i + 1}: not valid JSON`);
        process.exit(2);
      }
    });
}

// ---------------------------------------------------------------- §4.2 montage
const SYSTEMS = ["ase.eeg.1020.v1", "ase.limb.v1", "ase.face.v1", "ase.opaque.v1"];
const SIDES = ["left", "right", "midline", "bilateral", "n/a"];
const ARRANGEMENTS = ["circumferential", "linear", "grid", "scattered", "single"];
const POS_KEYS = {
  "ase.eeg.1020.v1": ["label"],
  "ase.limb.v1": ["angle_deg", "axial_mm"],
  "ase.face.v1": ["muscle"],
};

function checkMontage(sig) {
  const m = sig.montage;
  if (typeof m === "string") {
    return fail("R-4.2", "signal.montage is a free string; 0.1 requires a structured descriptor");
  }
  if (!m || typeof m !== "object") {
    return fail("R-4.2", "signal.montage missing; devices are not montage-comparable without it");
  }
  if (!SYSTEMS.includes(m.system)) {
    return fail("R-4.2", `montage.system "${m.system}" is not a registered coordinate system`);
  }
  for (const [field, allowed] of [["side", SIDES], ["arrangement", ARRANGEMENTS]]) {
    if (!allowed.includes(m[field])) fail("R-4.2", `montage.${field} "${m[field]}" not in vocabulary`);
  }
  if (!m.site) fail("R-4.2", "montage.site missing");
  if (!m.reference) fail("R-4.2", "montage.reference missing");

  if (m.system === "ase.opaque.v1") {
    return warn("R-4.2", "montage system is ase.opaque.v1: conformant, but not montage-comparable with any device");
  }
  const need = POS_KEYS[m.system];
  const pos = m.positions;
  if (!Array.isArray(pos) || pos.length !== sig.channels) {
    return fail("R-4.2", `montage.positions has ${pos?.length ?? 0} entries for ${sig.channels} channels`);
  }
  const chans = new Set(pos.map((p) => p.ch));
  if (chans.size !== pos.length) fail("R-4.2", "montage.positions contains duplicate ch indices");
  const bad = pos.find((p) => need.some((k) => p[k] === undefined));
  if (bad) {
    return fail("R-4.2", `montage.positions ch ${bad.ch} missing ${need.join("/")} required by ${m.system}`);
  }
  pass("R-4.2", `montage ${m.system} ${m.site}/${m.side}, ${pos.length} positions — comparable`);
}

// ---------------------------------------------------------------- §5.7 self-test
function checkSelftest(cap, actual) {
  const st = cap.selftest;
  if (!st) {
    return fail("R-5.7", "no selftest block; R-5.4 cannot be verified across a firmware update without one");
  }
  if (st.input !== "ase.selftest.v1") return fail("R-5.7", `selftest.input "${st.input}" unrecognised`);
  if (!Array.isArray(st.expected) || st.expected.length === 0) {
    return fail("R-5.7", "selftest.expected missing or empty");
  }
  if (cap.t1?.dim !== undefined && st.expected.length !== cap.t1.dim) {
    fail("R-5.7", `selftest.expected has ${st.expected.length} values, declared t1.dim is ${cap.t1.dim}`);
  }
  if (!(st.tolerance > 0)) fail("R-5.7", "selftest.tolerance must be positive");
  if (!st.expected.every((v) => Number.isFinite(v))) fail("R-5.7", "selftest.expected contains non-finite values");

  if (actual) {
    const r = compareSelftest(actual, st.expected, st.tolerance);
    r.ok
      ? pass("R-5.7", `device self-test output matches descriptor (worst |Δ| ${r.worst.toExponential(2)})`)
      : fail("R-5.7", `device self-test output does not match its own descriptor: ${r.reason}`);
  } else {
    pass("R-5.7", `selftest declared, ${st.expected.length} dims, tol ${st.tolerance}`);
  }
}

// ---------------------------------------------------- §5.4 across firmware versions
function compareVersions(a, b) {
  console.log(
    `ASE-0.1 cross-version check — ${a.vendor} ${a.model}: fw ${a.firmware} vs fw ${b.firmware}\n`
  );
  if (a.vendor !== b.vendor || a.model !== b.model) {
    console.error("refusing to compare two different models");
    process.exit(2);
  }
  if (a.firmware === b.firmware) warn("R-5.4", "both captures report the same firmware version");

  const spaceSame = a.t1?.feature_space === b.t1?.feature_space;
  const stA = a.selftest, stB = b.selftest;
  if (!stA || !stB) {
    fail("R-5.7", "both descriptors need a selftest block for a cross-version verdict");
  } else {
    const tol = Math.max(stA.tolerance, stB.tolerance);
    const r = compareSelftest(stB.expected, stA.expected, tol);
    if (spaceSame && !r.ok) {
      fail("R-5.4", `feature_space "${a.t1.feature_space}" unchanged but the transform moved: ${r.reason} — every encoder fitted against it is now silently wrong`);
    } else if (spaceSame && r.ok) {
      pass("R-5.4", "feature_space unchanged and transform verifiably identical");
    } else if (!spaceSame && !r.ok) {
      pass("R-5.4", `transform changed and feature_space was re-pinned ("${a.t1?.feature_space}" -> "${b.t1?.feature_space}")`);
    } else {
      warn("R-5.4", "feature_space changed but the transform is identical — harmless, invalidates downstream fits for nothing");
    }
  }
  if (!spaceSame) {
    const tiersLost = (a.tiers ?? []).filter((t) => !(b.tiers ?? []).includes(t));
    if (tiersLost.length) fail("R-7.5", `update removed tier(s): ${tiersLost.join(", ")}`);
    const transLost = (a.transport ?? []).filter((t) => !(b.transport ?? []).includes(t));
    if (transLost.length) fail("R-7.5", `update removed transport(s): ${transLost.join(", ")}`);
    if (b.previous_feature_space !== a.t1?.feature_space) {
      fail("R-7.5.1", "new firmware does not declare previous_feature_space; the refit window is unverifiable");
    } else pass("R-7.5.1", `previous feature space "${b.previous_feature_space}" still selectable`);
  }
}

// ---------------------------------------------------------------- §4, §7
function checkCapability(cap) {
  const tiers = cap.tiers ?? [];
  if (tiers.includes("t1")) pass("R-3", "T1 declared");
  else fail("R-3", "T1 is not in tiers[]; T0-only export is not ASE-Core conformant");

  for (const field of ["vendor", "model", "firmware"]) {
    if (!cap[field]) fail("R-4.1", `capability missing ${field}`);
  }
  if (!Array.isArray(cap.transport) || cap.transport.length === 0) {
    fail("R-4.1", "capability declares no transport");
  }

  const sig = cap.signal ?? {};
  if (sig.kind && sig.channels > 0 && sig.sample_rate_hz > 0) {
    pass("R-4.1", `signal ${sig.kind}, ${sig.channels}ch @ ${sig.sample_rate_hz}Hz`);
  } else {
    fail("R-4.1", "signal.kind / channels / sample_rate_hz incomplete");
  }
  checkMontage(sig);

  const t1 = cap.t1 ?? null;
  if (!t1) {
    fail("R-4.1", "no t1 block describes the exported feature space");
  } else {
    for (const field of ["feature_space", "dim", "window_ms", "stride_ms", "producer", "documentation"]) {
      if (t1[field] === undefined) fail("R-4.1", `t1.${field} missing`);
    }
    if (t1.producer === "model" && !/[.:@\-_]v?\d/.test(String(t1.feature_space))) {
      warn("R-5.4", `feature_space "${t1.feature_space}" carries no version token; a model update will silently invalidate every fitted encoder`);
    }
    if (t1.latency_max_ms === undefined) fail("R-5.3", "t1.latency_max_ms not documented");
    else pass("R-5.3", `worst-case latency documented (${t1.latency_max_ms} ms)`);

    if (t1.adaptive === true && t1.non_adaptive_mode !== true) {
      fail("R-5.5", "exported T1 is per-user adaptive with no non-adaptive mode offered");
    }
  }

  // §7 — access, locality, rights. Checked for every device, including one that
  // fails §3: a T0-only device's terms are exactly what needs to be on record.
  if (cap.requires_network === true) fail("R-7.1", "T1 export requires network; local interface is mandatory");
  else pass("R-7.1", "no network required for export");
  if (cap.requires_account === true) fail("R-7.1", "T1 export requires an account");
  const local = (cap.transport ?? []).some((t) =>
    /^(usb|ble|serial|loopback)/i.test(t) || /(localhost|127\.0\.0\.1)/.test(t)
  );
  if (local) pass("R-7.1", "at least one local transport");
  else fail("R-7.1", "no local transport (USB / BLE / loopback) among transports");

  if (cap.developer_gate === true) {
    fail("R-7.3", "T1 access gated behind an approved-developer programme; must be user-grantable");
  } else pass("R-7.3", "access is user-grantable");

  const cross = cap.terms?.cross_user_processing_permitted;
  if (cross === true) pass("R-7.4", "terms permit joint processing across consenting users");
  else if (cross === false) fail("R-7.4", "terms prohibit joint processing across consenting users");
  else fail("R-7.4", "terms.cross_user_processing_permitted not stated; silence here is where interop dies");

  return { t1 };
}

// ---------------------------------------------------------------- §5, §6
function checkFrames(cap, allFrames, t1) {
  if (allFrames.length === 0) return fail("R-5.1", "no frames supplied");

  const skipped = allFrames.length - allFrames.filter((f) => f.tier === "t1").length;
  if (skipped > 0) warn("R-5.1", `${skipped} non-T1 frame(s) not examined by this check`);
  const frames = allFrames.filter((f) => f.tier === "t1");
  if (frames.length === 0) {
    return fail("R-5.1", "capture contains no T1 frames; there is nothing for a third party to build on");
  }

  const dim = t1?.dim;
  const declaredSpace = t1?.feature_space;
  const spaces = new Set();
  const sessions = new Map();
  let monoOk = true, seqOk = true, dimOk = true, qualityOk = true, finiteOk = true;
  let adaptMissing = false;
  let lastMono = -Infinity, gaps = 0;

  frames.forEach((f, i) => {
    const at = `frame ${i}`;
    for (const field of ["t_mono_ns", "t_wall_ms", "session_id", "seq", "feature_space", "values", "quality"]) {
      if (f[field] === undefined) {
        fail("R-5.1", `${at}: required field ${field} missing`);
      }
    }
    spaces.add(f.feature_space);

    if (!Number.isInteger(f.t_mono_ns) || f.t_mono_ns < lastMono) monoOk = false;
    lastMono = f.t_mono_ns;

    if (!Array.isArray(f.values) || (dim && f.values.length !== dim)) dimOk = false;
    if (Array.isArray(f.values) && !f.values.every((v) => Number.isFinite(v))) finiteOk = false;

    const q = f.quality;
    const inUnit = (v) => typeof v === "number" && v >= 0 && v <= 1;
    if (!(inUnit(q) || (Array.isArray(q) && q.every(inUnit)))) qualityOk = false;

    if (t1?.adaptive === true && f.adapt_state === undefined) adaptMissing = true;

    const prev = sessions.get(f.session_id);
    if (prev !== undefined) {
      if (f.seq <= prev) seqOk = false;
      if (f.seq > prev + 1) gaps++;
    }
    sessions.set(f.session_id, f.seq);
  });

  monoOk ? pass("R-5.2", "t_mono_ns present, integral, non-decreasing")
         : fail("R-5.2", "t_mono_ns missing, non-integral, or goes backwards");
  dimOk ? pass("R-5.1", `all values[] match declared dim ${dim}`)
        : fail("R-5.1", `values[] length disagrees with declared t1.dim ${dim}`);
  if (!finiteOk) fail("R-5.1", "values[] contains NaN or Infinity");
  qualityOk ? pass("R-5.6", "quality present and in 0..1")
            : fail("R-5.6", "quality missing or out of range");
  seqOk ? pass("R-5.3", `seq strictly increasing per session (${gaps} visible gap(s))`)
        : fail("R-5.3", "seq repeats or decreases within a session — reordering or renumbering");
  if (adaptMissing) fail("R-5.5", "adaptive T1 declared but frames carry no adapt_state");

  if (spaces.size === 1) {
    const [only] = [...spaces];
    if (declaredSpace && only !== declaredSpace) {
      fail("R-5.4", `frames report feature_space "${only}" but capability declares "${declaredSpace}"`);
    } else pass("R-5.4", `single pinned feature_space "${only}"`);
  } else {
    fail("R-5.4", `frames mix ${spaces.size} feature spaces (${[...spaces].join(", ")}) — an unpinned or silently updated transform`);
  }

  sessions.size > 0
    ? pass("R-6.1", `${sessions.size} session id(s) present`)
    : fail("R-6.1", "no session_id present");
  if (cap.don_count === undefined) warn("R-6.2", "capability does not expose don_count");
}

// ---------------------------------------------------------------- profiles §8
function checkAlignProfile(cap, frames) {
  if (!(cap.profiles ?? []).includes("akasara.align.v1")) return;
  const anchored = frames.filter((f) => f.anchor);
  if (anchored.length === 0) {
    return fail("R-8", "profile akasara.align.v1 declared but no frame carries an anchor block");
  }
  const worst = Math.max(...anchored.map((f) => f.anchor.timing_err_ms ?? Infinity));
  worst <= 10
    ? pass("R-8", `anchored frames within ${worst} ms stimulus-lock`)
    : fail("R-8", `stimulus-lock error ${worst} ms exceeds the 10 ms profile target`);
}

// ---------------------------------------------------------------- main
const argv = process.argv.slice(2);
const USAGE = `usage:
  node check.mjs <capability.json> <frames.jsonl> [selftest-output.json]
  node check.mjs --compare <before.capability.json> <after.capability.json>`;

if (argv[0] === "--compare") {
  const [, beforePath, afterPath] = argv;
  if (!beforePath || !afterPath) {
    console.error(USAGE);
    process.exit(2);
  }
  compareVersions(loadCapability(beforePath), loadCapability(afterPath));
} else {
  const [capPath, framesPath, selftestPath] = argv;
  if (!capPath || !framesPath) {
    console.error(USAGE);
    process.exit(2);
  }
  const cap = loadCapability(capPath);
  const frames = loadFrames(framesPath);
  const actual = selftestPath ? JSON.parse(readFileSync(selftestPath, "utf8")) : null;
  const { t1 } = checkCapability(cap);
  checkFrames(cap, frames, t1);
  checkSelftest(cap, actual);
  checkAlignProfile(cap, frames);
  console.log(`ASE-0.1 conformance — ${cap.vendor} ${cap.model} fw ${cap.firmware}\n`);
}

const failures = results.filter((r) => r.ok === false);
for (const r of results) {
  const mark = r.ok === true ? "PASS" : r.ok === false ? "FAIL" : "WARN";
  console.log(`  ${mark}  ${r.id.padEnd(7)} ${r.msg}`);
}
console.log(
  `\n${failures.length === 0 ? "CONFORMANT" : "NOT CONFORMANT"} — ` +
    `${results.filter((r) => r.ok === true).length} pass, ${failures.length} fail, ` +
    `${results.filter((r) => r.ok === null).length} warn`
);
process.exit(failures.length === 0 ? 0 : 1);
