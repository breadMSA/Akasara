#!/usr/bin/env python3
"""§10.3 loopback WebSocket binding for the replay producer.

The descriptor `replay.py` writes declares a `ws://localhost:<port>` transport.
A declared transport that nothing serves is a false claim, and R-4.4 exists to
stop exactly that — so this is the thing that makes the claim true.

Hand-rolled RFC6455, no dependencies. That is not minimalism for its own sake:
the browser gate's `bridge.mjs` is a second hand-rolled implementation of the
same section in a different language, and the two agreeing is evidence about
the spec text rather than about a shared library.

Binds 127.0.0.1 only (R-10.5: the listener MUST bind to loopback only).

    python serve.py --capture out/db5-s1
    python serve.py --capture out/db5-s1 --measure     # throughput, no client
"""

import argparse
import base64
import hashlib
import json
import os
import socket
import struct
import threading
import time

GUID = b"258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
OP_TEXT, OP_BINARY, OP_CLOSE, OP_PING, OP_PONG = 0x1, 0x2, 0x8, 0x9, 0xA


# ------------------------------------------------------------------ framing
def encode(payload, opcode=OP_TEXT):
    """Server -> client frame. Servers never mask (RFC6455 §5.1)."""
    if isinstance(payload, str):
        payload = payload.encode("utf-8")
    n = len(payload)
    head = bytes([0x80 | opcode])
    if n < 126:
        head += bytes([n])
    elif n < (1 << 16):
        head += bytes([126]) + struct.pack(">H", n)
    else:
        head += bytes([127]) + struct.pack(">Q", n)
    return head + payload


def read_exactly(sock, n):
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("peer closed mid-frame")
        buf += chunk
    return buf


def decode(sock):
    """Client -> server frame. Returns (opcode, payload); client frames are
    always masked and an unmasked one is a protocol error, not a warning."""
    b0, b1 = read_exactly(sock, 2)
    opcode = b0 & 0x0F
    masked = bool(b1 & 0x80)
    n = b1 & 0x7F
    if n == 126:
        n = struct.unpack(">H", read_exactly(sock, 2))[0]
    elif n == 127:
        n = struct.unpack(">Q", read_exactly(sock, 8))[0]
    if not masked:
        raise ConnectionError("client frame is not masked")
    key = read_exactly(sock, 4)
    data = bytearray(read_exactly(sock, n))
    for i in range(n):
        data[i] ^= key[i % 4]
    return opcode, bytes(data)


def handshake(sock):
    req = b""
    while b"\r\n\r\n" not in req:
        chunk = sock.recv(4096)
        if not chunk:
            return False
        req += chunk
    key = None
    for line in req.split(b"\r\n"):
        if line.lower().startswith(b"sec-websocket-key:"):
            key = line.split(b":", 1)[1].strip()
    if not key:
        sock.sendall(b"HTTP/1.1 400 Bad Request\r\n\r\n")
        return False
    accept = base64.b64encode(hashlib.sha1(key + GUID).digest())
    sock.sendall(
        b"HTTP/1.1 101 Switching Protocols\r\n"
        b"Upgrade: websocket\r\nConnection: Upgrade\r\n"
        b"Sec-WebSocket-Accept: " + accept + b"\r\n\r\n")
    return True


