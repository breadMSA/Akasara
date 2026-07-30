"""ABF (ASE-0.1 §9.2), implemented from the layout table.

The reason to write this a second time, in a second language, is that §9.2 is
the part of the spec a vendor will implement in firmware against nothing but the
table — no reference file to diff against, because firmware is not JavaScript.
If the table alone is not enough to produce byte-identical frames, that is a
defect in the spec and it should surface here rather than in someone's BLE
stack.

`test_replay.py` encodes with this and decodes with `conformance/abf.mjs`, and
the other way round, so agreement is checked across the two rather than assumed.

Little-endian throughout. 24-byte header, value block, then trailers in bit
order.
"""

import math
import struct

TYPE_T1, TYPE_T0, TYPE_SESSION, TYPE_SELFTEST = 0x01, 0x02, 0x03, 0x04
VENC = {"f32": 0x00, "f16": 0x01, "i16": 0x02}
VENC_NAME = {v: k for k, v in VENC.items()}
WIDTH = {0x00: 4, 0x01: 2, 0x02: 2}
HEADER_BYTES = 24

FLAG_QUALITY_CH = 1 << 0
FLAG_ADAPT = 1 << 1
FLAG_ANCHOR = 1 << 2
FLAG_WALL = 1 << 3


def _fixed(v, maximum):
    """R-9.4: half away from zero, not Python's half-to-even. Getting this
    wrong is invisible in isolation and shows up only when someone diffs two
    implementations' bytes -- which is how it was found."""
    return int(math.floor(min(1.0, max(0.0, v)) * maximum + 0.5))


def frame_bytes(dim, venc="f32", channels=0, per_channel_quality=False,
                wall=False, adapt=False, anchor=False):
    n = HEADER_BYTES + dim * WIDTH[VENC[venc]]
    if venc == "i16":
        n += 4
    if per_channel_quality:
        n += channels
    if adapt:
        n += 2
    if anchor:
        n += 20
    if wall:
        n += 8
    return n


def encode_t1(frame, venc="f32", session_ord=0, adapt_ord=0,
              schedule_ord=0, item_ord=0):
    code = VENC[venc]
    values = frame["values"]
    dim = len(values)
    q = frame.get("quality")
    per_ch = isinstance(q, (list, tuple))
    aggregate = (sum(q) / len(q)) if per_ch else float(q)

    flags = 0
    if per_ch:
        flags |= FLAG_QUALITY_CH
    if frame.get("adapt_state") is not None:
        flags |= FLAG_ADAPT
    if frame.get("anchor") is not None:
        flags |= FLAG_ANCHOR
    if frame.get("t_wall_ms") is not None:
        flags |= FLAG_WALL

    out = bytearray()
    out += struct.pack("<BBBBHHIIQ", TYPE_T1, flags, code, 0, dim,
                       _fixed(aggregate, 65535),
                       frame["seq"], session_ord, frame["t_mono_ns"])

    if code == VENC["f32"]:
        out += struct.pack(f"<{dim}f", *values)
    elif code == VENC["f16"]:
        out += struct.pack(f"<{dim}e", *values)
    else:
        # int16 + a trailing float32 scale. The peak is taken from the frame
        # itself, so the quantisation step adapts to the frame's own range --
        # which is what R-9.1 is about: a vendor must not use this when the
        # resulting error exceeds its declared self-test tolerance.
        peak = max((abs(v) for v in values), default=0.0) or 5e-324
        scale = peak / 32767
        out += struct.pack(f"<{dim}h",
                           *(max(-32768, min(32767, round(v / scale))) for v in values))
        out += struct.pack("<f", scale)

    if per_ch:
        out += bytes(_fixed(v, 255) for v in q)
    if flags & FLAG_ADAPT:
        out += struct.pack("<H", adapt_ord)
    if flags & FLAG_ANCHOR:
        a = frame["anchor"]
        out += struct.pack("<IIQf", schedule_ord, item_ord,
                           a["t_stim_mono_ns"], a["timing_err_ms"])
    if flags & FLAG_WALL:
        out += struct.pack("<Q", frame["t_wall_ms"])
    return bytes(out)


def decode_t1(buf, channels=None):
    if len(buf) < HEADER_BYTES:
        raise ValueError("short buffer")
    (typ, flags, code, reserved, dim, quality_q, seq, session_ord,
     t_mono_ns) = struct.unpack_from("<BBBBHHIIQ", buf, 0)
    if typ != TYPE_T1:
        raise ValueError(f"not a T1 frame (type 0x{typ:02x})")
    if reserved != 0:
        raise ValueError("reserved byte must be 0")
    if code not in WIDTH:
        raise ValueError(f"unknown venc 0x{code:02x}")

    off = HEADER_BYTES
    if code == VENC["f32"]:
        values = list(struct.unpack_from(f"<{dim}f", buf, off))
        off += dim * 4
    elif code == VENC["f16"]:
        values = list(struct.unpack_from(f"<{dim}e", buf, off))
        off += dim * 2
    else:
        raw = struct.unpack_from(f"<{dim}h", buf, off)
        off += dim * 2
        scale = struct.unpack_from("<f", buf, off)[0]
        off += 4
        values = [r * scale for r in raw]

    out = {
        "tier": "t1", "seq": seq, "session_ord": session_ord,
        "t_mono_ns": t_mono_ns, "quality": quality_q / 65535, "values": values,
    }
    if flags & FLAG_QUALITY_CH:
        if channels is None:
            raise ValueError("per-channel quality present but channels unknown")
        out["quality"] = [b / 255 for b in buf[off:off + channels]]
        off += channels
    if flags & FLAG_ADAPT:
        out["adapt_ord"] = struct.unpack_from("<H", buf, off)[0]
        off += 2
    if flags & FLAG_ANCHOR:
        s_ord, i_ord, t_stim, err = struct.unpack_from("<IIQf", buf, off)
        out["anchor"] = {"schedule_ord": s_ord, "item_ord": i_ord,
                         "t_stim_mono_ns": t_stim, "timing_err_ms": err}
        off += 20
    if flags & FLAG_WALL:
        out["t_wall_ms"] = struct.unpack_from("<Q", buf, off)[0]
        off += 8

    out["_bytes"] = off
    return out
