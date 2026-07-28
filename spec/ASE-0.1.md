# ASE-0.1 — Akasara Signal Export

**Status:** Draft. **Date:** 2026-07-27. **Editor:** breadMSA.
**Applies to:** any body-signal input device — surface EMG bands, EEG headsets,
eye/face trackers, implanted or future neural interfaces.
**Licence:** spec text CC BY 4.0; reference code Apache-2.0; royalty-free patent
commitment in §12. Implementing this document requires no permission and no fee.

## 0. What this specifies, and what it does not

This document specifies **how a wearable makes the signal it already records
available to software the user chooses**, and the minimum fidelity at which it
must do so.

It is **not a design blueprint.** It does not specify electrodes, materials,
radios, connectors, enclosure, decoding algorithms, feature design, or what the
device is for. A vendor changes no hardware to conform; they add an output path
and a terms clause.

The one-line summary of the whole document:

> A device is ASE-conformant if a user can obtain **T1 feature frames** from it,
> on a local interface, in a documented and version-pinned feature space, with
> no contractual term forbidding the user from processing those frames together
> with another person's frames.

Everything else here is the detail needed to make that testable.

## 1. Why the tier matters (rationale, non-normative)

Every body-signal device internally passes through the same stages:

```
 sensor → filtered stream → feature/latent vector → classifier → discrete event
   T3          T2                   T1                              T0
```

Current consumer practice is to export **T0 only**: raw signal stays on the
device, applications receive discrete recognised gestures or commands. This is
defensible on privacy grounds and it is where at least one major vendor's
developer toolkit lands as of mid-2026.

The consequence is rarely stated: **T0 is not a lossy version of the signal, it
is a different object.** A discrete event is a projection onto the vendor's
fixed label set. Any use that needs the *geometry* of the signal — mapping one
person's signal space onto another's, adapting to a user the vendor never
trained on, supporting a vocabulary the vendor did not ship, research on the
population the vendor excluded — is not merely degraded at T0. It is impossible
at T0, at any data volume.

Published cross-subject work is the existence proof: a linear map fitted on one
person's feature frames transfers to another person's with no per-user
calibration, and survives across recording days. That result is fitted on
T1-level frames. Re-run on T0 event streams it does not exist to be run.

So T1 is not "more data". T1 is the lowest tier at which anyone other than the
device vendor can build anything.

### 1.1 What this costs a vendor, and the three real objections

Non-normative, and written for the person who has to approve this internally.

**Engineering cost.** Most of the document is free: T1 values already exist in
the pipeline, sequence numbers and session ids are bookkeeping, `quality` is
usually an impedance number the firmware already has. Two clauses cost real
work: **R-5.7** (a synthetic-input path through the production transform —
days, not weeks) and **R-7.5.1** (keeping the previous feature space obtainable
after a change, which §7 deliberately allows you to satisfy with a downgrade
image rather than two live pipelines).

**Objection 1 — "exporting features increases our privacy liability."** The
opposite is the more defensible reading, and it is worth putting in front of
counsel rather than assuming. ASE requires export to a **local** interface at
**user** request. The vendor does not collect, transmit, or store anything new;
the data leaves to the user's own machine on the user's instruction. Enacted
neural-data and data-portability law (CA, CO, CT, MT; EU Data Act) is already
moving toward obliging exactly this. A vendor that exports locally on request is
closer to compliant than one that keeps the signal and ships it to its own
cloud. §7.7 states explicitly that nothing here makes the vendor a controller or
processor of what the user does after export.

**Objection 2 — "T1 lets a competitor clone our gesture recognition."** Partly
true, and it should be said plainly rather than waved off. T1 features do let a
third party train a classifier. What they do not give away is the classifier
itself, the label taxonomy, the training corpus, or the tuning that makes
recognition feel good — which is where the work actually is. The spec never asks
for the model, the labels, or the training data. Weigh that exposure against the
alternative: the closed platforms will not interoperate with you, and a device
whose data cannot leave it cannot participate in any layer above it.

**Objection 3 — "we want an SDK programme / app review."** R-7.3 forbids
*vendor* approval of the developer. It does not forbid a **user** consent
prompt, per-application authorisation, revocation, rate visibility, or an audit
log. Gate on the user's decision as much as you like; do not gate on yours.

## 2. Terminology

The key words MUST, MUST NOT, SHOULD, SHOULD NOT, MAY are to be interpreted as
described in BCP 14 (RFC 2119, RFC 8174) when, and only when, they appear in
capitals.

- **Device** — the hardware plus its firmware.
- **Vendor** — the party that places the device on the market and sets its
  terms.
- **Host** — software on a machine the user controls, receiving exported data.
- **Subject** — the person whose body produces the signal.
- **User** — the person operating the device and exercising the rights in §7.
  In this document the user is presumed to be the subject; where they differ
  (a carer operating a device for someone else, a research participant) the
  rights in §7 follow the **subject**, and the vendor MUST NOT treat the
  operator's authorisation as the subject's.
- **Feature space** — the (dimension, semantics, producing-transform) triple
  that a T1 vector lives in.
- **Session** — a continuous period of wear. Ends at doff, power loss, or
  re-seat.
- **Analysis window** — the span of samples a single T1 vector summarises.

## 3. Export tiers

| Tier | Content | Certified as |
| --- | --- | --- |
| **T0** | Discrete events: recognised gestures, keys, commands | not sufficient alone |
| **T1** | Fixed-dimension numeric feature or latent vector per analysis window | **required** |
| **T2** | Continuous per-channel stream after fixed, documented filtering | optional badge |
| **T3** | Raw samples at ADC resolution and native rate | optional badge |

**R-3.1** ASE-Core conformance requires T1.

**R-3.2** A device that emits recognised events MUST expose them as T0 alongside
T1, never instead of it.

**R-3.3** T2 and T3 are declared as the badges `ase.t2` / `ase.t3`. They are
encouraged for research-grade devices and not expected of consumer ones.

## 4. Capability descriptor

**R-4.1** A conformant device MUST expose a machine-readable capability
descriptor over its local interface before any data flows. Schema:
`schema/capability.schema.json`.

```json
{
  "ase_version": "0.1",
  "vendor": "example",
  "model": "band-2",
  "firmware": "3.4.1",
  "tiers": ["t0", "t1"],
  "profiles": [],
  "signal": {
    "kind": "semg",
    "channels": 16,
    "sample_rate_hz": 2000,
    "montage": {
      "system": "ase.limb.v1",
      "site": "forearm-proximal",
      "side": "right",
      "arrangement": "circumferential",
      "reference": "differential-adjacent",
      "positions": [
        { "ch": 0, "angle_deg": 0, "axial_mm": 60 },
        { "ch": 1, "angle_deg": 22.5, "axial_mm": 60 }
      ]
    }
  },
  "t1": {
    "feature_space": "example.band2.tdfeat.v3",
    "dim": 64,
    "window_ms": 200,
    "stride_ms": 50,
    "producer": "dsp",
    "documentation": "https://example.com/ase/tdfeat-v3",
    "latency_typ_ms": 12,
    "latency_max_ms": 28
  },
  "clock": { "rtc": false, "mono_epoch": "boot", "drift_ppm_max": 40 },
  "selftest": { "input": "ase.selftest.v1", "expected": [], "tolerance": 1e-4 },
  "transport": [
    { "uri": "usb-cdc", "encodings": ["abf", "json"], "max_sustained_kbps": 8000 },
    { "uri": "ble://0001cd2c-3660-4e38-98ea-18dca6f5b514", "encodings": ["abf"],
      "phy": "2M", "max_sustained_kbps": 250 }
  ],
  "requires_account": false,
  "requires_network": false,
  "developer_gate": false,
  "terms": { "cross_user_processing_permitted": true, "url": "https://example.com/ase/terms" }
}
```

