# ASE-0.1 — Akasara Signal Export

**Status:** Draft. **Date:** 2026-07-27. **Editor:** breadMSA.
**Applies to:** any body-signal input device — surface EMG bands, EEG headsets,
eye/face trackers, implanted or future neural interfaces.

## 0. What this specifies, and what it does not

This document specifies **how a wearable makes the signal it already records
available to software the user chooses**, and the minimum fidelity at which it
must do so.

It does **not** specify electrodes, materials, radios, connectors, enclosure,
decoding algorithms, or what the device is for. Those stay the vendor's.

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

## 2. Terminology

MUST / MUST NOT / SHOULD / MAY per RFC 2119.

- **Device** — the hardware plus its firmware.
- **Host** — software on a machine the user controls, receiving exported data.
- **Feature space** — the (dimension, semantics, producing-model) triple that a
  T1 vector lives in.
- **Session** — a continuous period of wear. Ends at doff, power loss, or
  re-seat.

## 3. Export tiers

| Tier | Content | Certified as |
| --- | --- | --- |
| **T0** | Discrete events: recognised gestures, keys, commands | not sufficient alone |
| **T1** | Fixed-dimension numeric feature or latent vector per analysis window | **required** |
| **T2** | Continuous per-channel stream after fixed, documented filtering | optional badge |
| **T3** | Raw samples at ADC resolution and native rate | optional badge |

**ASE-Core conformance requires T1.** A device that also emits recognised events
MUST expose them as T0 alongside T1, never instead of it.

