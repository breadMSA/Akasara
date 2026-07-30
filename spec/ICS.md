# ASE-0.1 — Implementation Conformance Statement (ICS)

**Form to be completed by the vendor.** One row per requirement in `ASE-0.1.md`.
Fill the **Supported** column, sign the declaration at the bottom, and publish
this alongside the capability descriptor and the suite output required by
R-11.3.

This form is **not** normative. `ASE-0.1.md` governs; if a summary here differs
from the clause it points at, the clause wins. The summaries are compressions,
not the requirement — read the clause before answering the row.

## How to fill it in

**Supported** — one of:

| | |
| --- | --- |
| **Y** | Implemented as written. |
| **N** | Not implemented. Any **N** on a MUST row means the device is **not** ASE-0.1 Core conformant. Say so rather than leaving the row blank. |
| **N/A** | The requirement's precondition does not apply to this device (e.g. R-4.2.2 on a non-circumferential array). Give the reason in Notes; "N/A" without a reason reads as an evasion. |
| **—** | Not a vendor obligation. Pre-filled; nothing to answer. |

**Checked by** — how the answer can be tested by a third party:

| | |
| --- | --- |
| **suite** | `conformance/check.mjs` decides this from your descriptor and frames. |
| **declaration** | The suite can only record that you declared it. Nobody can verify it from the data — it is a statement about your terms, your firmware process, or your product behaviour. A false answer here is a false product statement, not a test failure (R-11.2). |
| **inspection** | Testable by a third party with the device in hand, but not by the suite. |

Rows marked **declaration** are the ones that carry your name rather than a
green tick. Eighteen of the 43 answerable rows depend on one, wholly or in part,
and they are the honest centre of this form.

## §3 — Export tiers

| Req | Status | What you are asserting | Checked by | Supported | Notes |
| --- | --- | --- | --- | --- | --- |
| R-3.1 | MUST | T1 export exists; T1 is what Core conformance requires | suite | | |
| R-3.2 | MUST | If the device emits recognised events, they are exposed as T0 *alongside* T1, never instead of it | inspection | | |
| R-3.3 | MAY | T2/T3, if offered, are declared as the `ase.t2` / `ase.t3` badges | suite | | |

## §4 — Capability descriptor

| Req | Status | What you are asserting | Checked by | Supported | Notes |
| --- | --- | --- | --- | --- | --- |
| R-4.1 | MUST | A machine-readable capability descriptor is exposed over the local interface before any data flows | suite | | |
| R-4.2 | MUST | `signal.montage` is a structured descriptor in a registered coordinate system, not a free string | suite | | |
| R-4.2.1 | MUST | If using `ase.opaque.v1`: `geometry_id` is declared, identical across interchangeable units and different as soon as they are not | suite | | |
| R-4.2.2 | MUST | Circumferential arrays: `angle_deg` accurate to within half an electrode spacing. (Consumers MUST NOT assume finer.) | declaration | | |
| R-4.2.3 | MUST | `axial_mm` declared for every channel in `ase.limb.v1` | suite | | |
| R-4.3 | MUST | `clock` block declares RTC presence, monotonic epoch, and worst-case oscillator drift in ppm | suite | | |
| R-4.4 | MUST | Every `transport[]` entry states URI, encodings, and `max_sustained_kbps`; at least one can carry the live T1 rate | suite | | |

## §5 — T1 frames