**R-4.2 (montage).** `signal.montage` MUST be a structured descriptor in a named
coordinate system, not a free string. Two montages are **comparable** if and
only if a third party can decide it from the descriptors alone, which requires:

| Field | Requirement |
| --- | --- |
| `system` | one of the registered systems (Appendix B) |
| `site` | region term from that system's vocabulary |
| `side` | `left` \| `right` \| `midline` \| `bilateral` \| `n/a` |
| `arrangement` | `circumferential` \| `linear` \| `grid` \| `scattered` \| `single` |
| `reference` | `monopolar-<site>` \| `differential-adjacent` \| `differential-pair` \| `average` \| `laplacian` |
| `positions[]` | one entry per channel, in that system's coordinates |

Registered coordinate systems for 0.1:

- **`ase.eeg.1020.v1`** — `positions[]` entries are `{ ch, label }` with `label`
  from the extended 10-20 set (`Fp1`, `AFz`, `T7`, …). `site` is the coverage
  region (`frontal`, `central`, `whole-head`, …).
- **`ase.limb.v1`** — for limb-worn surface arrays. `positions[]` entries are
  `{ ch, angle_deg, axial_mm }`: `angle_deg` is 0–360 clockwise around the limb
  viewed distally, origin at the anatomical landmark named by `site`;
  `axial_mm` is distance distal-positive from that landmark. `site` from
  `{forearm-proximal, forearm-mid, forearm-distal, upper-arm, wrist, thigh,
  shank, neck-anterior, neck-posterior}`.
- **`ase.face.v1`** — `positions[]` entries are `{ ch, muscle }` using FACS
  muscle names (`orbicularis-oris`, `zygomaticus-major`, …).
- **`ase.opaque.v1`** — escape hatch for arrangements the above cannot express
  (implanted arrays, novel geometries). `positions[]` MAY be omitted. A device
  declaring `ase.opaque.v1` is ASE-Core conformant but is not montage-comparable
  **across models**. The suite reports this rather than failing it.

**R-4.2.1 (opaque devices are still comparable to themselves).** A device using
`ase.opaque.v1` MUST declare `geometry_id`: an identifier that is identical
across units whose sensor arrangement is interchangeable, and different as soon
as it is not. Two captures carrying the same `geometry_id` are comparable; two
carrying different ones are not.

> Non-normative: the first draft let an opaque device be incomparable even with
> another unit of the same model, which is both useless and untrue — a
> production run is interchangeable by construction. `geometry_id` costs the
> vendor one string and recovers within-model comparability, which is the case
> that actually occurs. Cross-model comparability for opaque geometries stays
> genuinely unsolved (§14).

**R-4.2.2 (rotation, and how precise `angle_deg` has to be).** For a
`circumferential` array, two montages with the same electrode **count and
spacing** are comparable regardless of their absolute rotation. `angle_deg`
MUST be accurate to within half an electrode spacing; finer precision is not
required and MUST NOT be assumed by a consumer.

> Measured, not assumed (Ninapro DB5, 6 subjects, 30 ordered pairs, 52 shared
> movements, single-trial calibration-free direct transfer, chance 0.062):
>
> | B's band rotated | P@1 | vs aligned |
> | --- | --- | --- |
> | 0° | 0.285 | — |
> | 11.25° (¼ electrode) | 0.271 | −0.014, CI [−0.017, −0.011] |
> | 22.5° (½ electrode) | 0.260 | −0.025, CI [−0.030, −0.020] |
> | 45° (1 electrode) | 0.285 | 0.000 |
> | 90° (2 electrodes) | 0.285 | 0.000 |
>
> Two things fall out. Whole-electrode rotations are **exactly** free, because a
> fitted linear map absorbs a channel permutation — so requiring vendors to
> agree on absolute band orientation would buy nothing. Sub-electrode
> misalignment does cost, worst at the half-way point, but only ~9% of transfer,
> which is why the tolerance above is half a spacing and not a degree.
>
> The limit of the evidence: this holds for a map fitted per pair on that
> device's own data. A device shipping a fixed pre-trained decoder does not
> inherit the permutation invariance. The rotation is also modelled as a linear
> blend of neighbouring electrodes in the raw signal, which is first-order —
> real re-donning changes skin contact too, and that is the larger effect
> (see R-6.2).

**R-4.2.3 (axial placement).** Unlike rotation, displacement *along* the limb is
not permutation-like and nothing about it is free. `axial_mm` MUST be declared
for every channel in `ase.limb.v1`, and a consumer comparing two montages MUST
treat differing `axial_mm` as a real difference rather than a labelling detail.

> Measured (same setup; DB5 wears two Myo rings at different heights on the
> forearm, which is exactly an axial displacement of one ring): ring-to-ring at
> the **same** height transfers at P@1 0.245, at a **different** height 0.229 —
> −0.016, CI [−0.024, −0.008], retaining 93.4%. Smaller than one might expect,
> and unlike rotation it does not vanish. Note the baseline is lower than
> R-4.2.2's because a single 8-electrode ring carries less than both rings
> together; the comparison is like-for-like within this table.

Tolerance for comparability beyond the rotation and axial cases is not fixed by
this document; it belongs to the consumer of the data. The descriptor's job is
to make the question answerable.

**R-4.3 (clock declaration).** The descriptor MUST carry a `clock` block stating
whether the device has a real-time clock (`rtc`), the epoch of its monotonic
clock (`mono_epoch`, `boot` or `session`), and the manufacturer's worst-case
oscillator drift in ppm. Devices without an RTC are common and fully
conformant; they simply MUST NOT invent a wall-clock value (see R-5.2).

**R-4.4 (transport declaration).** Each entry in `transport[]` MUST state its
URI, the encodings it carries (§9), and `max_sustained_kbps` — the throughput
the vendor commits to sustaining on that transport under normal conditions. At
least one declared transport MUST sustain the device's own live T1 rate
(R-7.2); the suite computes this and fails a device that promises a frame rate
its only transport cannot carry.

## 5. T1 frames

**R-5.1** Each T1 frame MUST carry: `t_mono_ns`, `session_id`, `seq`,
`feature_space`, `values` (array of `dim` finite numbers), and `quality`.
`t_wall_ms` MUST be present if and only if the device has an RTC. Schema:
`schema/frame.schema.json`.

