# Gate

An ASE-0.1 signal source and the consent gate in front of it, in one page.

The phone's IMU stands in for a body-signal wearable. It is not a substitute for
one and does not pretend to be: the point is that everything **downstream** of
the sensor — the feature space, the frame format, the self-test, the session
model, the transport, and the gate deciding what may leave — is real, and none of
it changes when the source is swapped for an EMG band or an EEG headset. The
signal is the only part that is standing in.

Three parts:

- **Source** — IMU samples in, T1 feature frames out, in a pinned feature space,
  with a working R-5.7 self-test and a §10.3 loopback transport.
- **Cued protocol** — ten movements, prompted on a timer, so two devices produce
  captures that can be aligned to each other. A window is labelled only when it
  lies entirely inside a hold period; anything straddling a boundary is left
  unlabelled rather than assigned to whichever cue covers more of it. The label
  rides on `akasara.cue`, the same vendor-extension field the replay producer in
  `../replay` writes, so a consumer cannot tell which one produced a capture.
- **Gate** — nothing leaves this device unless a grant you wrote says it may.
  Default deny, no allow-all, every grant expires, revocation reaches a stream
  already in flight. The cue is its own grant field: it says what the person was
  asked to *do*, which the signal alone does not carry, so withholding it is a
  real choice and not a formality. Withholding it can never make the capture
  non-conformant — it is a vendor extension — and there is a test that keeps
  that true.

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

## T0 events

The gate exports T0 alongside T1 (R-3.2), from a recogniser that runs on the
exported T1 vectors and nothing else. Two codes:

| code | label | when |
| --- | --- | --- |
| 1 | `movement_onset` | mean per-channel RMS crosses **0.06** upward |
| 2 | `movement_offset` | it falls back below **0.03**, with the movement's `duration_ms` |

Two thresholds rather than one because a single one chatters: a hand held still
hovers around whatever value you pick and emits a burst of onsets. `T0_ENTER` and
`T0_EXIT` are in normalised full scale, set from the resting band of a handheld
phone.

**It declares no confidence, on purpose.** A hysteresis threshold does not have a
posterior, and R-3.2.1 says a device without one omits the field rather than
emitting 1.0 — so `t0.confidence` is `false` here, and by R-9.5 these events go
out as JSON rather than ABF. Manufacturing a plausible number from the distance
to the threshold would have made the tier look more finished than the recogniser
is.

**Every event names its evidence.** `t0.derived_from_t1` is true, so R-3.2.2
obliges each event to carry `t1_seq` — the `seq` of the T1 frame the recogniser
decided on — and the conformance suite checks that citation resolves to a frame
present in the capture whose window ended no later than the event. That one
integer is the difference between a vendor's claim and something a host can
re-derive. It is also why the egress path drops an event whose cited frame fell
outside the grant's allowance: a grant releases the last *n* records, the cut can
land between an event and its frame, and shipping the event without its evidence
is precisely what the clause forbids. Found by exporting under a small allowance,
not by reading the clause.

## What conformance this build actually has

Run the spec's own suite over the three files this app exports:

```
node spec/conformance/check.mjs capability.json frames.jsonl selftest.json
```

Measured on an S21 FE, real IMU, streaming over the bridge:
**CONFORMANT, 18 pass, 0 fail, 2 warn** (2026-07-29, before T0).

With the T0 tier added the same descriptor and a capture containing events reads
**CONFORMANT, 23 pass, 0 fail, 2 warn** — the five extra passes are the R-3.2 /
R-3.2.1 / R-3.2.2 rows. Stated separately because that run is the test harness
driving the app's own recogniser over a synthetic still→move→still trace, not the
phone: **the 23 has not yet been re-measured on the real IMU.** The 18 is the
number that came off hardware.

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

## Running a paired capture

Two phones, two people, one shared protocol. The point is not the movements —
they are arbitrary. The point is that both captures carry the same cue
vocabulary, so a consumer can ask whether one person's signal predicts the
other's on movements it was never fitted on.

1. Both phones: serve the repo over `localhost` (see above), open the page,
   **Start session**.
2. Set the same hold, rest and reps on both. Defaults are 3 s hold, 2 s rest,
   3 reps — ten cues, so about 2.5 minutes.
3. Press **Run protocol** on both at roughly the same moment. Exact
   synchronisation is not needed and is not what the cue is for: the cue is a
   label, not a timestamp, and each device labels its own windows by its own
   clock. R-5.2.1's measurement is the reason this is safe — a 400 ms offset
   between two people costs under 1% at gesture granularity.
4. Read the prompts and do them. Hold still during the rest periods; those
   windows are deliberately unlabelled and are what a consumer uses as the
   negative case.
5. Each phone: create a grant with `akasara.cue` included, export
   `capability.json` and `frames.jsonl`.
6. Put each phone's three files in its own directory and feed both to
   `apps/replay/align.py`, which does not care that these came from a phone
   rather than a dataset:

   ```
   python apps/replay/align.py out/phone-a out/phone-b
   ```

   Ten cues means five fitted on and five held out, so chance is 0.200 and the
   whole run is one ordered pair each way — enough to see the pipeline work end
   to end, nowhere near enough for an interval. `align.py` knows this app's
   feature space is channel-major and reduces it accordingly; it refuses a space
   it has not been told about rather than guessing, because getting that wrong
   silently averages RMS together with waveform length.

   Two phones is also below `align.py`'s own bar: it bootstraps over subjects,
   and two subjects give an interval that means nothing. Treat the first paired
   run as a wiring test, not a result.

What this can and cannot show: two phones held by **one** person is a
cross-device test, which is a real question but not a cross-person one. The
cross-person claim needs two bodies. Either way the capture is the same shape,
so the harness is worth having before the second person is.

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