# ------------------------------------------------------------------- source
class Capture:
    def __init__(self, path):
        with open(os.path.join(path, "capability.json"), encoding="utf-8") as fh:
            self.capability = json.load(fh)
        self.frames = []
        with open(os.path.join(path, "frames.jsonl"), encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    self.frames.append(json.loads(line))
        st = os.path.join(path, "selftest.json")
        self.selftest = None
        if os.path.exists(st):
            with open(st, encoding="utf-8") as fh:
                self.selftest = json.load(fh)
        self.t0 = time.monotonic_ns()

    @property
    def stride_s(self):
        return self.capability["t1"]["stride_ms"] / 1000.0

    def mono_ns(self):
        return time.monotonic_ns() - self.t0

    def control(self, msg):
        """§10.4. Only the commands this source can honestly answer; an
        unknown or inapplicable command is refused with a reason rather than
        silently ignored."""
        cmd = msg.get("cmd")
        if cmd == "status":
            cur = self.frames[0]["session_id"] if self.frames else None
            return {"cmd": "status", "don_count": self.capability.get("don_count"),
                    "session_id": cur, "tier": "t1", "encoding": "json"}
        if cmd == "selftest":
            if self.selftest is None:
                return {"cmd": "selftest", "error": "no self-test output in this capture"}
            return {"cmd": "selftest", "input": "ase.selftest.v1", "values": self.selftest}
        if cmd == "time_echo":
            return {"cmd": "time_echo", "token": msg.get("token"),
                    "t_mono_ns": self.mono_ns()}
        if cmd in ("set_tier", "set_encoding", "set_adaptive"):
            return {"cmd": cmd, "error":
                    "a replay exports one tier in one encoding and is never adaptive"}
        return {"error": f"unknown command {cmd!r}"}


def serve_client(conn, cap, rate_limited=True):
    conn.sendall(encode(json.dumps(cap.capability, ensure_ascii=False)))

    stop = threading.Event()

    def reader():
        try:
            while not stop.is_set():
                op, data = decode(conn)
                if op == OP_CLOSE:
                    break
                if op == OP_PING:
                    conn.sendall(encode(data, OP_PONG))
                elif op == OP_TEXT:
                    try:
                        msg = json.loads(data.decode("utf-8"))
                    except ValueError:
                        continue
                    conn.sendall(encode(json.dumps(cap.control(msg))))
        except (ConnectionError, OSError):
            pass
        finally:
            stop.set()

    threading.Thread(target=reader, daemon=True).start()

    sent = 0
    start = time.perf_counter()
    for frame in cap.frames:
        if stop.is_set():
            break
        conn.sendall(encode(json.dumps(frame, ensure_ascii=False)))
        sent += 1
        if rate_limited:
            # R-7.2 is about the live rate: pace at the declared stride so the
            # socket carries what a device would actually put on it.
            target = start + sent * cap.stride_s
            delay = target - time.perf_counter()
            if delay > 0:
                time.sleep(delay)
    stop.set()
    return sent


def measure(cap, seconds=3.0):
    """Throughput of the framing path alone, so the declared
    max_sustained_kbps has a measurement behind it."""
    payloads = [encode(json.dumps(f, ensure_ascii=False)) for f in cap.frames[:200]]
    if not payloads:
        raise SystemExit("capture has no frames")
    tx, rx = socket.socketpair()
    drained = threading.Event()

    def drain():
        try:
            while not drained.is_set():
                if not rx.recv(1 << 20):
                    break
        except OSError:
            pass

    threading.Thread(target=drain, daemon=True).start()

    total, n = 0, 0
    t0 = time.perf_counter()
    try:
        while time.perf_counter() - t0 < seconds:
            p = payloads[n % len(payloads)]
            tx.sendall(p)
            total += len(p)
            n += 1
    except OSError:
        pass
    dt = time.perf_counter() - t0
    drained.set()
    tx.close()
    rx.close()
    kbps = total * 8 / dt / 1000
    per_frame = total / max(n, 1)
    live_kbps = per_frame * 8 * (1 / cap.stride_s) / 1000
    print(f"loopback socket sustained {kbps:,.0f} kbps "
          f"({n:,} frames in {dt:.1f} s, {per_frame:.0f} B/frame)")
    print(f"live rate needs {live_kbps:.0f} kbps at {1/cap.stride_s:.0f} Hz "
          f"— headroom {kbps/live_kbps:.0f}x")
    return kbps


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--capture", required=True, help="directory written by replay.py")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--measure", action="store_true",
                    help="measure framing throughput and exit, no listener")
    ap.add_argument("--once", action="store_true", help="serve one client then exit")
    args = ap.parse_args()

    cap = Capture(args.capture)
    if args.measure:
        measure(cap)
        return

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", args.port))          # loopback only, per R-10.5
    srv.listen(1)
    print(f"ASE §10.3 loopback source on ws://localhost:{args.port} "
          f"— {len(cap.frames)} frames, {cap.capability['t1']['dim']}-dim, "
          f"{1/cap.stride_s:.0f} Hz")
    try:
        while True:
            conn, _ = srv.accept()
            try:
                if handshake(conn):
                    sent = serve_client(conn, cap)
                    print(f"client done, {sent} frames sent")
            finally:
                conn.close()
            if args.once:
                break
    except KeyboardInterrupt:
        pass
    finally:
        srv.close()


if __name__ == "__main__":
    main()