**R-5.2 (clocks).** `t_mono_ns` MUST come from a monotonic device clock that
does not jump on wall-clock adjustment, and MUST refer to the **end of the
analysis window**, not the time of transmission. Its epoch MUST be device boot
or session start, as declared in R-4.3 — **never the Unix epoch**, because in
the JSON encoding a nanosecond value that large exceeds the 2^53 exactly
representable range and is silently corrupted. A device with no RTC MUST omit
`t_wall_ms` rather than emit 0, a build date, or an uninitialised value.

**R-5.2.1 (host time sync).** The device SHOULD implement the `time_echo`
control command (§10.4): the host sends a token, the device returns it with the
`t_mono_ns` at which it was received. Two exchanges bracketing a capture let the
host place device time on its own clock and estimate drift.

> Why SHOULD and not MUST, measured (same setup as R-4.2.2): sliding one
> person's analysis window against the other's by a fixed offset costs almost
> nothing at gesture granularity — P@1 0.285 at 0 ms, 0.285 at 25 ms, 0.284 at
> 100 ms, 0.283 at 400 ms, i.e. **0.8% lost at 400 ms**. Cross-device clock
> error from the declared `drift_ppm_max` is two to three orders of magnitude
> smaller than that over a session. Making `time_echo` mandatory would impose
> firmware work to protect a tolerance the task does not appear to need.
>
> That first result used whole-repetition windows seconds long, so it was
> re-run at the window lengths this document actually uses. It did not invert:
>
> | window | offset 25 ms | 100 ms | 200 ms | 400 ms |
> | --- | --- | --- | --- | --- |
> | 200 ms | 102% | 103% | 100% | **89%**, CI [−0.032, −0.008] |
> | 100 ms | 103% | 103% | 98% | **87%**, CI [−0.030, −0.006] |
>
> The tolerance is ~200 ms and is set by the movement, not by the window
> length — shortening the window from 200 ms to 100 ms does not tighten it.
> Only at 400 ms does the window slide far enough off the movement to cost
> 11–13%. Small offsets score marginally *above* aligned because they skip the
> onset transient, which is a real effect and not noise.
>
> The residual limit: every measurement here pairs two people event-by-event.
> A workload that pairs them sample-by-sample is untested, and remains the case
> that would make this a MUST.

**R-5.3** The device MUST document typical and worst-case sensor-to-host
latency, and MUST NOT reorder frames. Gaps MUST be visible as `seq` gaps, never
silently concealed by re-numbering.

**R-5.4 (feature-space pinning).** `feature_space` MUST be a stable identifier
for the exact transform producing `values`. **Any change to that transform —
including a firmware or model update that a vendor considers an improvement —
MUST change the identifier.**

> Non-normative: this is the clause most likely to be violated by accident and
> the most expensive when it is. Every encoder any third party has fitted
> against a feature space is invalidated by a silent change to it. A silently
> re-trained device-side model does not degrade downstream systems visibly; it
> makes them wrong.

**R-5.5** The device MUST NOT apply per-user adaptation to exported T1 values
without declaring it. If adaptive normalisation is applied, the frame MUST carry
`adapt_state` identifying the current adaptation, and the device MUST offer a
mode in which exported T1 is non-adaptive.

**R-5.6 (quality).** `quality` MUST be either a single 0..1 aggregate or an
array of **exactly `signal.channels` values** in 0..1 — per channel, not per
feature dimension. It MUST be produced by measurement, not by the classifier's
confidence. Per-`kind` definitions are in Appendix A, and are normative.

**R-5.7 (feature-space self-test).** The device MUST expose a self-test that
runs the **exact production T1 transform** over a fixed synthetic input and
returns the resulting vector. The descriptor MUST publish the expected output:

```json
"selftest": {
  "input": "ase.selftest.v1",
  "expected": [0.1421, -0.0038, ...],
  "tolerance": 1e-4
}
```

`ase.selftest.v1` is the deterministic synthetic signal generated by
`conformance/selftest.mjs` for the device's declared channel count and sample
rate: per channel *c*, sample *n*, at rate *fs*, over exactly 2.000 s —

```
x[c][n] = 0.5·sin(2π(20+7c)·n/fs) + 0.2·sin(2π(150+11c)·n/fs) + 0.05·r[c][n]
```

where `r` is the first 2·fs outputs of a xorshift32 PRNG seeded with `c+1`,
scaled to [-1, 1]. Values are in **normalised full scale**: ±1.0 corresponds to
the device's own ADC full-scale range, so the device applies its normal scaling
and any input outside its range clips exactly as a real signal would.

**R-5.7.1 (which window).** The published vector MUST be the T1 output of the
**last analysis window ending at or before t = 2.000 s**. Devices MUST NOT
average windows, and MUST NOT return the first window (which is contaminated by
filter start-up transients that differ across implementations).

**R-5.7.2 (tolerance).** `tolerance` MUST be at least the vendor's own
build-to-build variation for the same transform — fixed-point pipelines and
compiler changes move the last bits. A vendor that states a tolerance tighter
than its own reproducibility will fail its own self-test after a routine
toolchain upgrade.

The self-test MUST bypass acquisition and per-user adaptation, and MUST NOT be
special-cased: a device that computes self-test output by any path other than
its production transform is non-conformant.

> Non-normative: this is what makes R-5.4 *decidable*. Without it, "did a
> firmware update silently change the transform?" can only be guessed at
> statistically, and the guess is confounded by electrode placement, the user,
> and the day. With it, the question is one array comparison, runnable by anyone
> holding the device, before and after any update. The clause costs a vendor a
> few hundred bytes in the descriptor. It is the single highest-leverage
> requirement in this document.

## 6. Session and wear state

**R-6.1** A new `session_id` MUST be issued at every don, re-seat, or power
cycle. Devices MUST NOT continue a session id across removal.

**R-6.2** The device MUST expose `don_count` and, where measurable, an
indication of placement shift within a session. Because the descriptor is
typically read once at connect, `don_count` MUST also be obtainable at any time
via the `status` control command (§10.4).

> Non-normative: cross-day and cross-donning drift is the dominant failure mode
> for any map fitted on this data. A host that cannot see where sessions break
> cannot compensate for drift it cannot see.

## 7. Access, locality, and rights

**R-7.1 (local interface).** T1 export MUST be reachable over a local interface
— USB, BLE GATT, or a loopback socket — with **no vendor cloud round-trip, no
network connectivity, and no account**. A vendor cloud API MAY exist in
addition. It does not satisfy this requirement.

**R-7.2 (live rate).** Exported T1 MUST be available at the device's native
frame rate on at least one declared transport (R-4.4). Deliberate rate
reduction, batching delays beyond documented latency, or quota-limiting the
local interface below live rate is non-conformant. A transport that is
physically incapable of the live rate is not a violation — declaring no
transport that can carry it is.

**R-7.3 (user authorisation, not vendor approval).** Access MUST be grantable by
the user to software of the user's choice. A conformant device MUST NOT restrict
T1 export to an approved-developer programme, a signed application list, or an
app store. Per-application consent, revocation, and audit logging under the
user's control are explicitly permitted (see §1.1, objection 3).

**R-7.4 (no cross-user restriction).** The device's terms MUST NOT prohibit the
user, or software acting for the user, from processing exported frames jointly
with frames exported by another person's device, where each person has
authorised it.

Minimum sufficient wording, which a vendor may paste into its terms:

