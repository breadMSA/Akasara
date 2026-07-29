# Gate

An ASE-0.1 signal source and the consent gate in front of it, in one page.

The phone's IMU stands in for a body-signal wearable. It is not a substitute for
one and does not pretend to be: the point is that everything **downstream** of
the sensor — the feature space, the frame format, the self-test, the session
model, the transport, and the gate deciding what may leave — is real, and none of
it changes when the source is swapped for an EMG band or an EEG headset. The
signal is the only part that is standing in.

Two halves:

- **Source** — IMU samples in, T1 feature frames out, in a pinned feature space,
  with a working R-5.7 self-test and a §10.3 loopback transport.
- **Gate** — nothing leaves this device unless a grant you wrote says it may.
  Default deny, no allow-all, every grant expires, revocation reaches a stream
  already in flight.

No account, no network, no server. Frames live in memory and die with the tab;
grants and the audit ledger live in this browser's own storage and nowhere else.

## Running it

Open `index.html`. Device motion needs a secure context, so on a phone serve it
over `http://localhost` (localhost counts as secure) rather than opening the file
across the network:

```
python -m http.server 8000        # then open http://localhost:8000/apps/gate/
```

On a desktop with no motion sensor, switch the source to **Simulated**. A
simulated capture is labelled `"akasara.source": "simulated"` in its capability
descriptor and carries a different `model`, so it can never be mistaken for a
recording of a body.

To make the loopback transport real, run the bridge alongside it:

```
node apps/gate/bridge.mjs          # ws://127.0.0.1:8765
```

## The feature space

`akasara.imu.tdfeat.v1` — 6 channels (ax ay az gx gy gz), dim 12, 200 ms window,
100 ms stride, channel-major:

```
values[2c]     = RMS = sqrt(mean(x²))            over the window
values[2c + 1] = WL  = mean(|x[i] − x[i−1]|)     over the window
```

Input is normalised full scale, where ±1.0 is ±4 g on the accelerometer and
±2000 °/s on the gyroscope. Anything beyond that clips, exactly as it would in
hardware.

No filtering, no per-user state, no adaptation, no fitted normalisation. That is
deliberate rather than lazy: R-5.4 pins a feature space by promising that the
same input yields the same output forever, and a transform carrying hidden state
cannot make that promise. `t1Transform()` is the only path that produces a T1
value — live capture and self-test both go through it, as R-5.7 requires.

`quality` follows Appendix A for `imu` (per-channel tracking validity): the
fraction of the window's expected samples that actually arrived, reduced by the
fraction of samples that clipped. It is a measurement of the acquisition, never a
confidence in what the values mean.

## What conformance this build actually has

Run the spec's own suite over the three files this app exports:

```
node spec/conformance/check.mjs capability.json frames.jsonl selftest.json
```

Measured on an S21 FE, real IMU, streaming over the bridge:
**CONFORMANT, 17 pass, 0 fail, 2 warn.**

Running `bridge.mjs` is not what makes R-7.1 pass. The descriptor declares the
loopback transport only while the socket is actually open, so **Start streaming**
has to be pressed before `capability.json` is exported, and **Stop streaming**
withdraws the declaration again. That is deliberate — a descriptor promising a
transport nobody can reach is worse than one admitting it has none — but it does
mean the export order matters.

The two warnings are real and are not going away:

- **R-4.2** — the montage is `ase.opaque.v1`. A phone's IMU has no
  electrode geometry to declare, so captures are comparable within this model and
  not across models. Declaring anything else would be a lie.
- **R-4.3** — `clock.drift_ppm_max` is undeclared, because this build has not
  measured the host clock's drift. The spec would rather have the warning than a
  number nobody took.

Without the bridge, the descriptor honestly declares no local transport and the
suite reports **NOT CONFORMANT on R-7.1** — a browser cannot bind a listening
socket. That failure is the measured reason for a native build, and it is left
visible rather than papered over.

## The gate

A grant names one recipient, one purpose, an expiry, and a frame allowance. There
is no allow-all and no "remember this choice": a permission that cannot lapse is
how consent quietly becomes permanent.

A grant is a frame budget, and exporting frames spends what is left of it. A
grant whose allowance is smaller than the capture is therefore consumed by its
own first frame export, which is intended; the export panel says so rather than
greying its buttons without explanation. `capability.json` and `selftest.json`
cost nothing, so exporting those first leaves the allowance for the frames.

Withholding a field redacts the descriptor too, not only the frames.
`capabilityUnderGrant()` declares `clock.rtc: false` when a grant withholds
`t_wall_ms`, because a descriptor claiming an RTC beside frames carrying no wall
time is a capture that fails R-5.1 — the privacy control would otherwise be
manufacturing non-conformant exports.

Every export path — the three files, the signed bundle, and the live stream —
goes through `applyGrant()`. Redaction happens there rather than at each call
site, so a new export path cannot forget it. Withheld fields are dropped, except
`session_id`, which is replaced by a per-grant pseudonym rather than deleted:
R-6.1 exists so a consumer can see where sessions break, and removing the field
outright destroys that for no privacy gain. The pseudonym is salted with a random
per-grant value that never leaves the device — salting it with the grant id
instead would have been worthless, since the grant id travels inside the bundle
and anyone once given a real session id could have recomputed the link.

Exporting frames releases the **most recent** frames that the grant's remaining
allowance covers, not the oldest.

The signed bundle carries an ECDSA P-256 signature from a non-extractable key
generated in this browser. It shows that two captures came from the same source
and that neither was edited afterwards. It is **not** an identity and does not
try to be one — §10.5 is explicit that ASE Core does not address forgery, and
overclaiming here would be worse than the gap.

The audit ledger records that *n* frames went to a named recipient under a named
grant. It never records what was in them.

## Tests

```
node --test apps/gate/test/artifacts.test.mjs   # exports pass the real suite
node --test apps/gate/test/bridge.test.mjs      # the §10.3 bridge, end to end
```

`artifacts.test.mjs` lifts the DOM-free half of `index.html` out of the file and
runs it, rather than reimplementing the transform — a change that breaks
conformance breaks the test.