| Req | Status | What you are asserting | Checked by | Supported | Notes |
| --- | --- | --- | --- | --- | --- |
| R-5.1 | MUST | Every frame carries `t_mono_ns`, `session_id`, `seq`, `feature_space`, `values`, `quality`; `t_wall_ms` present iff the device has an RTC | suite | | |
| R-5.2 | MUST | `t_mono_ns` is monotonic, refers to the **end of the analysis window**, epoch is boot or session — never the Unix epoch; no invented wall clock | suite | | |
| R-5.2.1 | SHOULD | `time_echo` control command implemented so a host can place device time on its own clock | inspection | | |
| R-5.3 | MUST | Sensor-to-host latency documented; frames never reordered; gaps visible as `seq` gaps, never concealed by renumbering | suite (partial) | | |
| R-5.4 | MUST | `feature_space` changes on **any** change to the producing transform, including an improvement you shipped in a firmware update | declaration | | |
| R-5.4.1 | MUST | `t1.layout` is `feature-major`, `channel-major` or `opaque`; if not opaque, `dim` is a multiple of `signal.channels` | suite | | |
| R-5.5 | MUST | No undeclared per-user adaptation of exported T1; if adaptive, `adapt_state` is carried and a non-adaptive mode exists | declaration | | |
| R-5.6 | MUST | `quality` is a measured 0..1 aggregate or exactly `signal.channels` values — never classifier confidence; per-kind definitions in Appendix A are normative | suite (shape) / declaration (provenance) | | |
| R-5.7 | MUST | A self-test runs the **exact production transform** over `ase.selftest.v1` and the descriptor publishes `expected` + `tolerance` | suite | | |
| R-5.7.1 | MUST | The published vector is the last analysis window ending at or before t = 2.000 s; no averaging, not the first window | declaration | | |
| R-5.7.2 | MUST | `tolerance` is at least your own build-to-build variation; the self-test bypasses acquisition and adaptation and is **not** special-cased | declaration | | |

> R-5.7.2 is the row most worth pausing on. A device that computes its self-test
> output by any path other than the production transform is non-conformant, and
> the suite cannot see the difference. This row is the whole reason the self-test
> means anything.

## §6 — Session and wear state

| Req | Status | What you are asserting | Checked by | Supported | Notes |
| --- | --- | --- | --- | --- | --- |
| R-6.1 | MUST | A new `session_id` at every don, re-seat, or power cycle; never continued across removal | suite (visible) / declaration (trigger) | | |
| R-6.2 | MUST | `don_count` exposed, plus within-session placement shift where measurable; `don_count` also obtainable any time via `status` | suite | | |

## §7 — Access, locality, and rights

*Every row in this section except R-7.2 is a **declaration**. This is stated in
R-11.2 and repeated here so it is unmissable: a green suite run says nothing
about §7.*

| Req | Status | What you are asserting | Checked by | Supported | Notes |
| --- | --- | --- | --- | --- | --- |
| R-7.1 | MUST | T1 reachable over USB, BLE GATT, or a loopback socket with **no vendor cloud round-trip, no network, no account**. A cloud API may exist but does not satisfy this | declaration | | |
| R-7.2 | MUST | T1 available at native frame rate on at least one declared transport; no deliberate rate reduction or quota on the local interface | suite | | |
| R-7.3 | MUST | Access is grantable by the **user** to software of the user's choice. No approved-developer programme, signed-app list, or app store gate. (User consent, revocation, audit logging are all permitted.) | declaration | | |
| R-7.4 | MUST NOT | Your terms do **not** prohibit a user from processing their frames jointly with another consenting person's frames. Paste the model wording in §7 or cite your own clause | declaration | | ← cite clause + URL |
| R-7.5 | MUST NOT | No firmware update removes a certified tier or transport, or changes a `feature_space`, without user-visible notice at install | declaration | | |
| R-7.5.1 | MUST | After a `feature_space` change the previous one stays **obtainable** until re-enrollment completes, minimum 90 days; `previous_feature_space` declared for the window | suite (declaration present) / declaration (the 90 days) | | state which route: mode / downgrade image / setting |
| R-7.6 | MUST | Retained data exportable in a §9 encoding. Proprietary-only export containers are non-conformant | inspection | | |
| R-7.7 | — | *Nothing here makes you a controller or processor of exported data, or obliges you to support downstream use.* Protection for you, not an obligation | — | — | — |

## §8 — Profiles

| Req | Status | What you are asserting | Checked by | Supported | Notes |
| --- | --- | --- | --- | --- | --- |
| R-8.1 | MUST NOT | *Binds the editor, not you:* Core conformance is never conditioned on taking a profile licence. You may ship, certify and advertise Core without ever contacting the editor | — | — | — |

## §9 — Encodings