> Data you export from the device under [export feature] is yours. We place no
> restriction on your combining it with data exported by other people who have
> likewise chosen to share theirs with you.

> Non-normative: R-7.4 is the clause that decides whether an interoperability
> layer between people can legally exist. Read the enacted neural-data statutes
> (CA, CO, CT, MT; EU Data Act portability): they establish user ownership and
> portability of the data, and none of them, as of this draft, addresses
> cross-user joint processing. That silence is currently filled by terms of
> service. R-7.4 fills it the other way.

**R-7.5 (no silent downgrade).** A firmware update MUST NOT remove a certified
tier, remove a transport, or change a `feature_space`, without explicit
user-visible notice at install time.

**R-7.5.1 (refit window).** After a `feature_space` change, the previous feature
space MUST remain **obtainable** by the user until re-enrollment under the new
one is complete, and in any case for no less than **90 days**. Firmware that
changed `t1.feature_space` MUST declare `previous_feature_space` in its
descriptor for the duration of the window.

"Obtainable" is satisfied by **any** of: a selectable mode in current firmware;
a published downgrade image the user can install without vendor approval; or a
documented device setting that restores the previous transform. Two concurrently
resident pipelines are **not** required — that would be the expensive reading,
and it is not the intent.

> Derivation, and its limits. The window exists for one purpose: to let a user
> re-fit whatever was built on the old feature space before it disappears. So it
> must cover a full re-enrollment, and re-enrollment is bounded by *donning
> sessions*, not by compute — cross-day and cross-donning variation is the
> dominant term, so sessions must be spread across distinct days.
>
> Wear frequency is now sourced rather than assumed: Rock Health's 2025
> Consumer Adoption Survey (N = 8,000, fielded December 2025) reports **83% of
> wearable owners wear their device five or more days per week**, 59% always or
> nearly always. A device removed nightly or for charging is donned at least
> once per worn day, so ≥5 donnings/week is the right figure for a typical
> owner — not the 3/week this document assumed in its first draft.
>
> Recomputing: ~20 donning sessions at ≥5/week is ~4 weeks of active wear, and
> doubling for interruption gives ~8 weeks ≈ 56 days. **That is shorter than the
> 90-day floor, and the floor is kept anyway** — deliberately, because a floor
> exists to protect the worst case, not the median. The same literature that
> gives the median gives the tail: adherence studies consistently find a
> substantial low-adherence group (~29% in the SafeHeart ICD cohort over six
> months), and consumer wearables are widely abandoned within about two months.
> 90 days covers the median with margin and still does not cover the deepest
> tail.
>
> What remains unmeasured is the **20 donning sessions** itself; it is
> extrapolated from fitting behaviour observed offline, not measured. The
> cross-day EMG dataset used elsewhere in this document (Hyser) carries two
> sessions per subject, which cannot show where a learning curve saturates — it
> bounds only the data-volume half, which saturates near 100 single-session
> trials. An earlier revision said no open dataset could settle the other half;
> that was wrong. CEMHSEY records 11 consecutive days with the electrode grids
> taken down and re-applied each day, openly on Zenodo
> (10.5281/zenodo.14224328, 10.5281/zenodo.14272463), and the
> registration-gated Ninapro DB6 (10 sessions over 5 days) is a second option.
> Neither reaches 20 donnings, so either would bound the parameter rather than
> confirm it. It stays asserted until one of them is run.
>
> The completion condition, not the day count, is the substantive requirement;
> the floor only stops a vendor from declaring re-enrollment "complete" the
> moment it ships.

**R-7.6 (export on demand).** Beyond live streaming, the user MUST be able to
export retained data in one of the encodings of §9. Proprietary-only export
containers are non-conformant.

**R-7.7 (no downstream responsibility).** Nothing in this document makes the
vendor a controller, processor, or joint controller of data after it has been
exported to the user's host, nor obliges the vendor to support, validate, or
warrant any downstream use. Conformance is about not *forbidding* the user; it
imposes no duty to assist.

## 8. Profiles

A profile is an optional capability declared in `profiles[]`, layering
additional requirements on ASE-Core. Profiles do not change Sections 3–7.

Registered:

| Profile id | Adds | Availability |
| --- | --- | --- |
| `ase.t2`, `ase.t3` | higher tiers per §3 | open, royalty-free, no permission needed |
| `akasara.align.v1` | **Anchored enrollment**: the device can lock exported frames to an externally presented stimulus schedule with bounded, reported timing error (target ≤ 10 ms), and can emit a signed enrollment record covering a full anchor run. This is what allows an encoder fitted on one person to be related to one fitted on another. | separate licence from the editor |

**R-8.1** ASE-Core conformance MUST NOT be conditioned on taking any profile
licence. A vendor may implement, ship, certify, and advertise full ASE-Core
conformance without ever contacting the editor, and the §12 grants apply to
Core unconditionally and irrevocably. `akasara.align.v1` is strictly additive:
declining it costs a device nothing in Core conformance.

The anchor material and the fitting procedure behind `akasara.align.v1` are not
part of this document and are not required to build a conformant device.

## 9. Encodings

Two encodings carry the same information model. A device MUST implement at
least one; the descriptor declares which per transport (R-4.4).

### 9.1 JSON

UTF-8 JSON objects exactly as shown in §4 and §5. Mandatory for the capability
descriptor and the self-test result on every transport, because both are read
once and human inspection matters more than bytes.

JSON MUST NOT be used for T1 streaming above ~30 kbps of payload (see the table
in §10). Its per-frame cost is roughly 2.3× the binary encoding, and numeric
text loses the exactness that R-5.7 depends on.

### 9.2 ABF — ASE Binary Frame

Little-endian throughout. Header is 24 bytes, followed by the value block and
optional trailers.

| Offset | Size | Field |
| --- | --- | --- |
| 0 | 1 | `type` — `0x01` T1 frame, `0x02` T0 event, `0x03` session announce, `0x04` self-test result |
| 1 | 1 | `flags` — bit0 per-channel quality trailer, bit1 `adapt_state` trailer, bit2 anchor trailer, bit3 `t_wall_ms` trailer |
| 2 | 1 | `venc` — value encoding: `0x00` float32, `0x01` float16, `0x02` int16 + scale |
| 3 | 1 | reserved, MUST be 0 |
| 4 | 2 | `dim` |
| 6 | 2 | `quality_q` — aggregate quality, unsigned fixed point, 0 = 0.0, 65535 = 1.0 |
| 8 | 4 | `seq` |
| 12 | 4 | `session_ord` — ordinal of the current session; the string `session_id` is announced once per session by a `type = 0x03` message |
| 16 | 8 | `t_mono_ns` — unsigned, epoch per R-4.3 |
| 24 | `dim × w` | `values`, `w` = 4/2/2 by `venc` |

For `venc = 0x02`, a float32 `scale` immediately follows the value block;
element *i* of the feature vector is `values[i] × scale`.

Trailers appear in bit order after the value block (and after `scale` if
present): per-channel quality as `channels` bytes (0..255 mapped to 0..1);
`adapt_state` as a `uint16` id resolved via the descriptor; anchor as
`{ uint32 schedule_ord, uint32 item_ord, uint64 t_stim_mono_ns, float32
timing_err_ms }`; `t_wall_ms` as a `uint64`.

