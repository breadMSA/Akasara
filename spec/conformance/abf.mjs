#!/usr/bin/env node
/**
 * ABF — ASE Binary Frame, reference codec for ASE-0.1 §9.2.
 *
 * Little-endian, 24-byte header, optional trailers. This file exists so the
 * encoding is implemented rather than merely described: a vendor can diff their
 * bytes against it, and the layout table in the spec is checkable.
 *
 * Usage: node abf.mjs --selftest     round-trip and layout checks
 */

import { pathToFileURL } from "node:url";

export const TYPE = { T1: 0x01, T0: 0x02, SESSION: 0x03, SELFTEST: 0x04 };
export const VENC = { f32: 0x00, f16: 0x01, i16: 0x02 };
export const HEADER_BYTES = 24;
const WIDTH = { 0x00: 4, 0x01: 2, 0x02: 2 };

const FLAG_QUALITY_CH = 1 << 0;
const FLAG_ADAPT = 1 << 1;
const FLAG_ANCHOR = 1 << 2;
const FLAG_WALL = 1 << 3;

/* ---- float16, no dependencies ------------------------------------------ */

function f32ToF16(v) {
  const f = new Float32Array(1);
  f[0] = v;
  const x = new Uint32Array(f.buffer)[0];
  const sign = (x >>> 16) & 0x8000;
  let exp = (x >>> 23) & 0xff;
  let man = x & 0x7fffff;
  if (exp === 0xff) return sign | 0x7c00 | (man ? 0x200 : 0); // Inf / NaN
  let e = exp - 127 + 15;
  if (e >= 0x1f) return sign | 0x7c00; // overflow -> Inf
  if (e <= 0) {
    if (e < -10) return sign; // underflow -> zero
    man |= 0x800000;
    const shift = 14 - e;
    const half = (man + (1 << (shift - 1))) >>> shift;
    return sign | half;
  }
  const rounded = man + 0x1000;
  if (rounded & 0x800000) return sign | ((e + 1) << 10); // mantissa carry
  return sign | (e << 10) | (rounded >>> 13);
}

function f16ToF32(h) {
  const sign = (h & 0x8000) ? -1 : 1;
  const exp = (h >>> 10) & 0x1f;
  const man = h & 0x3ff;
  if (exp === 0) return sign * Math.pow(2, -14) * (man / 1024);
  if (exp === 0x1f) return man ? NaN : sign * Infinity;
  return sign * Math.pow(2, exp - 15) * (1 + man / 1024);
}

/* ---- encode ------------------------------------------------------------ */

/**
 * @param {object} frame  the JSON-shaped T1 frame of §5
 * @param {object} opts   { venc: "f32"|"f16"|"i16", channels, sessionOrd }
 */
export function encodeT1(frame, opts = {}) {
  const vencName = opts.venc ?? "f32";
  const venc = VENC[vencName];
  if (venc === undefined) throw new Error(`unknown value encoding ${vencName}`);
  const dim = frame.values.length;
  const w = WIDTH[venc];

  const perCh = Array.isArray(frame.quality);
  const aggregate = perCh
    ? frame.quality.reduce((a, b) => a + b, 0) / frame.quality.length
    : frame.quality;

  let flags = 0;
  if (perCh) flags |= FLAG_QUALITY_CH;
  if (frame.adapt_state !== undefined) flags |= FLAG_ADAPT;
  if (frame.anchor) flags |= FLAG_ANCHOR;
  if (frame.t_wall_ms !== undefined) flags |= FLAG_WALL;

  let size = HEADER_BYTES + dim * w;
  if (venc === VENC.i16) size += 4; // trailing float32 scale
  if (perCh) size += frame.quality.length;
  if (flags & FLAG_ADAPT) size += 2;
  if (flags & FLAG_ANCHOR) size += 20;
  if (flags & FLAG_WALL) size += 8;

  const buf = Buffer.alloc(size);
  buf.writeUInt8(TYPE.T1, 0);
  buf.writeUInt8(flags, 1);
  buf.writeUInt8(venc, 2);
  buf.writeUInt8(0, 3);
  buf.writeUInt16LE(dim, 4);
  // R-9.4: half away from zero. Math.round already is, for the non-negative
  // values this field holds; named here so it stays deliberate. A half-to-even
  // language gets a different byte, which is how the clause came to exist.
  buf.writeUInt16LE(Math.round(Math.min(1, Math.max(0, aggregate)) * 65535), 6);
  buf.writeUInt32LE(frame.seq, 8);
  buf.writeUInt32LE(opts.sessionOrd ?? 0, 12);
  buf.writeBigUInt64LE(BigInt(frame.t_mono_ns), 16);

  let off = HEADER_BYTES;
  if (venc === VENC.f32) {
    for (const v of frame.values) { buf.writeFloatLE(v, off); off += 4; }
  } else if (venc === VENC.f16) {
    for (const v of frame.values) { buf.writeUInt16LE(f32ToF16(v), off); off += 2; }
  } else {
    const peak = Math.max(...frame.values.map(Math.abs), Number.MIN_VALUE);
    const scale = peak / 32767;
    for (const v of frame.values) {
      buf.writeInt16LE(Math.max(-32768, Math.min(32767, Math.round(v / scale))), off);
      off += 2;
    }
    buf.writeFloatLE(scale, off); off += 4;
  }

  if (perCh) for (const q of frame.quality) buf.writeUInt8(Math.round(q * 255), off++);  // R-9.4
  if (flags & FLAG_ADAPT) { buf.writeUInt16LE(opts.adaptOrd ?? 0, off); off += 2; }
  if (flags & FLAG_ANCHOR) {
    buf.writeUInt32LE(opts.scheduleOrd ?? 0, off); off += 4;
    buf.writeUInt32LE(opts.itemOrd ?? 0, off); off += 4;
    buf.writeBigUInt64LE(BigInt(frame.anchor.t_stim_mono_ns), off); off += 8;
    buf.writeFloatLE(frame.anchor.timing_err_ms, off); off += 4;
  }
  if (flags & FLAG_WALL) { buf.writeBigUInt64LE(BigInt(frame.t_wall_ms), off); off += 8; }

  if (off !== size) throw new Error(`internal: wrote ${off} of ${size} bytes`);
  return buf;
}

