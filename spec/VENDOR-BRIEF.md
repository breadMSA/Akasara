# ASE-0.1 — vendor brief

*Two pages, for the person who has to approve this internally. Nothing here is
normative; every claim is sourced to a section of `ASE-0.1.md`, which is the
document that governs. If the two ever disagree, the spec wins.*

---

## The ask, in one sentence

> Let a user obtain **T1 feature frames** from your device, on a local
> interface, in a documented and version-pinned feature space, with no term in
> your agreement forbidding that user from processing those frames together with
> another consenting person's frames.

That is the whole of ASE-Core conformance (§0). Everything else in the
specification exists to make that sentence testable rather than aspirational.

## What it is not

It is **not a design blueprint** (§0). ASE does not specify electrodes,
materials, radios, connectors, enclosure, decoding algorithms, feature design,
or what the device is for. **No hardware changes to conform.** You add an output
path and a terms clause.

It is not a cloud integration, a data-sharing agreement, or a partnership. The
export is local, at the user's request, to the user's own machine. You are not
asked to send us anything, ever.

It is not a certification programme. There is no fee, no gatekeeper, and no
approved-vendor list (§11.4) — a spec that gates its own conformance reproduces
the problem it exists to solve.

## What it costs

| | |
| --- | --- |
| **Free — already in your pipeline** | T1 values exist between your filter stage and your classifier; sequence numbers and session ids are bookkeeping; `quality` is usually an impedance figure your firmware already computes. |
| **Real work — R-5.7** | A synthetic-input path that runs through the *production* transform, so the declared feature space can be verified against the device itself. Days, not weeks. |
| **Real work — R-7.5.1** | Keeping the previous feature space obtainable after you change it. §7 deliberately lets you satisfy this with a downgrade image rather than running two live pipelines. |

Documentation cost: one capability descriptor (JSON, §4) published alongside the
firmware.

## The three objections we expect, answered

**1. "Exporting features increases our privacy liability."**
The opposite is the more defensible reading, and it belongs in front of counsel
rather than being assumed either way — we are not offering a legal opinion and
this brief is not one. ASE requires export to a **local**
interface at **user** request: you do not collect, transmit, or store anything
new. Enacted neural-data and portability law — California, Colorado,
Connecticut, Montana; the EU Data Act — is already moving toward obliging
something close to this. A vendor that exports locally on request is nearer to
compliant than one that keeps the signal and ships it to its own cloud. §7.7
states explicitly that nothing in ASE makes you a controller or processor of
what the user does after export (R-7.7).

**2. "T1 lets a competitor clone our gesture recognition."**
Partly true, and worth saying plainly rather than waving off. T1 features do let
a third party train a classifier. What they do not hand over is the classifier
itself, the label taxonomy, the training corpus, or the tuning that makes
recognition feel good — which is where the work actually is. The spec never asks
for your model, your labels, or your training data. Weigh that exposure against
the alternative: the closed platforms will not interoperate with you, and a
device whose data cannot leave it cannot participate in any layer above it.

**3. "We want an SDK programme and app review."**
R-7.3 forbids **vendor** approval of the developer. It does not forbid a **user**
consent prompt, per-application authorisation, revocation, rate visibility, or
an audit log. Gate on the user's decision as much as you like; do not gate on
yours.

## Why T1 specifically, and not T0

Every body-signal device passes through the same stages: sensor → filtered
stream → feature vector → classifier → discrete event. Current consumer practice
is to export the last one only.

The consequence is rarely stated: **T0 is not a lossy version of the signal, it
is a different object** (§1). A discrete event is a projection onto your fixed
label set. Any use that needs the *geometry* — mapping one person's signal space
onto another's, adapting to a user you never trained on, supporting a vocabulary
you did not ship, research on a population you excluded — is not degraded at T0.
It is impossible at T0, at any data volume. Published cross-subject work is the
existence proof, and it is fitted on T1-level frames; re-run on event streams it
does not exist to be run.

So T1 is not "more data". It is the lowest tier at which anyone other than you
can build anything.

## What you get

- A user-facing answer to "can I get my own data out", with a version number
  attached instead of a promise.
- Position on the side the regulatory current is already running (Objection 1).
- Access to whatever gets built above the layer. A closed platform will
  interoperate with itself and with no one else; that leaves the cross-vendor
  slot structurally empty, and only devices whose data can leave them can
  occupy it.
- No fee, no membership, no dependency on us.

## How you claim it

Self-certify. Run the reference suite (Apache-2.0, in `spec/conformance/`):

```
node spec/conformance/check.mjs <capability.json> <frames.jsonl> [selftest.json]
```

It prints per-requirement PASS/FAIL and a verdict. Then publish the capability
descriptor and the suite output alongside the claim.

**Be aware of what the suite does and does not decide (§11.2).** It verifies the
declarations and the data: frame structure, clocks, sequencing, montage
completeness, self-test consistency, bandwidth feasibility. Most of §7 is a
statement about your *terms*, and the suite can only check that you have
declared it. A false declaration is a false statement by you, not a test
failure. A green run is not an audit, and we will not describe it as one.

Claims must name the exact firmware version tested, and must not be made for a
device family, a roadmap, or an unreleased version (§11.3). "ASE-compatible",
"ASE-ready" and "supports ASE" are undefined and mean nothing.

## Licensing and IP

Spec text **CC BY 4.0**; reference code **Apache-2.0**. Implementing requires no
permission and no fee.

The editor makes a **royalty-free, irrevocable, worldwide, non-exclusive**
patent non-assertion commitment covering the required portions of the spec
(§12.2). It is not conditioned on any licence, fee, membership, or contact; it
runs with the specification and binds successors; the only carve-out is standard
defensive suspension against a party that asserts a patent against an ASE
implementation. The editor holds no issued relevant patents as of the draft
date — the clause exists so your counsel does not have to take that on trust,
and so it stays true if that changes.

"ASE" is **not** a registered mark and no certification mark exists (§12.3). Do
not build brand dependence on an ASE badge yet.

## Honest statement of status

ASE-0.1 is a **draft**, written by a single editor (§13.1). There is no
consortium, no working group, and no shipping conformant device. We are not
going to imply otherwise in order to get a meeting.

What exists today: the specification, a machine-checkable schema, a reference
conformance suite with test vectors, and §14's open list of what 0.2 still has
to settle.

## What we are actually asking for

Not a commitment. One of these, in increasing order of cost to you:

1. **Tell us where it is wrong.** Specifically: which requirement would your
   firmware team refuse, and why. That feedback changes the document — §14
   exists for exactly this, and 0.1 already withdrew two claims that did not
   survive measurement.
2. **Run the suite against a capability descriptor you write on paper**, without
   shipping anything, and tell us what the descriptor could not honestly say.
3. **Ship T1 behind a user-facing toggle in a developer or beta build**, and
   claim conformance for that firmware version only.

The current draft, the schema and the suite are in `spec/`; `spec/README.md` is
the two-minute orientation. Corrections and objections go to the repository's
issue tracker, which is the only channel — there is no membership step and
nothing to sign.

Also worth knowing before you reply: if the editor becomes unreachable for 12
months, the spec freezes and every grant in §12 survives (§13.5). No implementer
is stranded by this being a one-person project.