T2 and T3 are declared as `ase.t2` / `ase.t3` badges. They are encouraged for
research-grade devices and not expected of consumer ones.

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
    "documentation": "https://example.com/ase/tdfeat-v3"
  },
  "transport": ["ws://localhost:7654", "usb-cdc"],
  "requires_account": false,
  "requires_network": false
}
```

**R-4.2 (montage).** `signal.montage` MUST be a structured descriptor in a named
coordinate system, not a free string. Two montages are **comparable** if and
only if a third party can decide it from the descriptors alone, which requires:

| Field | Requirement |
| --- | --- |
| `system` | one of the registered systems below |
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
  (implanted arrays, novel geometries). `positions[]` MAY be omitted. **A device
  declaring `ase.opaque.v1` is ASE-Core conformant but is not montage-comparable
  with anything, including another unit of the same model.** The suite reports
  this rather than failing it.

Tolerance for comparability is not fixed by this document; it belongs to the
consumer of the data. The descriptor's job is to make the question answerable.

## 5. T1 frames

**R-5.1** Each T1 frame MUST carry: `t_mono_ns`, `t_wall_ms`, `session_id`,
`seq`, `feature_space`, `values` (array of `dim` finite numbers), and
`quality`. Schema: `schema/frame.schema.json`.

**R-5.2** `t_mono_ns` MUST come from a monotonic device clock that does not jump
on wall-clock adjustment, and MUST refer to the **end of the analysis window**,
not the time of transmission.

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

**R-5.6** `quality` MUST report at minimum contact/impedance adequacy per channel
or an aggregate 0..1, and MUST be produced by measurement, not by the classifier's
confidence. Per-`kind` definitions are in Appendix A.

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
rate: per channel *c*, sample *n*, at rate *fs*, over 2.000 s —

```
x[c][n] = 0.5·sin(2π(20+7c)·n/fs) + 0.2·sin(2π(150+11c)·n/fs) + 0.05·r[c][n]
```

where `r` is the first 2·fs outputs of a xorshift32 PRNG seeded with `c+1`,
scaled to [-1, 1]. Units are full-scale, so the device applies its normal
scaling to it.

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

**R-6.2** The descriptor MUST expose `don_count` and, where measurable, an
indication of placement shift within a session.

> Non-normative: cross-day and cross-donning drift is the dominant failure mode
> for any map fitted on this data. A host that cannot see where sessions break
> cannot compensate for drift it cannot see.

## 7. Access, locality, and rights

**R-7.1 (local interface).** T1 export MUST be reachable over a local interface
— USB, BLE GATT, or a loopback socket — with **no vendor cloud round-trip, no
network connectivity, and no account**. A vendor cloud API MAY exist in
addition. It does not satisfy this requirement.

**R-7.2 (live rate).** Exported T1 MUST be available at the device's native
frame rate. Deliberate rate reduction, batching delays beyond documented
latency, or quota-limiting the local interface below live rate is
non-conformant.

**R-7.3 (user authorisation, not vendor approval).** Access MUST be grantable by
the user to software of the user's choice. A conformant device MUST NOT restrict
T1 export to an approved-developer programme, a signed application list, or an
app store.

**R-7.4 (no cross-user restriction).** The device's terms MUST NOT prohibit the
user, or software acting for the user, from processing exported frames jointly
with frames exported by another person's device, where each person has
authorised it.

> Non-normative: R-7.4 is the clause that decides whether an interoperability
> layer between people can legally exist. Read the enacted neural-data statutes
> (CA, CO, CT, MT; EU Data Act portability): they establish user ownership and
> portability of the data, and none of them, as of this draft, addresses
> cross-user joint processing. That silence is currently filled by terms of
> service. R-7.4 fills it the other way.

**R-7.5 (no silent downgrade).** A firmware update MUST NOT remove a certified
tier, remove a transport, or change a `feature_space`, without explicit
user-visible notice at install time.

**R-7.5.1 (refit window).** After a `feature_space` change, the device MUST keep
the previous feature space selectable until the user has completed a
re-enrollment under the new one, and in any case for no less than **90 days**.
Firmware that changed `t1.feature_space` MUST declare `previous_feature_space`
in its descriptor for the duration of the window, so that the window's existence
is externally checkable rather than promised.

> Derivation, and its limits. The window exists for one purpose: to let a user
> re-fit whatever was built on the old feature space before it disappears. So it
> must cover a full re-enrollment, and re-enrollment is bounded by *donning
> sessions*, not by compute — cross-day and cross-donning variation is the
> dominant term, so sessions must be spread across distinct days.
>
> Taking ~20 distinct donning sessions as the enrollment target and consumer
> wear at ~3 sessions/week gives ~7 weeks of active wear. Doubling for interruption
> (travel, illness, a device left in a drawer) gives ~14 weeks ≈ 90 days.
>
> Both parameters are estimates, not measurements: 20 sessions is extrapolated
> from the fitting behaviour we have observed offline, and 3/week is an
> assumption about consumer wear with no citation behind it. The number is
> therefore a **policy floor derived from stated assumptions**, and it is stated
> that way deliberately — a reader who disagrees with either parameter can see
> exactly which one to argue with. The completion condition, not the day count,
> is the substantive requirement; the floor only stops a vendor from declaring
> re-enrollment "complete" the moment it ships.

**R-7.6 (export on demand).** Beyond live streaming, the user MUST be able to
export retained data in the same frame format. Proprietary-only export
containers are non-conformant.

## 8. Profiles

A profile is an optional capability declared in `profiles[]`, layering
additional requirements on ASE-Core. Profiles do not change Sections 3–7.

Registered:

| Profile id | Adds | Availability |
| --- | --- | --- |
| `ase.t2`, `ase.t3` | higher tiers per §3 | open |
| `akasara.align.v1` | **Anchored enrollment**: the device can lock exported frames to an externally presented stimulus schedule with bounded, reported timing error (target ≤ 10 ms), and can emit a signed enrollment record covering a full anchor run. This is what allows an encoder fitted on one person to be related to one fitted on another. | licensed separately; contact the editor |

A device implements `akasara.align.v1` by satisfying the timing and record
requirements. The anchor material and the fitting procedure are not part of this
document and are not required to build a conformant device.

## 9. Conformance and testing

A device is **ASE-0.1 Core conformant** if it satisfies every MUST in §§4–7 and
passes the reference suite in `conformance/`.

```
node spec/conformance/check.mjs <capability.json> <frames.jsonl>
```

The suite reports per-clause pass/fail. It is deliberately runnable by a vendor
before ever contacting anyone: self-certification, published results, no
gatekeeper, no fee. Test vectors — one conformant, several instructively
non-conformant — are in `conformance/vectors/`.

Claiming conformance means publishing the descriptor and a suite run. Nothing
else.

## 10. Transport bindings

At least one binding MUST be implemented. All three carry the same JSON objects
defined in §4 and §5; bindings differ only in framing.

### 10.1 BLE GATT

Primary service and characteristics (128-bit, assigned by this document):

| Role | UUID | Properties |
| --- | --- | --- |
| ASE service | `0001cd2c-3660-4e38-98ea-18dca6f5b514` | — |
| Capability | `0002cd2c-3660-4e38-98ea-18dca6f5b514` | read |
| T1 frame | `0003cd2c-3660-4e38-98ea-18dca6f5b514` | notify |
| T0 event | `0004cd2c-3660-4e38-98ea-18dca6f5b514` | notify |
| Control | `0005cd2c-3660-4e38-98ea-18dca6f5b514` | write, notify |
| Self-test | `0006cd2c-3660-4e38-98ea-18dca6f5b514` | read |

Capability and self-test are read in ≤512-byte chunks, offset-addressed, UTF-8
JSON. Frame notifications carry one complete JSON object per notification;
devices MUST negotiate an ATT MTU large enough for one frame, or fragment with a
1-byte header `(seq_low << 1) | more`. Control accepts
`{"cmd":"set_tier"|"set_adaptive"|"selftest", ...}`.

**R-10.1** The device MUST NOT require pairing with a vendor application, and
MUST NOT gate these characteristics behind a vendor-specific authentication
characteristic.

### 10.2 USB CDC / serial

Newline-delimited JSON, one object per line, UTF-8, no framing header.
Capability is emitted once on connect, then frames. 921600 baud or higher for
`dim ≥ 32` at 20 Hz.

### 10.3 Loopback WebSocket

`ws://localhost:<port>`, one JSON text message per object; capability sent as
the first message on connect. The listener MUST bind to loopback only.

## 11. Open issues for 0.2

- `ase.limb.v1` fixes an origin at a named landmark but says nothing about how
  the device knows where that landmark is; in practice the user positions the
  band by eye. The descriptor is honest about intent, not about millimetres.
- `ase.opaque.v1` is a real hole, deliberately left open: a device can be fully
  conformant and still not comparable to anything. It exists so implanted and
  novel geometries are not forced into a false vocabulary.
- No `kind`-specific requirement yet distinguishes a *good* T1 feature set from a
  conformant one. The spec constrains form, not information content, and a vendor
  can ship a conformant, useless feature space.
- Self-test (R-5.7) proves the transform is unchanged. It does not prove the
  transform is applied to real acquisition — a device could pass self-test and
  still stream garbage. Detecting that needs a physical fixture.
- No security model. Any local process can read frames once the transport is up;
  host-side authorisation is out of scope and probably should not be.
- Fragmentation header in §10.1 has a 128-frame wrap and no reassembly timeout.

## Appendix A — `quality` per signal kind

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