| Req | Status | What you are asserting | Checked by | Supported | Notes |
| --- | --- | --- | --- | --- | --- |
| R-9.1 | MUST NOT | float16/int16 not used where quantisation exceeds your declared `tolerance`; `t1` declares which encodings are lossless for your feature space | declaration | | |
| R-9.2 | MUST | Unknown `type` values and trailer bits are skippable; a receiver never desynchronises | inspection | | |
| R-9.3 | MUST | `.ase` readers verify per-record CRC-32 (ISO-HDLC) and reject failures; verify the trailer digest on full read; report a missing trailer as truncated | inspection | | writer-side only if you do not ship a reader |
| R-9.4 | MUST | fixed-point `quality_q` and per-channel quality are produced by `floor(v x max + 0.5)` — half away from zero, not the half-to-even some languages default to | inspection | | byte-level; two conformant codecs disagreed here before the clause existed |

## §10 — Transport bindings

| Req | Status | What you are asserting | Checked by | Supported | Notes |
| --- | --- | --- | --- | --- | --- |
| R-10.1 | MUST NOT | No pairing with a vendor application required; no vendor-specific auth characteristic gating T1/T0 | inspection | | |
| R-10.2 | MUST | BLE: 4-byte fragmentation header; reassembly times out at 3× `latency_max_ms`; fragments never merged across differing `msg_id` | inspection | | N/A if no BLE binding |
| R-10.3 | MAY | If single-host: the rejection reason is reported rather than failing silently, and the slot is **not** reserved for a vendor application | declaration | | |
| R-10.4 | MUST | BLE T1/T0 characteristics require an encrypted link (LE Secure Connections). Just Works permitted; unencrypted streaming is not | inspection | | N/A if no BLE binding |
| R-10.5 | MUST | Loopback WebSocket binds to loopback only, rejects unconfigured `Origin`, and is never exposed on `0.0.0.0` even behind an option | inspection | | N/A if no WS binding |
| R-10.6 | MUST NOT | T2/T3 never exposed on a transport with weaker protection than T1 | inspection | | N/A if no T2/T3 |
| R-10.7 | MUST | Loss of the encrypted link ends the session rather than silently resuming onto a new one | inspection | | |

## §11 — Conformance and claims

| Req | Status | What you are asserting | Checked by | Supported | Notes |
| --- | --- | --- | --- | --- | --- |
| R-11.1 | MUST | Every MUST in §§3–10 and Appendix A is satisfied **and** the reference suite passes | suite | | attach suite output |
| R-11.2 | — | *Defines the limits of the suite.* Not a vendor obligation | — | — | — |
| R-11.3 | MUST | Your claim reads "ASE-0.1 Core conformant", names the exact firmware version tested, and ships with the descriptor and suite output. No family, roadmap, or unreleased-version claims | declaration | | firmware version: |
| R-11.4 | — | *Self-certification: no fee, no gatekeeper, no revoking authority.* Not a vendor obligation | — | — | — |
| R-11.5 | SHOULD | If you offer this feature space for cross-user use: it beats the channel-mean reduction of itself on your own data and task, by a margin whose 95% CI excludes zero — and you publish the task, subject count, and bootstrap unit | declaration | | outside the suite by construction |

## Appendix A — per-kind `quality`

| Req | Status | What you are asserting | Checked by | Supported | Notes |
| --- | --- | --- | --- | --- | --- |
| A | MUST | `quality` follows the normative definition in Appendix A for your declared `signal.kind` | declaration | | state the kind and the measurement |

## Summary

All 48 requirement identifiers in `ASE-0.1.md` appear above exactly once, plus
one row for Appendix A.

| | Count |
| --- | --- |
| **Rows you must answer** | **43** |
| — decided outright by the suite | 14 |
| — part suite, part declaration | 4 |
| — your declaration alone | 14 |
| — third-party inspection, not the suite | 11 |
| Informational rows, nothing to answer | 4 |

Fourteen green ticks are not a conformance claim. Eighteen rows rest wholly or
partly on your signature, and that is by design — a specification that could
mechanically verify a vendor's terms would be a specification that gated on the
vendor's permission, which is the problem ASE exists to remove.

## Declaration

```
Vendor:                 ______________________________
Device / model:         ______________________________
Firmware version:       ______________________________
Descriptor published at:______________________________
Suite output attached:  [ ] yes
Date:                   ______________________________
Signed (name, role):    ______________________________
```

> The signatory states that the answers above are accurate for the named
> firmware version. R-11.4 provides no authority to revoke a claim; the remedy
> for a false one is the ordinary remedy for a verifiably untrue product
> statement, and every row above is checkable by a third party.