/* ---- decode ------------------------------------------------------------ */

export function decodeT1(buf, channels) {
  if (buf.length < HEADER_BYTES) throw new Error("short buffer");
  const type = buf.readUInt8(0);
  if (type !== TYPE.T1) throw new Error(`not a T1 frame (type 0x${type.toString(16)})`);
  if (buf.readUInt8(3) !== 0) throw new Error("reserved byte must be 0");

  const flags = buf.readUInt8(1);
  const venc = buf.readUInt8(2);
  const w = WIDTH[venc];
  if (w === undefined) throw new Error(`unknown venc 0x${venc.toString(16)}`);
  const dim = buf.readUInt16LE(4);

  const out = {
    tier: "t1",
    seq: buf.readUInt32LE(8),
    session_ord: buf.readUInt32LE(12),
    t_mono_ns: Number(buf.readBigUInt64LE(16)),
    quality: buf.readUInt16LE(6) / 65535,
    values: new Array(dim),
  };

  let off = HEADER_BYTES;
  if (venc === VENC.f32) {
    for (let i = 0; i < dim; i++) { out.values[i] = buf.readFloatLE(off); off += 4; }
  } else if (venc === VENC.f16) {
    for (let i = 0; i < dim; i++) { out.values[i] = f16ToF32(buf.readUInt16LE(off)); off += 2; }
  } else {
    const raw = new Array(dim);
    for (let i = 0; i < dim; i++) { raw[i] = buf.readInt16LE(off); off += 2; }
    const scale = buf.readFloatLE(off); off += 4;
    for (let i = 0; i < dim; i++) out.values[i] = raw[i] * scale;
  }

  if (flags & FLAG_QUALITY_CH) {
    if (channels === undefined) throw new Error("per-channel quality present but channels unknown");
    out.quality = [];
    for (let c = 0; c < channels; c++) out.quality.push(buf.readUInt8(off++) / 255);
  }
  if (flags & FLAG_ADAPT) { out.adapt_ord = buf.readUInt16LE(off); off += 2; }
  if (flags & FLAG_ANCHOR) {
    out.anchor = {
      schedule_ord: buf.readUInt32LE(off),
      item_ord: buf.readUInt32LE(off + 4),
      t_stim_mono_ns: Number(buf.readBigUInt64LE(off + 8)),
      timing_err_ms: buf.readFloatLE(off + 16),
    };
    off += 20;
  }
  if (flags & FLAG_WALL) { out.t_wall_ms = Number(buf.readBigUInt64LE(off)); off += 8; }

  out._bytes = off;
  return out;
}

