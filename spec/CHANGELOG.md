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
Fourth same-day revision — **a withdrawal**:

- **§11.5's absolute floor of "≥ 3.5× chance" is withdrawn**, one revision after
  being proposed, because replicating on Hyser HD-sEMG (256-ch grid, 3 subjects,
  6 pairs) broke it: Hyser's *best* feature set reaches 2.3× chance, so the
  threshold would have failed a perfectly good feature space. The ranking of
  individual features does not transfer either — MAV-only is the best set on DB5
  and near-chance on Hyser. What replicated is **relative**: a real feature space
  beats its own channel-mean reduction with a CI excluding zero on both datasets
  (+0.153 and +0.051), and 8-bit quantisation is free on both. The criterion is
  restated in that form. Both legs are still sEMG, so "second modality" remains
  the open 1.0 item, now better bounded: look for a relative margin, not a score.
  *(The feature-ranking half of this entry was retracted the same day — see the
  fifth revision below. The withdrawal of the absolute floor stands.)*
- Enrollment data volume saturates around ~100 single-session trials (Hyser),
  which bounds the data-volume half of R-7.5.1's parameter. The
  donning-diversity half still has no dataset. *("No dataset" was corrected in
  the sixth revision below — CEMHSEY exists. It is still unrun.)*
- Numbering, scope, and BCP 14 citation fixes: §3 requirements are now labelled
  R-3.1–R-3.3 (the suite already emitted "R-3"), conformance scope in R-11.1
  covers §§3–10 and Appendix A rather than §§4–7.

Fifth same-day revision — **a retraction inside the previous withdrawal**:

- **"The ranking of features does not transfer" is retracted.** The fourth
  revision reported MAV-only as best on DB5 and near chance (1.1×) on Hyser and
  wrote that into §11.5. Auditing the Hyser leg against the dataset's own WFDB
  header — which the loader had never read — showed every channel carries its
  own `baseline`, so MAV and RMS were being measured on a per-electrode DC
  pedestal while WL and VAR are DC-immune by construction. That is the reported
  ranking, manufactured by the loader. With the pedestal removed MAV goes 1.1× →
  1.6× (positive on 27 of 30 pairs) while WL and VAR are bit-identical, and the
  feature sets collapse into one 1.5–2.0× band with no inversion. §11.5 now
  states the retraction rather than deleting the claim.
- **Both §11.5 legs re-measured on one footing.** DB5 carries the same pedestal,
  three times smaller, and is unmoved by the correction (full +0.0015), so its
  published numbers change only in the third decimal (full 0.285 → 0.288, full
  vs channel-mean +0.153 → +0.156). The Hyser leg is also widened from 3
  subjects / 6 pairs to 6 / 30 — the same pair count as the DB5 leg.
- **The withdrawal of the absolute floor survives the audit**, which is why it is
  not reversed: Hyser's corrected best is 2.2×, still far below 3.5×. Also
  checked and rejected as an explanation of the gap: the two legs had used
  different retrieval sizes (16-way vs 10-way) and a multiple of chance is not
  comparable across *N* — at DB5's exact settings Hyser reaches 2.4×.
- **Experiment seeds made reproducible.** The split seeds were derived from
  Python's `hash()`, which is salted per process, so the §11.5 numbers were not
  reproducible between runs. Now `crc32`.

Sixth same-day revision — **§11.5 becomes normative, at SHOULD**:

- **A third leg closes §14's largest 1.0 item.** The criterion had two sEMG legs
  and could still have been a fact about muscle. It now has an EEG leg:
  ds007822 Prisoner's-Dilemma hyperscanning, 11 triads × 3 players, 19-ch 10-20,
  round-retrieval between two players who lived the same game round, with players
  from different triads as a real null rather than a shuffle. The full 95-d
  band-power space beats its own channel-mean reduction by **+0.040, CI [+0.031,
  +0.049]**, on 55 of 66 pairs, and survives a drift control that forces
  candidate rounds ≥3 and ≥5 apart (+0.043, +0.076). The criterion also **fails**
  things — alpha-only and theta-only spaces do not clear it in any setting — so
  it separates rather than decorates. 8-bit quantisation is free here too
  (−0.0002, CI [−0.0008, +0.0004]): three datasets now support §9.2.
- **New R-11.5, at SHOULD.** A T1 feature space offered for cross-user use SHOULD
  beat its own channel-mean reduction with a CI excluding zero, and a vendor
  quoting such a margin MUST also publish the task, the independent-subject
  count, and the unit the interval was resampled over. It is not a MUST because
  the task is vendor-chosen and because the margin can be earned from generic
  transferable structure: most of the EEG margin is still there between players
  who never shared a round (cross-triad 0.131 vs 0.098), and the genuinely
  shared-state part is only +0.020, CI [+0.006, +0.033]. That limit is now
  written into §11.5 and is the new form of the open item — it needs a task a
  vendor cannot overfit, not another modality.
- **Third data point against an absolute floor.** The best EEG space reaches
  1.8× chance, against 4.6× on DB5 and 2.0× on Hyser. The withdrawal of "≥ 3.5×"
  is not a two-dataset accident.
- **Schema and suite follow the requirement.** `t1.cross_user_margin` is added to
  the capability schema with `margin`, `ci_low`, `ci_high`, `task`, `subjects`
  and `bootstrap_unit` all required once the object is present; `check.mjs` fails
  R-11.5 on a margin quoted without them, warns when the CI does not exclude zero
  or when the resampling unit is not `subject`, and a new `bad-margin` vector
  covers the failure. The margin itself is measured on data the suite never sees,
  which R-11.2 now says explicitly.

- **R-7.5.1's "~20 donning sessions" is still unmeasured, and now has a named
  candidate.** CEMHSEY (11 consecutive days, grids re-applied daily, Zenodo
  10.5281/zenodo.14224328 / .14272463) could bound the donning-diversity half.
  Eleven days is not twenty, so it would make the parameter partially bounded
  rather than measured. Recorded in §11.5 as the next thing to run; the spec text
  continues to say the number is asserted.