**R-9.1** A device MUST NOT use `venc = 0x01` (float16) or `0x02` (int16) when
the resulting quantisation exceeds its declared self-test `tolerance`, and MUST
declare in `t1` which encodings are lossless for its feature space. A host
receiving a lossy encoding cannot verify R-5.7 from the stream.

> Why the narrow encodings are not a tidiness feature (non-normative). Measured
> 2026-07-28 on a consumer handset over a tethered cellular uplink, one location,
> one carrier: a 4096-byte payload cost **+258 ms** over a 256-byte one to the
> nearest reachable endpoint, and +290 ms to the nearest datacentre region. The
> cost is in the uplink — `time_starttransfer` tracked `time_total` to within a
> millisecond, so the time went into getting the request out, not into the far
> side answering. Over a wired link the same two sizes were indistinguishable,
> which is why this does not show up on a developer's desk.
>
> A 1024-dimension float32 vector is 4 KB. On that link it does not fit a live
> conversational budget and an 8-bit encoding of the same vector does. That is
> the whole reason `venc` carries narrow options, and R-9.1 is what stops a
> vendor reaching for them past the point where the values still mean what the
> feature space says they mean.
>
> Caveats, because one measurement is one measurement: a single network, a
> single time of day, and a tethered radio belonging to a second handset. The
> **shape** — uplink-bound, so payload width is the lever — is expected to be
> portable; the milliseconds are not.

**R-9.2** Unknown `type` values and unknown trailer bits MUST be skippable: a
receiver that does not understand a message MUST be able to discard it using
the length its transport provides, and MUST NOT desynchronise.

### 9.3 Export container (`.ase`)

Streaming is protected by its link layer; a file on disk is not, and R-7.6
exports are exactly the artifacts someone will still be fitting encoders
against in two years. The container therefore carries integrity checks.

An `.ase` file is: the capability descriptor as one UTF-8 JSON line terminated
by `\n`, then a sequence of records, then a trailer.

| Part | Layout |
| --- | --- |
| Record | `uint32 length` (of the payload), payload bytes (one ABF message), `uint32 crc32` of the payload |
| Trailer | ASCII `ASEEND\n`, then `uint64 record_count`, then the 32-byte SHA-256 of every payload byte in order |

**R-9.3** A reader MUST verify each record's CRC-32 (ISO-HDLC, the zlib
polynomial) and MUST reject a record that fails rather than silently passing
corrupted values downstream. A reader MUST verify the trailer digest when the
file is read in full, and MUST report a truncated file — a missing trailer —
as truncated rather than as a short but valid capture.

> Non-normative: per-record CRC rather than per-frame, and a whole-file digest
> rather than a signature. This detects the failure that actually happens — bit
> rot, a half-written file, a truncated copy — without pretending to
> authenticate the device, which a CRC cannot do and which needs the
> `akasara.align.v1` signed record or a platform attestation to do properly.

## 10. Transport bindings

At least one binding MUST be implemented.

**Bandwidth, computed, not assumed.** ABF payload including the 24-byte header:

| dim | rate | float32 | float16 |
| --- | --- | --- | --- |
| 16 | 20 Hz | 14 kbps | 9 kbps |
| 32 | 20 Hz | 24 kbps | 14 kbps |
| 64 | 20 Hz | 45 kbps | 24 kbps |
| 64 | 50 Hz | 112 kbps | 61 kbps |
| 128 | 50 Hz | 214 kbps | 112 kbps |

Against these: BLE 1M PHY delivers ~30–100 kbps of application throughput in
practice; 2M PHY with a 247-byte MTU and a short connection interval reaches a
few hundred kbps at real power cost; USB CDC exceeds all of it trivially.

The honest conclusion, which a vendor should reach before choosing a radio:
**JSON over BLE does not work.** A dim-64 JSON frame is 628 bytes; at 50 Hz that
is 251 kbps, over budget on 1M PHY before protocol overhead. ABF float16 at the
same dim and rate is 61 kbps and fits. Anything at T2/T3 belongs on USB.

### 10.1 BLE GATT

Service and characteristics — 128-bit UUIDs from a base allocated at random for
this specification, per normal Bluetooth practice for non-SIG-adopted services:

| Role | UUID | Properties |
| --- | --- | --- |
| ASE service | `0001cd2c-3660-4e38-98ea-18dca6f5b514` | — |
| Capability | `0002cd2c-3660-4e38-98ea-18dca6f5b514` | read |
| T1 frame | `0003cd2c-3660-4e38-98ea-18dca6f5b514` | notify |
| T0 event | `0004cd2c-3660-4e38-98ea-18dca6f5b514` | notify |
| Control | `0005cd2c-3660-4e38-98ea-18dca6f5b514` | write, notify |
| Self-test | `0006cd2c-3660-4e38-98ea-18dca6f5b514` | read |

Capability and self-test are read in ≤512-byte chunks, offset-addressed, UTF-8
JSON. T1 notifications carry ABF.

**R-10.1** The device MUST NOT require pairing with a vendor application, and
MUST NOT gate these characteristics behind a vendor-specific authentication
characteristic.

**R-10.2 (fragmentation).** Where an ABF message exceeds the negotiated ATT MTU,
each notification MUST begin with a 4-byte fragmentation header: `uint16
msg_id`, `uint8 frag_index`, `uint8 frag_flags` (bit0 = more fragments follow).
`msg_id` increments per message and wraps at 65536. A receiver MUST discard a
partially reassembled message if the next fragment does not arrive within 3× the
declared `latency_max_ms`, and MUST NOT merge fragments across differing
`msg_id`.

### 10.2 USB CDC / serial

ABF messages framed with **COBS** and delimited by a `0x00` byte, or
newline-delimited JSON where the rate table above permits it. Capability is
emitted once on connect, then frames.

> Note: over USB CDC the baud rate setting is a virtual parameter and does not
> limit throughput; on a real UART bridge it does. A device behind a UART bridge
> MUST report the achievable rate in `max_sustained_kbps` (R-4.4) rather than
> assume the host will infer it from a baud setting.

### 10.3 Loopback WebSocket

`ws://localhost:<port>`; JSON as text messages, ABF as binary messages.
Capability is sent as the first message on connect. The listener MUST bind to
loopback only.

### 10.4 Control plane

Available on every binding. Commands, as JSON objects:

| Command | Effect |
| --- | --- |
| `{"cmd":"status"}` | returns `don_count`, current `session_id`/`session_ord`, active tier and encoding |
| `{"cmd":"set_tier","tier":"t1"}` | selects the streaming tier |
| `{"cmd":"set_encoding","venc":"f32"}` | selects the value encoding |
| `{"cmd":"set_adaptive","on":false}` | enters the non-adaptive mode required by R-5.5 |
| `{"cmd":"selftest"}` | runs R-5.7 and returns the vector |
| `{"cmd":"time_echo","token":"…"}` | returns `{token, t_mono_ns}` for R-5.2.1 |

**R-10.3 (multiple hosts).** A device MAY accept only one streaming host at a
time. If it does, it MUST report the rejection reason rather than failing
silently, and MUST NOT reserve the single slot for a vendor application.