/** Bytes on the wire for a given shape — used by the suite's R-4.4 check. */
export function frameBytes({
  dim, venc = "f32", channels = 0,
  perChannelQuality = false, wall = false, adapt = false, anchor = false,
}) {
  let n = HEADER_BYTES + dim * WIDTH[VENC[venc]];
  if (venc === "i16") n += 4;
  if (perChannelQuality) n += channels;
  if (adapt) n += 2;
  if (anchor) n += 20;
  if (wall) n += 8;
  return n;
}

/* ---- selftest ---------------------------------------------------------- */

function selftest() {
  let failures = 0;
  const check = (name, ok, detail = "") => {
    console.log(`  ${ok ? "ok  " : "FAIL"}  ${name}${detail ? " — " + detail : ""}`);
    if (!ok) failures++;
  };

  const frame = {
    tier: "t1", t_mono_ns: 1234567890123, t_wall_ms: 1785000000000,
    session_id: "s-1", seq: 42, feature_space: "x.v1",
    values: [0.5, -0.25, 0.125, 1.0, -1.0, 0, 3.5, -0.0078125],
    quality: [0.9, 0.8, 0.7, 1.0],
    anchor: { schedule_id: "a", item: "b", t_stim_mono_ns: 1234567000000, timing_err_ms: 3.25 },
  };

  const f32 = encodeT1(frame, { venc: "f32", channels: 4 });
  const d32 = decodeT1(f32, 4);
  check("f32 round-trip is exact", d32.values.every((v, i) => v === frame.values[i]));
  check("f32 length matches frameBytes()",
    f32.length === frameBytes({ dim: 8, venc: "f32", channels: 4, perChannelQuality: true, wall: true, anchor: true }),
    `${f32.length} bytes`);
  check("header is 24 bytes", HEADER_BYTES === 24);
  check("all trailers consumed", d32._bytes === f32.length, `${d32._bytes} of ${f32.length}`);
  check("seq / t_mono / session survive", d32.seq === 42 && d32.t_mono_ns === 1234567890123);
  check("t_wall_ms survives", d32.t_wall_ms === 1785000000000);
  check("anchor timing survives", d32.anchor.timing_err_ms === 3.25);
  check("per-channel quality survives within 1/255",
    d32.quality.every((q, i) => Math.abs(q - frame.quality[i]) < 1 / 255));

  const d16 = decodeT1(encodeT1(frame, { venc: "f16", channels: 4 }), 4);
  const worst16 = Math.max(...d16.values.map((v, i) => Math.abs(v - frame.values[i])));
  check("f16 round-trip within 1e-3 for these values", worst16 < 1e-3, `worst ${worst16.toExponential(2)}`);

  const di = decodeT1(encodeT1(frame, { venc: "i16", channels: 4 }), 4);
  const worstI = Math.max(...di.values.map((v, i) => Math.abs(v - frame.values[i])));
  check("i16+scale round-trip within 1e-3", worstI < 1e-3, `worst ${worstI.toExponential(2)}`);

  // exact-value edge cases for the f16 path
  const edges = [0, -0, 1, -1, 65504, 6.103515625e-5, 0.0009765625];
  const de = decodeT1(encodeT1({ ...frame, values: edges, quality: 0.5, t_wall_ms: undefined, anchor: undefined },
    { venc: "f16" }), 0);
  check("f16 represents its exactly-representable edges exactly",
    de.values.every((v, i) => v === edges[i] || (Object.is(edges[i], -0) && v === 0)));

  // no-RTC device: t_wall_ms absent must not set the flag
  const noRtc = { ...frame, t_wall_ms: undefined, quality: 0.75, anchor: undefined };
  const dn = decodeT1(encodeT1(noRtc, { venc: "f32" }), 0);
  check("absent t_wall_ms stays absent", dn.t_wall_ms === undefined);
  check("aggregate quality within 1/65535", Math.abs(dn.quality - 0.75) < 1 / 65535);

  // bandwidth table in §10 must match the codec
  const kbps = (dim, hz, venc) => (frameBytes({ dim, venc }) * hz * 8) / 1000;
  check("§10 table: dim64 @50Hz f32 = 112 kbps", Math.round(kbps(64, 50, "f32")) === 112);
  check("§10 table: dim64 @50Hz f16 = 61 kbps", Math.round(kbps(64, 50, "f16")) === 61);
  check("§10 table: dim32 @20Hz f32 = 24 kbps", Math.round(kbps(32, 20, "f32")) === 24);

  console.log(failures === 0 ? "\nABF selftest: all checks passed" : `\nABF selftest: ${failures} FAILED`);
  return failures;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  if (process.argv[2] === "--selftest") process.exit(selftest() === 0 ? 0 : 1);
  console.error("usage: node abf.mjs --selftest");
  process.exit(2);
}
