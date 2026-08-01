# ASE — Akasara Signal Export

An open specification for body-signal wearables: **how a device makes the signal
it already records available to software its user chooses.**

Not a design blueprint. It specifies what must come out of the box and under
what terms — no electrodes, radios, enclosures, or algorithms. A vendor changes
no hardware to conform.

| File | What it is |
| --- | --- |
| [`ASE-0.1.md`](ASE-0.1.md) | The specification. |
| [`schema/`](schema/) | JSON Schema for the capability descriptor and the T1 frame. |
| [`conformance/check.mjs`](conformance/check.mjs) | Reference test suite, zero dependencies. |
| [`conformance/abf.mjs`](conformance/abf.mjs) | Reference codec for the ABF binary frame encoding (§9.2). |
| [`conformance/selftest.mjs`](conformance/selftest.mjs) | Generator for `ase.selftest.v1`, the fixed synthetic input every device runs its T1 transform over. |
| [`CHANGELOG.md`](CHANGELOG.md) | Errata and revisions, per §13.2. |
| [`LICENSE`](LICENSE) / [`LICENSE-CODE`](LICENSE-CODE) | CC BY 4.0 for the text, Apache-2.0 for the code. Patent commitment in §12.2. |

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

## Cost to implement, honestly

Most of it is free — T1 values already exist in the pipeline, and sequence
numbers, session ids and `quality` are bookkeeping. Two clauses cost real work:
the self-test path (R-5.7, days) and keeping the previous feature space
obtainable after a change (R-7.5.1, satisfiable with a downgrade image rather
than two live pipelines). §1.1 answers the three objections a vendor actually
raises: privacy liability, competitor cloning, and SDK gating.

## Running the suite

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

# the binary encoding round-trips and matches the bandwidth table in §10
node abf.mjs --selftest
```

Vectors cover a conformant device, the align profile, a T0-only cloud-gated
device, a stream with a silent transform change, a device promising a frame rate
its radio cannot carry, a device inventing a wall clock it does not have, and a
device quoting an R-11.5 feature-space margin without the task, subject count and
resampling unit that make an interval readable, and a device quoting one measured
at a single donning through a pipeline whose fitted parameters scale with the
feature dimension (R-11.5.1, R-11.5.2) — the two knobs that, on CEMHSEY, move the
same space's margin from +0.093 to +0.177 and from +0.422 to −0.126.

`--compare` is the point of R-5.7: a device publishes what its production
transform returns for one fixed synthetic input, so a silently re-trained
on-device model is detectable from two descriptors alone — no statistics, no
access to the hardware.

## Certification

Self-certification. No fee, no gatekeeper, no approved-vendor list — a spec that
gates its own conformance reproduces the problem it exists to solve. Claim
wording and what the suite can and cannot decide are in §11; the honest limit is
that every §7 requirement except R-7.2 is a vendor declaration the suite can
only record, not verify.

## For vendors

`VENDOR-BRIEF.md` is the two-page version for whoever has to approve this
internally: the ask, what it costs, the three objections we expect, and what we
are actually asking for. It is non-normative and every claim in it points back
to a clause here.

`ICS.md` is the Implementation Conformance Statement — one row for every one of
the 54 requirement identifiers in the specification, with what you are
asserting, whether the suite can decide it or only record your declaration, and
a column to fill in. Of the 49 answerable rows the suite decides 18 outright;
20 rest wholly or partly on the vendor's signature. That split is deliberate and
is spelled out in R-11.2.

## Licence and patents

Text CC BY 4.0, code Apache-2.0. §12.2 is a royalty-free, irrevocable patent
commitment that requires no registration, fee, or contact, with defensive
suspension as its only carve-out. ASE-Core conformance is never conditioned on
any profile licence (R-8.1). If the editor becomes unreachable for 12 months the
spec freezes and every grant survives (§13.5) — no implementer is stranded.

## Status

Draft 0.1, 2026-07-27, single editor, no organisation behind it (§13.1). Open
issues are in §14. The schema and clause numbering may still move before 1.0;
requirement identifiers are never reused or renumbered.