### 10.5 Security model

What is being protected: a T1 stream is biometric-grade data about a person's
body, continuously. What is deliberately **not** in scope: this specification
defines no write path to the body, so nothing here can be abused to actuate a
device. That asymmetry is intentional and should survive into any successor.

| Threat | Position |
| --- | --- |
| Passive radio eavesdropper | **R-10.4**: BLE T1 and T0 characteristics MUST require an encrypted link (LE Secure Connections). Just Works pairing is permitted; unencrypted streaming is not. |
| Network attacker reaching the loopback socket | **R-10.5**: the WebSocket listener MUST bind to a loopback address only, MUST reject `Origin` headers it was not configured for, and MUST NOT be exposed on `0.0.0.0` even behind an option. |
| A malicious application on the user's own machine | **Out of scope, and stated rather than hidden.** Once the transport is up, any local process with the same privileges can read frames. Confining that is the host operating system's job — the same position taken for microphones and cameras — and a device-side attempt at it would collapse into the developer-gating that R-7.3 forbids. |
| A vendor exfiltrating the signal | Not addressed by this document. R-7.1 removes the *necessity* of a cloud path; it does not prove the absence of one. That takes network monitoring, not a spec. |
| A forged or replayed capture | Not addressed at Core. A CRC (R-9.3) detects damage, not forgery. Devices needing provenance implement the signed enrollment record of `akasara.align.v1`. |

**R-10.6** A device MUST NOT expose T2 or T3 on a transport with weaker
protection than it applies to T1. Higher tiers are strictly more sensitive.

**R-10.7** Loss of the encrypted link MUST end the session (R-6.1) rather than
resume silently onto a new one; a host MUST be able to see the discontinuity.

## 11. Conformance and claims

**R-11.1** A device is **ASE-0.1 Core conformant** if it satisfies every MUST in
§§3–10 and Appendix A, and passes the reference suite in `conformance/`.

```
node spec/conformance/check.mjs <capability.json> <frames.jsonl> [selftest.json]
node spec/conformance/check.mjs --compare <before.json> <after.json>
```

**R-11.2 (what the suite can and cannot decide).** The suite verifies the
**declarations and the data**: frame structure, clocks, sequencing, montage
completeness, self-test consistency, bandwidth feasibility. Every requirement in
§7 other than R-7.2 is a statement about the vendor's terms and product
behaviour, and the suite can only check that the vendor has *declared* it. A
false declaration is a false statement by the vendor, not a test failure. This
line is stated here so that no one mistakes a green run for an audit. R-11.5 is
likewise outside the suite: it is measured on the vendor's own data, which the
suite never sees, so the suite can check only that the required margin, task,
subject count and bootstrap unit have been published.

**R-11.3 (claiming conformance).** A conformance claim MUST take the form
"ASE-0.1 Core conformant" optionally followed by badges, MUST name the exact
firmware version tested, and MUST be accompanied by the published capability
descriptor and suite output. Claims MUST NOT be made for a device family, a
roadmap, or an unreleased version. "ASE-compatible", "ASE-ready", and
"supports ASE" are not defined by this document and mean nothing.

**R-11.4 (self-certification, and its limits).** There is no fee, no gatekeeper,
and no approved-vendor list — a spec that gates its own conformance reproduces
the problem it exists to solve. There is also, therefore, no authority that can
revoke a claim. The remedy for a false claim is the same as for any other false
product statement: it is checkable by anyone in minutes, and consumer-protection
law already covers verifiably untrue advertising.

### 11.5 Feature-space floor

§14 records that ASE constrains the *form* of a T1 feature space and not its
information content, so a vendor could ship something conformant and useless.
That gap is now partly closed: a reference task does separate them.

Reference task, as run: Ninapro DB5, 6 subjects, 30 ordered subject pairs, 52
shared movements, features fitted per pair on training movements only,
single-trial calibration-free retrieval of held-out movements, chance 0.062.
Features are computed after removing each channel's DC pedestal, on both this
dataset and the next — see the retraction further down for why that is stated.

| Feature space | P@1 | × chance |
| --- | --- | --- |
| MAV only, 16 d | 0.300 | 4.8 |
| WL only, 16 d | 0.300 | 4.8 |
| full 64 d (MAV+RMS+WL+VAR) | 0.288 | 4.6 |
| full, 8-bit quantised | 0.288 | 4.6 |
| VAR only, 16 d | 0.256 | 4.1 |
| channel-mean, 4 d | 0.132 | 2.1 |
| total energy, 1 d | 0.110 | 1.8 |

Paired across pairs: full vs channel-mean **+0.156, CI [+0.141, +0.171]** — the
task separates a real feature space from a degenerate one decisively.

**An absolute threshold was drafted here and then withdrawn.** The first version
of this section proposed a floor of "≥ 3.5× chance". Replicating on a second
dataset killed it, and auditing that replication then killed one of the two
reasons first given for the withdrawal. Both are recorded below, because the
retracted one is the more useful warning.

Second dataset: Hyser HD-sEMG (256-channel grid, 2048 Hz, 6 subjects, 30 ordered
pairs — the same pair count as the DB5 leg — 32 shared gestures, chance 0.100).
Both columns are measured with the per-channel DC pedestal removed; see the
retraction below for why that matters:

| Feature space | DB5 (16-ch ring) | Hyser (256-ch grid) |
| --- | --- | --- |
| full (MAV+RMS+WL+VAR) | 0.288 (4.6×) | 0.198 (2.0×) |
| full, 8-bit quantised | 0.288 (4.6×) | 0.198 (2.0×) |
| WL only | 0.300 (4.8×) | **0.199 (2.0×)** |
| MAV only | **0.300 (4.8×)** | 0.161 (1.6×) |
| VAR only | 0.256 (4.1×) | 0.147 (1.5×) |
| channel-mean 4 d | 0.132 (2.1×) | 0.133 (1.3×) |
| total energy 1 d | 0.110 (1.8×) | 0.109 (1.1×) |

- **The absolute multiple of chance does not transfer.** Hyser's *best* feature
  space reaches 2.0× — below the 3.5× that was about to be written down. A vendor
  with a perfectly good HD-sEMG feature space would have been judged
  non-conformant by that floor. This is not an artefact of the two legs using
  different retrieval sizes (a multiple of chance is not comparable across *N*):
  re-running Hyser at DB5's exact settings, 16-way with k = 30, still gives a
  best of 2.4× (measured on the four subjects available when that check was run).
- **What holds on both is relative:** a real feature space beats its own
  degenerate reduction — DB5 +0.156, CI [+0.141, +0.171]; Hyser +0.065, CI
  [+0.049, +0.083]. And 8-bit quantisation is free in both (0.288 vs 0.288;
  0.198 vs 0.198), which is what makes §9.2's lossy encodings defensible.
