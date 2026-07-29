#!/usr/bin/env node
/**
 * ASE-0.1 §10.3 loopback bridge for the Gate web build.
 *
 * A browser can produce T1 frames but cannot bind a listening socket, so the web
 * build on its own declares no local transport and fails R-7.1. This process is
 * that missing listener: it binds loopback only, the page connects to it as the
 * device, and any consumer connecting to the same port gets exactly what §10.3
 * describes — the capability descriptor as the first message, then live T1
 * frames, with the §10.4 control plane available throughout.
 *
 * Usage:  node bridge.mjs [port]                 (default 8765)
 *
 * Zero dependencies, Node >= 18. Deliberately not a general WebSocket library:
 * it implements only what RFC 6455 requires to carry these messages.
 */

import { createServer } from "node:http";
import { createHash, randomUUID } from "node:crypto";

const PORT = Number(process.argv[2]) || 8765;
const HOST = "127.0.0.1";
const GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11";

/* R-10.5 — loopback only, and an Origin allowlist. A page served from anywhere
 * else has no business reaching a body-signal stream on this machine. Any local
 * port is accepted because the page is normally served by whatever static server
 * is to hand; a remote origin never is. */
const LOCAL_ORIGIN = /^https?:\/\/(localhost|127\.0\.0\.1|\[::1\])(:\d+)?$/;
const originAllowed = (o) => o === "null" || o === undefined || LOCAL_ORIGIN.test(o);

/* ------------------------------------------------------------------ framing */

function accept(key) {
  return createHash("sha1").update(key + GUID).digest("base64");
}

function encode(text) {
  const payload = Buffer.from(text, "utf8");
  const len = payload.length;
  let header;
  if (len < 126) {
    header = Buffer.from([0x81, len]);
  } else if (len < 65536) {
    header = Buffer.alloc(4);
    header[0] = 0x81;
    header[1] = 126;
    header.writeUInt16BE(len, 2);
  } else {
    header = Buffer.alloc(10);
    header[0] = 0x81;
    header[1] = 127;
    header.writeBigUInt64BE(BigInt(len), 2);
  }
  return Buffer.concat([header, payload]);
}

/** Incremental RFC 6455 reader. Emits complete text messages. */
function reader(onMessage, onClose, onPing) {
  let buf = Buffer.alloc(0);
  let fragments = [];

  return (chunk) => {
    buf = Buffer.concat([buf, chunk]);
    for (;;) {
      if (buf.length < 2) return;
      const fin = (buf[0] & 0x80) !== 0;
      const opcode = buf[0] & 0x0f;
      const masked = (buf[1] & 0x80) !== 0;
      let len = buf[1] & 0x7f;
      let offset = 2;

      if (len === 126) {
        if (buf.length < offset + 2) return;
        len = buf.readUInt16BE(offset);
        offset += 2;
      } else if (len === 127) {
        if (buf.length < offset + 8) return;
        const big = buf.readBigUInt64BE(offset);
        if (big > 8n * 1024n * 1024n) { onClose(); return; }   // no unbounded frames
        len = Number(big);
        offset += 8;
      }

      let mask = null;
      if (masked) {
        if (buf.length < offset + 4) return;
        mask = buf.subarray(offset, offset + 4);
        offset += 4;
      }
      if (buf.length < offset + len) return;

      const payload = Buffer.from(buf.subarray(offset, offset + len));
      if (mask) for (let i = 0; i < payload.length; i++) payload[i] ^= mask[i % 4];
      buf = buf.subarray(offset + len);

      if (opcode === 0x8) { onClose(); return; }
      if (opcode === 0x9) { onPing(payload); continue; }
      if (opcode === 0xa) continue;

      fragments.push(payload);
      if (fin) {
        const text = Buffer.concat(fragments).toString("utf8");
        fragments = [];
        onMessage(text);
      }
    }
  };
}

/* -------------------------------------------------------------------- state */

let device = null;                 // the one source socket
let capability = null;             // last descriptor the device announced
const consumers = new Map();       // id -> socket
const pending = new Map();         // control-command id -> consumer id

let framesRelayed = 0;

function send(sock, obj) {
  if (!sock || sock.destroyed) return;
  sock.write(encode(typeof obj === "string" ? obj : JSON.stringify(obj)));
}

function log(...args) {
  console.log(new Date().toISOString().slice(11, 19), ...args);
}

/* ------------------------------------------------------------------- server */

