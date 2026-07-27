# ASE — Akasara Signal Export

An open specification for body-signal wearables: **how a device makes the signal
it already records available to software its user chooses.**

| File | What it is |
| --- | --- |
| [`ASE-0.1.md`](ASE-0.1.md) | The specification. |
| [`schema/`](schema/) | JSON Schema for the capability descriptor and the T1 frame. |
| [`conformance/`](conformance/) | Reference test suite, zero dependencies, plus conformant and non-conformant vectors. |
| [`conformance/selftest.mjs`](conformance/selftest.mjs) | Generator for `ase.selftest.v1`, the fixed synthetic input every device runs its T1 transform over. |

## The short version

Every body-signal device — EMG band, EEG headset, implant — internally passes
through the same stages:

```
 sensor → filtered stream → feature/latent vector → classifier → discrete event
   T3          T2                   T1                              T0
```

Consumer devices export **T0**: the recognised gesture, not the signal. That is
defensible for privacy and fatal for everything else, because a discrete event
is not a lossy signal — it is a projection onto the vendor's fixed label set.
Anything needing the *geometry* of the signal (adapting to a user the vendor
never trained on, a vocabulary the vendor never shipped, mapping one person's
signal space onto another's) is not degraded at T0. It cannot be attempted.

**ASE requires T1**: fixed-dimension feature frames, on a local interface, in a
version-pinned feature space, with no term forbidding a user from processing
their frames alongside another consenting person's.

## Certification

Self-certification. Run the suite, publish the descriptor and the output:

```bash
cd conformance

# device conformance: descriptor, a frame capture, optionally the device's
# own self-test output
node check.mjs vectors/good.capability.json vectors/good.frames.jsonl \
               vectors/good.selftest-output.json

# did a firmware update silently change the feature space? two descriptors,
# no captures needed
node check.mjs --compare vectors/good.capability.json \
                         vectors/silent-update.after.capability.json
```

No fee, no gatekeeper, no approved-vendor list — a spec that gates its own
conformance reproduces the problem it exists to solve.

The `--compare` mode is the point of R-5.7. A device publishes what its
production transform returns for one fixed synthetic input; anyone can then
detect a silently re-trained on-device model from two descriptors alone, with no
statistics and no access to the hardware.

## Who this is for

Any hardware maker outside a closed platform's ecosystem. You are locked out of
the same walled gardens, and a cross-vendor semantic layer is not something any
one of you can build alone. The tier requirement costs you a serial endpoint and
a documented feature vector. It buys a device whose data a user actually owns.

## Status

Draft 0.1, 2026-07-27. Open issues are listed in §10. Comments welcome; the
schema and clause numbering may still move before 1.0.