- **Retracted: a claimed second failure, "the ranking of features does not
  transfer either."** The first Hyser run reported MAV-only as the best space on
  DB5 and near chance (1.1×) on Hyser, and this document quoted it. That was a
  defect in the loader used here, not a property of HD-sEMG. Hyser's WFDB header
  gives every channel its own `baseline`; the loader read the raw `.dat` without
  the header, so MAV = mean |x| and RMS were computed on a signal sitting on a
  per-electrode DC pedestal (|channel mean| = 0.365 of channel std), while WL (a
  difference) and VAR (mean-subtracted) are DC-immune by construction — which is
  exactly the ranking that was reported and mistaken for a finding. Removing the
  pedestal moves MAV from 1.1× to 1.6× (+0.049, positive on 27 of 30 pairs) and
  leaves WL and VAR bit-identical, which is the check that the correction changed
  only what it should. The corrected sets fall in one band, 1.5–2.0×, with no
  inversion left to explain. DB5 carries the same pedestal but a much smaller one
  (0.124 of std) and is unmoved by the correction (full +0.0015), so the
  cross-dataset comparison above is now on one footing rather than two pipelines.

**Third leg, on a different modality.** Both datasets above are sEMG, so the
criterion could still have been a fact about muscle. It was re-run on EEG:
ds007822 Prisoner's-Dilemma hyperscanning, 11 triads × 3 players, 19-channel
10-20 at 300 Hz. Different physics, different montage, and a different transfer
task — two players in a triad live the same game round, so an ordered pair is
scored by retrieving held-out rounds, and two players from *different* triads
never shared a round and give a real null rather than a shuffle. Feature space is
per-round log band-power, 19 channels × 5 bands; every reduction below is a
reduction of that same tensor. 66 within-triad ordered pairs, chance 0.083:

| Feature space | P@1 | × chance | vs channel-mean 5 d |
| --- | --- | --- | --- |
| full 95 d | 0.151 | 1.8× | **+0.040, CI [+0.031, +0.049]** |
| full, 8-bit quantised | 0.151 | 1.8× | +0.040, CI [+0.031, +0.049] |
| gamma only, 19 d | 0.157 | 1.9× | +0.046, CI [+0.033, +0.060] |
| beta only, 19 d | 0.148 | 1.8× | +0.038, CI [+0.026, +0.049] |
| band-mean, 19 d | 0.141 | 1.7× | +0.030, CI [+0.019, +0.041] |
| theta only, 19 d | 0.107 | 1.3× | −0.004, CI [−0.014, +0.006] |
| alpha only, 19 d | 0.104 | 1.2× | −0.007, CI [−0.018, +0.005] |
| channel-mean, 5 d | 0.111 | 1.3× | — |
| total power, 1 d | 0.097 | 1.2× | — |

Three things this settles, and one it does not:

- **The relative criterion holds on a third dataset and a second modality.** The
  full space beats its own channel-mean reduction on 55 of 66 pairs with a CI
  clear of zero. Repeating under a drift control — candidate rounds forced ≥ 3
  and ≥ 5 rounds apart, so nothing is winnable from slow within-session drift
  alone — gives +0.043 and +0.076, both still clear of zero.
- **The criterion is not vacuous: it fails things.** Alpha-only and theta-only
  are perfectly conformant T1 spaces and do *not* beat the channel-mean
  reduction, in every one of the three settings. A criterion that everything
  passes would be decoration; this one separates.
- **8-bit quantisation is free on a third modality too** (−0.0002, CI
  [−0.0008, +0.0004]), which is now three datasets supporting §9.2.
- **What it does not settle: the criterion does not certify that a space carries
  the *intended* information.** Most of the full-vs-channel-mean margin is also
  present between players who never shared a round (cross-triad 0.131 vs 0.098).
  The margin therefore says "this space carries more cross-user-transferable
  structure than its degenerate twin", not "this space carries shared state". The
  genuinely shared-state part is the within-minus-cross difference, +0.020 (CI
  [+0.006, +0.033]) for the full space, real but much smaller. A vendor could pass
  §11.5 on generic structure. That is a limit of what a *feature-space* floor can
  ever check, not a defect to be tuned away.

**Criterion, now normative at SHOULD level (was provisional and non-normative):**

**R-11.5** A T1 feature space offered for cross-user use SHOULD beat the
channel-mean reduction of *itself*, on the vendor's own data and the vendor's own
transfer task, by a margin whose 95% confidence interval excludes zero; a vendor
publishing such a margin MUST also publish the task, the number of independent
subjects, and the unit over which the interval was bootstrapped. It remains
SHOULD and not MUST because the task is vendor-chosen and, per the bullet above,
the margin can be earned from structure other than the intended signal. A floor
MUST NOT be expressed as a minimum `dim` — dimension count is not merit, and on
DB5 the 16-d MAV set beat the 64-d full set (+0.016, CI [+0.009, +0.024]).

Honest limits. The three legs are 6 subjects / 30 pairs (DB5), 6 subjects / 30
pairs (Hyser), and 33 subjects / 66 pairs (EEG). In none of them are the pairs
independent — each subject appears in several — so a bootstrap over pairs gives a
narrower interval than a subject-level test would, which is why R-11.5 obliges a
vendor to name the unit. No headline claim rests on the interval alone: the
Hyser retraction moves 27 of 30 pairs and the EEG margin 55 of 66. Three legs is
still three legs, and no absolute score is claimed for any of them — 4.6×, 2.0×
and 1.8× on the three datasets is the whole reason the floor is relative.

One parameter in this area remains unmeasured and is not measured here: R-7.5.1's
"~20 donning sessions". Hyser carries two sessions per subject, which bounds only
the data-volume half. A dataset that could settle the donning-diversity half does
exist — CEMHSEY, 11 consecutive days with the grids re-applied each day, Zenodo
10.5281/zenodo.14224328 and .14272463 — but 11 days is not 20, so it would move
the parameter from asserted to partially bounded rather than to measured. It is
recorded here as the next thing to run, not as a result.

The general lesson, recorded because it is cheap and this document paid for it
twice: a number that reaches a spec must be replicated on a second dataset, and
the loader that produced it must be checked against the dataset's own header
before the result is described as a property of the signal.

## 12. Intellectual property

**12.1 Copyright.** This specification text is © 2026 breadMSA and licensed
**CC BY 4.0**. You may copy, quote, translate, and redistribute it, including
commercially, with attribution. Reference code in `conformance/` and `schema/`
is licensed **Apache-2.0**; see `LICENSE-CODE`.

**12.2 Patent commitment.** The editor makes a **royalty-free, irrevocable,
worldwide, non-exclusive** commitment not to assert any patent claim he owns or
controls that is *necessarily infringed* by implementing the required portions
of this specification, against any party implementing it. This commitment:

- covers ASE-Core and the open `ase.t2` / `ase.t3` badges;
- runs with the specification, binds successors, and survives transfer;
- is **not** conditioned on any licence, fee, membership, or contact; and
- may be **suspended, as to a specific party only**, if that party asserts a
  patent claim against any ASE implementation — the standard defensive
  termination, and the only carve-out.

The editor holds no issued patents relevant to this document as of the draft
date. This clause exists so that a vendor's counsel does not have to take that
on trust, and so that it remains true if that changes.