const server = createServer((req, res) => {
  res.writeHead(426, { "content-type": "text/plain" });
  res.end("ASE-0.1 loopback bridge: connect over WebSocket.\n");
});

server.on("upgrade", (req, socket) => {
  const origin = req.headers.origin ?? "null";
  const key = req.headers["sec-websocket-key"];

  if (!key) { socket.destroy(); return; }
  if (!originAllowed(origin)) {
    log(`refused upgrade from origin ${origin}`);
    socket.end("HTTP/1.1 403 Forbidden\r\n\r\n");
    return;
  }

  socket.write(
    "HTTP/1.1 101 Switching Protocols\r\n" +
    "Upgrade: websocket\r\n" +
    "Connection: Upgrade\r\n" +
    `Sec-WebSocket-Accept: ${accept(key)}\r\n\r\n`
  );
  socket.setNoDelay(true);

  const isDevice = (req.url ?? "/").startsWith("/device");
  isDevice ? attachDevice(socket) : attachConsumer(socket);
});

/* ------------------------------------------------------------------- device */

function attachDevice(socket) {
  /* R-10.3 — one streaming source at a time, and the reason is reported rather
   * than the connection dying silently. */
  if (device && !device.destroyed) {
    send(socket, { type: "error", reason: "a source is already connected to this bridge" });
    socket.end();
    return;
  }
  device = socket;
  log("source connected");

  const read = reader(
    (text) => {
      let msg;
      try { msg = JSON.parse(text); } catch { return; }

      if (msg.type === "capability") {
        capability = msg.capability;
        log(`capability: ${capability?.vendor} ${capability?.model} ${capability?.t1?.feature_space}`);
        for (const sock of consumers.values()) send(sock, capability);
        return;
      }
      if (msg.type === "frame") {
        framesRelayed++;
        const line = JSON.stringify(msg.frame);
        for (const sock of consumers.values()) send(sock, line);
        return;
      }
      if (msg.type === "control_reply") {
        const target = pending.get(msg.id);
        pending.delete(msg.id);
        const sock = consumers.get(target);
        if (sock) send(sock, msg.reply);
        return;
      }
    },
    () => closeDevice(),
    (payload) => socket.write(Buffer.concat([Buffer.from([0x8a, payload.length]), payload]))
  );

  socket.on("data", read);
  socket.on("error", closeDevice);
  socket.on("close", closeDevice);
}

function closeDevice() {
  if (!device) return;
  log(`source disconnected after ${framesRelayed} frame(s)`);
  device.destroy();
  device = null;
  /* R-10.7 — the consumers must be able to see the discontinuity, not resume
   * silently onto whatever connects next. */
  for (const sock of consumers.values()) {
    send(sock, { type: "session_end", reason: "source disconnected" });
  }
  capability = null;
}

/* ----------------------------------------------------------------- consumer */

function attachConsumer(socket) {
  const id = randomUUID().slice(0, 8);
  consumers.set(id, socket);
  log(`consumer ${id} connected (${consumers.size} total)`);

  /* §10.3 — capability is the first message on connect. If no source is up yet,
   * say so rather than sending a stale descriptor. */
  if (capability) send(socket, capability);
  else send(socket, { type: "no_source", reason: "no source is connected to this bridge yet" });

  const read = reader(
    (text) => {
      let cmd;
      try { cmd = JSON.parse(text); } catch { return; }
      if (!cmd.cmd) return;
      if (!device) { send(socket, { error: "no source connected" }); return; }
      const cid = randomUUID().slice(0, 8);
      pending.set(cid, id);
      send(device, { type: "control", id: cid, cmd });
    },
    () => {
      consumers.delete(id);
      socket.destroy();
      log(`consumer ${id} disconnected (${consumers.size} left)`);
    },
    (payload) => socket.write(Buffer.concat([Buffer.from([0x8a, payload.length]), payload]))
  );

  socket.on("data", read);
  socket.on("error", () => { consumers.delete(id); socket.destroy(); });
  socket.on("close", () => consumers.delete(id));
}

server.listen(PORT, HOST, () => {
  console.log(`ASE-0.1 loopback bridge on ws://${HOST}:${PORT}`);
  console.log(`  source   ws://${HOST}:${PORT}/device`);
  console.log(`  consumer ws://${HOST}:${PORT}/`);
  console.log("  bound to loopback only; other interfaces are not served.\n");
});
