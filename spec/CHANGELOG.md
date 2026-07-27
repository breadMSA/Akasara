# ASE changelog

Per §13.2: errata and clarifications that do not change what a conformant device
must do may be issued at any time and are listed here. Anything that changes a
requirement increments the minor version and carries a migration note.
Requirement identifiers are never reused or renumbered.

## 0.1 — 2026-07-27 (draft, unpublished)

First draft. Not yet issued to any implementer, so the changes below are
pre-publication revisions rather than errata against a released version.

Within-draft revisions on the same day, recorded because they are the kind of
thing a later reader will want to see was caught rather than missed:

- **Added §12 (IPR) and §13 (governance).** The first draft had no licence, no
  patent position, no trademark position, and no change or succession process —
  the gap that stops a vendor's counsel before engineering reads page 1.
- **Added §9.2 ABF binary encoding.** The first draft carried T1 frames as JSON
  on every transport, including BLE. Computed: a dim-64 JSON frame is 628 bytes,
  251 kbps at 50 Hz, over the practical 1M PHY budget before overhead. ABF
  float16 at the same dim and rate is 61 kbps.
- **Corrected §10.2.** The first draft specified a baud rate for USB CDC, where
  baud is a virtual parameter that does not limit throughput. Replaced with COBS
  framing and a `max_sustained_kbps` declaration (R-4.4).
- **R-5.2 clock epoch.** Nanoseconds since the Unix epoch exceed the 2^53 range
  JSON represents exactly. Epoch is now required to be boot or session start.
- **R-5.1 / R-4.3 RTC honesty.** Devices without a real-time clock must omit
  `t_wall_ms` rather than emit an invented value.
- **R-5.7.1.** The first draft did not say *which* analysis window the self-test
  vector comes from over a 2-second input — every vendor would have chosen
  differently. Now: the last window ending at or before 2.000 s.
- **R-5.6.** Per-channel `quality` array length is `signal.channels`, not `dim`.
- **R-7.5.1 relaxed.** "Selectable" became "obtainable", explicitly satisfiable
  by a downgrade image; two concurrently resident pipelines were never the
  intent and would have been the most expensive clause in the document.
- **§1.1 added** to answer the three objections a vendor actually raises
  (liability, competitor cloning, SDK gating) instead of only asserting the
  user-side value.
- **R-8.1 added:** Core conformance is unconditional and never contingent on the
  `akasara.align.v1` licence.
- **R-11.2 added** to state which requirements the suite can decide and which
  are vendor declarations it can only record.
Second same-day revision — three open issues closed with measurements rather
than assertions (Ninapro DB5, 6 subjects, 30 ordered pairs, chance 0.062):

- **R-4.2.2 added.** Whole-electrode band rotation is exactly free (a fitted
  linear map absorbs a channel permutation); sub-electrode misalignment costs at
  most ~9%, worst at the half-way point. So comparability needs matching
  electrode count and spacing, not matching absolute orientation, and
  `angle_deg` needs half-a-spacing accuracy, not degrees.
- **R-5.2.1 justified.** A 400 ms window offset between two people costs 0.8% of
  transfer, orders of magnitude more slack than declared oscillator drift
  consumes. `time_echo` stays SHOULD, now on evidence instead of taste.
- **§11.5 added:** a provisional, non-normative feature-space floor of 3.5×
  chance. The reference task separates real feature sets (4.2–4.8× chance) from
  degenerate ones (1.7–2.1×), paired CI [+0.137, +0.168]. Two constraints fell
  out: a floor must not be written as a minimum `dim` (MAV-only 16 d beats the
  full 64 d set, CI [+0.009, +0.024]), and 8-bit quantisation is nearly free,
  which is what makes §9.2's lossy encodings defensible.
- **§9.3 export container** with per-record CRC-32 and a whole-file SHA-256,
  replacing the "no integrity check" open issue.
- **§10.5 security model** — threat table, BLE encryption required (R-10.4),
  loopback-only binding (R-10.5), tier-monotonic protection (R-10.6), session
  break on link loss (R-10.7), and an explicit statement that same-machine
  isolation is the host OS's job.
- **R-4.2.1 added:** opaque-montage devices declare a `geometry_id`, recovering
  within-model comparability. The first draft declared them incomparable even
  with another unit of the same model, which was both useless and untrue.
Third same-day revision — the remaining measurable open issues:

- **R-4.2.3 added (axial placement).** Rotation was measured; displacement along
  the limb was not, and unlike rotation it is not permutation-like. DB5 wears two
  rings at different forearm heights, which is exactly that displacement:
  same-height 0.245 vs different-height 0.229, −0.016, CI [−0.024, −0.008],
  retaining 93.4%. Small, but it does not vanish, so `axial_mm` is required per
  channel and must be treated as a real difference.
- **R-5.2.1 re-tested at the document's own window lengths.** The previous
  result used whole-repetition windows and carried a caveat that short windows
  might invert it. They do not: at both 200 ms and 100 ms windows, offsets to
  200 ms are free and only 400 ms costs (11–13%, CI excludes zero). The
  tolerance is set by the movement, not the window. Caveat replaced with the one
  case still untested — sample-by-sample pairing.
- **R-7.5.1 derivation re-sourced.** The invented "3 sessions/week" is replaced
  by Rock Health's 2025 Consumer Adoption Survey (N = 8,000): 83% of owners wear
  five or more days per week. That recomputes the window to ~56 days, shorter
  than the stated floor. The 90-day floor is kept anyway and the reason is now
  written down — a floor protects the low-adherence tail, not the median. One
  parameter (the ~20-donning enrollment target) remains unmeasured, with the
  reason it cannot be measured on public data stated.
- Numbering, scope, and BCP 14 citation fixes: §3 requirements are now labelled
  R-3.1–R-3.3 (the suite already emitted "R-3"), conformance scope in R-11.1
  covers §§3–10 and Appendix A rather than §§4–7.
