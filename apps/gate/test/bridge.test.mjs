/**
 * End-to-end test of the §10.3 loopback bridge. The WebSocket framing in
 * bridge.mjs is hand-written, so it is exercised against a real client rather
 * than reasoned about.
 *
 * Run:  node --test apps/gate/test/bridge.test.mjs
 */

import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const BRIDGE = join(here, "..", "bridge.mjs");
const PORT = 8931 + (process.pid % 400);
const BASE = `ws://127.0.0.1:${PORT}`;

let proc;

before(async () => {
  proc = spawn(process.execPath, [BRIDGE, String(PORT)], { stdio: ["ignore", "pipe", "pipe"] });
  await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error("bridge did not start")), 5000);
    proc.stdout.on("data", (b) => {
      if (String(b).includes("loopback bridge on")) { clearTimeout(timer); resolve(); }
    });
    proc.on("error", reject);
  });
});

after(() => proc?.kill());

/** Connect and collect messages; resolves once `n` have arrived. */
function connect(path = "/") {
  const sock = new WebSocket(BASE + path);
  const queue = [];
  const waiters = [];
  sock.addEventListener("message", (ev) => {
    const parsed = (() => { try { return JSON.parse(ev.data); } catch { return ev.data; } })();
    const w = waiters.shift();
    if (w) w(parsed); else queue.push(parsed);
  });
  return {
    sock,
    open: new Promise((res, rej) => {
      sock.addEventListener("open", res, { once: true });
      sock.addEventListener("error", () => rej(new Error("socket error")), { once: true });
    }),
    next: () => new Promise((res, rej) => {
      if (queue.length) return res(queue.shift());
      const t = setTimeout(() => rej(new Error("timed out waiting for a message")), 4000);
      waiters.push((m) => { clearTimeout(t); res(m); });
    }),
    send: (obj) => sock.send(JSON.stringify(obj)),
    close: () => sock.close(),
  };
}

const CAPABILITY = { ase_version: "0.1", vendor: "akasara", model: "gate-web-sim", t1: { feature_space: "akasara.imu.tdfeat.v1" } };

test("a consumer arriving before any source is told so, not given a stale descriptor", async () => {
  const c = connect();
  await c.open;
  const first = await c.next();
  assert.equal(first.type, "no_source");
  c.close();
});

test("capability is the first message a consumer sees, then frames flow", async () => {
  const dev = connect("/device");
  await dev.open;
  dev.send({ type: "capability", capability: CAPABILITY });
  await new Promise((r) => setTimeout(r, 100));

  const c = connect();
  await c.open;
  const first = await c.next();
  assert.equal(first.t1.feature_space, "akasara.imu.tdfeat.v1", "capability must arrive first");

  const frame = { tier: "t1", t_mono_ns: 100000000, session_id: "s-1", seq: 0, feature_space: "akasara.imu.tdfeat.v1", values: [1, 2], quality: [0.9] };
  dev.send({ type: "frame", frame });
  assert.deepEqual(await c.next(), frame);

  c.close();
  dev.close();
  await new Promise((r) => setTimeout(r, 100));
});

test("a large frame survives the 16-bit length path", async () => {
  const dev = connect("/device");
  await dev.open;
  dev.send({ type: "capability", capability: CAPABILITY });
  await new Promise((r) => setTimeout(r, 100));
  const c = connect();
  await c.open;
  await c.next();

  const big = { tier: "t1", seq: 1, values: new Array(4000).fill(0.123456) };
  dev.send({ type: "frame", frame: big });
  const got = await c.next();
  assert.equal(got.values.length, 4000);

  c.close();
  dev.close();
  await new Promise((r) => setTimeout(r, 100));
});

test("the §10.4 control plane round-trips consumer -> source -> consumer", async () => {
  const dev = connect("/device");
  await dev.open;
  dev.send({ type: "capability", capability: CAPABILITY });
  await new Promise((r) => setTimeout(r, 100));
  const c = connect();
  await c.open;
  await c.next();

  c.send({ cmd: "status" });
  const control = await dev.next();
  assert.equal(control.type, "control");
  assert.equal(control.cmd.cmd, "status");
  dev.send({ type: "control_reply", id: control.id, reply: { don_count: 7, tier: "t1" } });
  assert.deepEqual(await c.next(), { don_count: 7, tier: "t1" });

  c.close();
  dev.close();
  await new Promise((r) => setTimeout(r, 100));
});

test("a second source is refused with a stated reason, not silently (R-10.3)", async () => {
  const first = connect("/device");
  await first.open;
  first.send({ type: "capability", capability: CAPABILITY });
  await new Promise((r) => setTimeout(r, 100));

  const second = connect("/device");
  await second.open;
  const msg = await second.next();
  assert.equal(msg.type, "error");
  assert.match(msg.reason, /already connected/);

  first.close();
  await new Promise((r) => setTimeout(r, 100));
});

test("losing the source ends the session visibly (R-10.7)", async () => {
  const dev = connect("/device");
  await dev.open;
  dev.send({ type: "capability", capability: CAPABILITY });
  await new Promise((r) => setTimeout(r, 100));
  const c = connect();
  await c.open;
  await c.next();

  dev.close();
  const msg = await c.next();
  assert.equal(msg.type, "session_end");

  c.close();
});