**12.3 Trademark, stated honestly.** "ASE" and "Akasara Signal Export" are not
registered marks as of this draft, and no certification mark exists yet. The
practical position: anyone may state an accurate conformance claim per R-11.3
without permission, and nothing here restricts that. If a certification mark is
later registered, it will be registered for the purpose of **policing false
claims**, and accurate claims made under this section will remain permitted
without fee. Vendors should not build brand dependence on an ASE badge until
that exists.

**12.4 No warranty.** The specification and the reference code are provided "as
is", without warranty of any kind. Conformance is not a safety, security,
medical, or regulatory certification, and it does not substitute for any
approval a device requires in its market.

## 13. Governance

**13.1 Current state, stated plainly.** This is a single-editor specification
with no organisation behind it. A vendor is entitled to weigh that, so it is
written here rather than left to be discovered.

**13.2 Change process.** Errata and clarifications that do not change what a
conformant device must do may be issued at any time and are recorded in
`CHANGELOG.md`. Anything that changes a requirement increments the minor version
(0.1 → 0.2) and MUST include a migration note stating what a 0.1-conformant
device must do, if anything, to remain conformant. Requirement identifiers are
**never reused or renumbered**; a withdrawn requirement is marked withdrawn and
its number retired.

**13.3 Version negotiation.** A host MUST accept a descriptor whose
`ase_version` differs from its own and MUST ignore fields it does not
understand. A device MUST NOT refuse a host on version grounds. Within 0.x,
compatibility is best-effort and the descriptor is the authority.

**13.4 Registries.** New montage systems, profiles, `signal.kind` values, and
value encodings are added by pull request to this repository (Appendix B).
Vendor-specific extensions need no permission: prefix them with a reverse-DNS
vendor string (`com.example.foo`) and they will never collide with a registered
name. Registered names are lower-case, dotted, and versioned.

**13.5 Succession and abandonment.** If the editor becomes unreachable for 12
consecutive months, this specification is deemed permanently frozen at its last
published version, and every grant in §12 remains in force irrevocably. No
implementer is ever stranded by the editor's absence — the worst case is a
specification that stops improving, not one that stops being safe to implement.

## 14. Open issues for 0.2

- `ase.limb.v1` fixes an origin at a named landmark but says nothing about how
  the device knows where that landmark is; in practice the user positions the
  band by eye. **Partly retired** by R-4.2.2: the measured cost of getting it
  wrong is ~9% at worst within one electrode spacing, and whole-electrode error
  is free, so the descriptor does not need millimetres. What remains open is
  axial (along-limb) placement, which was not tested and is not permutation-like.
- `ase.opaque.v1` still cannot be compared **across models**. R-4.2.1 recovered
  the within-model case, which is the one that actually occurs; cross-model
  comparability for opaque geometries is genuinely unsolved and may not be
  solvable from a descriptor alone.
- The feature-space criterion (§11.5) stays **relative**, because three datasets
  now show that an absolute multiple of chance does not transfer between sensor
  geometries (4.6×, 2.2×, 1.8×). (A companion claim, that the *ranking* of
  features does not transfer either, was retracted in §11.5 — it was a loader
  defect.) It is no longer non-normative: a third leg on EEG carried it to a
  second modality, so it is now **R-11.5 at SHOULD level**. What keeps it off
  MUST is the remaining open item, and it is a different one than before: the
  transfer task is vendor-chosen, and the margin can be earned from generic
  transferable structure rather than the intended signal — most of the EEG margin
  survives between people who never shared a round. Closing that needs a task a
  vendor cannot overfit, not another modality.
- Enrollment data volume saturates around ~100 single-session trials on Hyser
  (P@1 0.132 at ~40 trials, 0.164 at ~100, 0.166 at ~200). That bounds the
  data-volume half of R-7.5.1's parameter; the donning-diversity half still does
  not have a dataset (two sessions per subject is not a learning curve).
- Whether a second donning helps or hurts enrollment is **not resolved**: Hyser
  cross-day vs same-day came out −0.015 with CI [−0.039, +0.011] over 6 pairs,
  i.e. no detectable effect at this power, which contradicts neither exp-22's
  positive nor a null.
- Self-test (R-5.7) proves the transform is unchanged. It does not prove the
  transform is applied to real acquisition — a device could pass self-test and
  still stream garbage. Detecting that needs a physical fixture.
- The security model (§10.5) leaves same-machine isolation to the host OS. That
  is defensible for a read-only export spec and would be indefensible the moment
  any successor adds a write path.
- The 90-day floor in R-7.5.1 now rests on **one** unmeasured parameter, not
  two: wear frequency is sourced (Rock Health 2025, N = 8,000), but the
  ~20-donning enrollment target is still an extrapolation. Public cross-day EMG
  datasets carry two sessions per subject, which cannot locate a saturation
  point; this needs a many-donning dataset or vendor telemetry.
- `time_echo` stays a SHOULD, now on evidence at the document's own window
  lengths rather than at gesture granularity (R-5.2.1). The untested case is a
  workload that pairs two people sample-by-sample rather than event-by-event.
- R-5.7 self-test proves the transform is unchanged, not that it is applied to
  real acquisition. Closing this needs a signal injected at the electrodes and a
  conformant device to inject it into — so it is blocked on a first implementer,
  not on money or effort. It is the only open issue with that property.

## Appendix A — `quality` per signal kind (normative)

`quality` answers one question: *how much should a consumer discount this
frame?* It is a measurement, never a classifier's confidence (R-5.6).

**sEMG** — per channel, derived from electrode-skin impedance where measurable,
otherwise from a documented proxy. 1.0 = impedance within the vendor's stated
operating band; 0.0 = open contact. Power-line contamination (50/60 Hz band
power relative to signal band) MUST be folded in, as it is the dominant contact
failure mode in practice.

**EEG** — per channel: impedance in the stated band, plus railing/saturation
fraction over the window. Devices with dry electrodes SHOULD report the
impedance estimate itself in the descriptor alongside the normalised value,
since dry-electrode operating bands are not comparable to wet.

**Implanted / spike** — per channel or per array: fraction of the window lost to
artifact rejection, and whether the channel is currently included in the
device's own decoding. A channel the device has itself excluded MUST report
below 0.5.

**IMU / eye / face** — per channel tracking validity; for optical methods,
occlusion fraction over the window.

Any `kind` not listed: the vendor MUST document its own definition and MUST
state the failure mode it captures. An undocumented `quality` is a violation of
R-5.6 even when the number is present and in range.

## Appendix B — Registries

| Registry | Values in 0.1 | How to add |
| --- | --- | --- |
| Montage systems | `ase.eeg.1020.v1`, `ase.limb.v1`, `ase.face.v1`, `ase.opaque.v1` | PR per §13.4 |
| Profiles | `ase.t2`, `ase.t3`, `akasara.align.v1` | PR; profile must not weaken §§3–7 |
| `signal.kind` | `semg`, `eeg`, `ecog`, `spike`, `eog`, `imu`, `mixed`, `other` | PR with an Appendix A entry |
| Value encodings | `f32` (0x00), `f16` (0x01), `i16+scale` (0x02) | PR; must state exactness vs R-5.7 |
| Control commands | `status`, `set_tier`, `set_encoding`, `set_adaptive`, `selftest`, `time_echo` | PR |

Vendor extensions use a reverse-DNS prefix and are never registered.
