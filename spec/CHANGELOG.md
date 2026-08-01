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

Fourth revision, 2026-07-29 — the first defect found by an implementation that
did not write the spec:

- **`check.mjs` R-5.2 was capture-wide, not per session.** R-4.3 permits the
  monotonic epoch to be **session start**, so a capture holding several sessions
  legitimately restarts `t_mono_ns` at each one. The suite compared every frame
  against the previous frame regardless of session, and therefore failed a
  conformant multi-session export. Monotonicity is now checked within each
  `session_id`; a clock going backwards inside one session still fails, and both
  directions are locked by new vectors (`good-sessions.*`,
  `bad-clock-backwards.frames.jsonl`). No requirement changed — the suite was
  wrong about the requirement.

  Found by `apps/replay`, a second producer written in a second language against
  the spec text, whose DB5 captures carry one session per exercise file. This is
  the specific thing a single-implementation specification cannot find out about
  itself.

Fifth revision, 2026-07-29 — the second and third things a second implementation
found, and one negative result:

- **R-9.4 added (fixed-point rounding).** §9.2's two fixed-point quality fields
  did not say how to round. The reference codec in JavaScript uses
  `Math.round` (half away from zero); a Python implementation written from the
  layout table alone uses the language default (half to even). On a quality of
  exactly 0.7 the product is 178.5 and the two produce **different bytes** —
  178 against 179 — for the same frame. The difference is below the field's own
  resolution and cannot change any decision, but byte equality is the first
  thing two implementers compare, and leaving it undefined manufactured a bug
  for them to find. Now stated: `floor(v × max + 0.5)`. Both reference codecs
  are pinned to it by a test that encodes on one side and decodes on the other.
- **A second modality is exercised end to end.** `apps/replay` now also produces
  from 19-channel scalp EEG at 300 Hz: the `ase.eeg.1020.v1` montage system
  rather than limb geometry, log band power rather than time-domain features,
  and its own pinned feature space. CONFORMANT, no warnings. "Signal-agnostic"
  was previously a design claim tested on one signal; it has now been produced
  and consumed on three.
- **A negative worth recording against §11.5.** Measured on that EEG capture, the
  cross-user margin within a triad (people who actually played the same rounds)
  is **+0.010, CI [+0.005, +0.015]** — and between triads, people who never
  shared a round, it is **+0.010, CI [+0.007, +0.012]**. Identical. On this task
  and this feature space, the entire margin is generic transferable structure and
  none of it is evidence about the pair. §11.5 already warns that a margin can be
  earned this way; this is the extreme case of the warning coming true, and it is
  why the EEG captures deliberately publish **no** `cross_user_margin` at all.
  The DB5 sEMG margin is unaffected: +0.162, CI [+0.153, +0.172], collapsing to
  −0.004 under a permutation control.

Sixth revision, 2026-07-30 — the fourth thing a second implementation found, and
the EEG negative bounded:

- **R-5.4.1 added (vector layout).** R-5.4 pins *which* transform produced
  `values[]`. It does not pin the order of the answer. `apps/replay` and
  `apps/gate` compute the same two time-domain features and lay them out
  differently — feature-major and channel-major — and both were correct, both
  conformant, and mutually unusable. A consumer collapsing the wrong axis
  averages RMS together with waveform length and reports the result as the
  channel-mean baseline that §11.5 asks a vendor to beat: wrong, silent, and not
  caught by anything in the suite. `t1.layout` is now required, one of
  `feature-major`, `channel-major`, `opaque`. `opaque` is a real answer and costs
  the device the ability to state an R-11.5 margin, since the baseline that
  margin is measured against does not exist for a vector that does not factor.
  This is the first defect found not by a second implementation reading the spec,
  but by two of them being pointed at each other.
- **The EEG negative is bounded rather than restated.** Both permutation controls
  are now reported (1.0x chance, margin −0.004 and +0.001), which is what shows
  the 1.4–1.6x retrieval is a real transfer and not noise, and the sharper
  question is asked directly: does sharing the rounds raise retrieval at all,
  before any reduction? **+0.008, CI [−0.001, +0.017], p = 0.099, 12/18 positive.**
  A near-miss, reported as one. The negative about the *margin* stands. What it
  is not is a negative about EEG: the cue is the round index, and forty rounds of
  one game are forty repetitions of one state rather than forty distinct ones, so
  the task has a ceiling near its floor and could not have shown a pair effect
  where one existed.

Seventh revision, 2026-07-30 — the tiers either side of T1 were described but
never implemented, and implementing them found the fifth defect:

- **R-9.5 added (T0 event payload).** `type = 0x02` was allocated in §9.2's
  header table and given a BLE characteristic UUID in §10.1, while **its payload
  was defined nowhere in the document.** R-3.2 could therefore be satisfied and
  R-9.2 obeyed — a receiver could skip the message by its transport length
  without desynchronising — by two vendors whose event streams were mutually
  unreadable. This is R-5.4.1 one tier down, and it was found the same way: by
  implementing the tier instead of describing it. The payload is now a fixed 16
  bytes after the standard header, with `dim` 0 and `venc` `0x00`. The two
  reference codecs agree byte-for-byte on it, which is the check that says the
  table is implementable from the text alone.
- **R-3.2.1 added (T0 event object).** Fields, an `event_space` identifier pinned
  the way R-5.4 pins `feature_space`, a code registry in the descriptor rather
  than a label per event, a T0 `seq` counter that is **not** shared with the T1
  one, and the rule that a recogniser with no posterior **omits** `confidence`
  rather than emitting 1.0.
- **R-3.2.2 added (an event MUST name its evidence).** R-3.2 as written was
  satisfiable by a T1 stream and, beside it, an event stream with no stated
  relationship to it — two feeds a consumer has to take on faith line up. Where
  the recogniser runs on the exported feature space, every event now carries
  `t1_seq`: the frame it decided on. That one integer is what makes a T0 event
  **falsifiable** — a host can hold the vector and check the decision against it
  — and the suite verifies the citation resolves to a frame present in the
  capture and ending no later than the event. Where the recogniser does not run on
  exported frames, the field must be **absent** rather than approximated.
- **R-3.3.1 added (T2/T3 must be self-describing).** "Raw" and "filtered" are not
  descriptions. Every public dataset the reference implementations read had to be
  told out of band whether its numbers were microvolts or millivolts and whether
  a notch had already been applied, and getting either wrong changes an amplitude
  feature by three orders of magnitude without failing anything. A declared badge
  now costs a unit with its prefix, a layout, and — for T2 — the ordered list of
  stages actually applied; T3 additionally costs `adc_bits` and `lsb_per_unit`.
  The clause bites immediately and correctly: of the three producers, only the
  Ninapro one can declare `ase.t3`, because the PD-EEG recording's unit is wrong
  by six orders of magnitude and BrainFlow exposes no ADC scale at all. A badge
  refused for a reason in the data is the clause working.
- **§0.1 and R-0.1 added (ISO/IEC TS 27571:2026).** A real international
  committee exists in this field — ISO/IEC JTC 1/SC 43, formed March 2022,
  secretariat SAC — and published a non-invasive BCI data format TS in April
  2026. The earlier draft's implicit claim that nobody was standardising here was
  never verified and is false. The accurate statement is narrower and is now in
  the document: the **rights layer** is unclaimed. TS 27571 is the sibling of §5,
  not a competitor to §7, and where the two name the same element differently that
  is a defect in this document.

Requirement count: 48 -> 53.

Eighth revision, 2026-07-31 — a third dataset, and the first defect found by
neither a reader nor a second implementation but by an acquisition path the
document had not imagined:

- **R-5.5.1 added (frozen adaptation).** R-5.5 required a device applying
  per-user adaptation to declare it *and to offer a non-adaptive mode*. That
  assumed the adaptation was the device's own and therefore the device's to
  switch off. THINGS-EEG2 ships samples already whitened per participant, and
  the un-whitened stream is not distributed, so its ASE producer's exported T1
  is per-user adaptive with no switch to offer anywhere. The clause left exactly
  two descriptors, and both were wrong: declaring `adaptive: false` — because
  the whitening was somebody else's decision — **passed the suite and was a
  lie**, and declaring the truth **failed R-5.5 for a reason no vendor could
  fix**. A clause that passes evasion and fails honesty is backwards. Where the
  adaptation was fitted upstream and is frozen, the descriptor now declares
  `adapt_scope: "frozen"`, `non_adaptive_mode: false`, and `adapt_fitted_on`,
  and `adapt_state` MUST NOT move within a session — which the suite checks.
  This is not an exotic case: every SDK that exports features computed after an
  enrollment calibration sits in it, and under R-5.5 alone all of them would
  have declared `false`.
- **The EEG negative is corrected, and the correction is the sharper result.**
  The seventh revision recorded that the ds007822 capture publishes no
  `cross_user_margin`, and blamed the *task*: forty rounds of one game are forty
  repetitions of one state. That was right and incomplete. On THINGS-EEG2 the
  task ceiling is gone — 10 people, the same **200** images, 80 repetitions
  each, 100-way retrieval — and the same feature space still earns nothing:
  **band power, margin +0.000, CI [−0.001, +0.002], 6/10 subjects positive.**
  Exporting the evoked window itself instead, over the same people, cues,
  splits and estimator: **+0.040, CI [+0.036, +0.044], 10/10 positive**, full
  space 6.9x chance against the reduction's 2.9x, and both collapse to 1.0x
  under the permutation control. So EEG *does* carry a cross-person margin. Part
  of what the earlier negative measured was the transform, not the task and not
  the modality — and §11.5's badge cannot see that difference, because it asks
  whether a space beats its own degenerate reduction and never whether the space
  was worth choosing. §11.5 is unchanged; that limit is now stated in it rather
  than left to be discovered — together with the two conditions on the evoked
  figure: it keeps every fourth sample rather than computing anything, and the
  recording is epoched, so +0.040 is an upper bound obtained under stimulus
  alignment a continuously streaming device does not have.
- **A control, because the new margin is earned on adapted data.** Whitening
  removes the common-mode covariance a channel-mean baseline lives on, so a
  frozen per-user whitening could in principle manufacture an R-11.5 margin
  rather than reveal one. Measured where both versions exist — Ninapro DB5, as
  released and after the same per-subject whitening — it does the opposite:
  the margin falls from **+0.162 [+0.153, +0.172] to +0.116 [+0.102, +0.130]**,
  a paired change of **−0.046, CI [−0.055, −0.038], 0/6 subjects up**. The
  THINGS-EEG2 margin is if anything understated by its preprocessing. This is a
  different signal and a full-covariance whitening rather than MVNN's
  noise-covariance one, so it bounds the direction, not the magnitude.

Requirement count: 53 -> 54.

### Ninth revision — 2026-08-01: the donning curve, and two ways an R-11.5 margin could drift

- **R-7.5.1's "~20 donning sessions" moves from asserted to bounded.** It had
  been extrapolated from offline fitting behaviour; no dataset on hand could
  locate where a re-enrollment curve saturates, because the cross-day EMG sets
  used elsewhere here carry two sessions per subject. CEMHSEY carries eleven
  consecutive days per subject with the electrode grids re-applied each morning.
  All six GESTURE subjects, 11-way gesture recognition on a held-out day, chance
  0.091: **0.440 at one donning, 0.539 at four, 0.585 at ten**, with 90% of the
  ten-donning accuracy reached by four donnings, 95% by six, 99% by nine. The
  curve flattens inside the range the dataset carries — the tenth donning is
  worth +0.004, CI [-0.005, +0.011] — and bounding every further donning by that
  last step, all ten between 10 and 20 could add at most +0.036. **~20 is neither bounded
  from below by this nor contradicted; the substantive claim it stands for is
  what got measured.** The 90-day floor is unchanged and is now more
  conservative, not less.
- **The confound was controlled rather than noted.** One trial per day makes
  *k* days also *k* repetitions — the half already bounded on Hyser. CEMHSEY's
  five trials per day give a single-donning arm at matched row count and matched
  held-out test days, and because that arm always enrolls on day 1 it also sits
  farther from the test day, so the *k* = 1 gap (one donning and one trial on
  both sides) is differenced out. What remains is donning diversity alone:
  **+0.039 at two sessions, +0.052 at three, +0.064 at four, CI [+0.040,
  +0.092], positive on 6 of 6 subjects.** Roughly two thirds of what four
  enrollment sessions buy is their being separate donnings and one third is
  repetition; one subject's single-donning arm is flat (0.329 -> 0.329) and
  another's declines (0.295 -> 0.269). This
  also retires the open item that said a second donning's effect was unresolved:
  Hyser's −0.015, CI [−0.039, +0.011] was a power problem, not a null.
- **An error caught before it reached the document, recorded because the lesson
  is cheap.** The first version of this analysis used the per-feature
  standardisation this repository uses elsewhere and reported one donning at
  0.230 — barely above chance — and a total gain of +0.519. That is a degenerate
  estimator, not a finding: 1280 free parameters fitted to 11 enrollment rows.
  Under three non-degenerate normalisations the gain is +0.099 to +0.145 and the
  curve is far flatter. Every headline above is now published with its
  sensitivity to that choice.
- **R-11.5.1 and R-11.5.2 added**, from what the same dataset showed about the
  criterion rather than about any feature space. The same 1280-d space against
  its own channel-mean reduction, identical samples, splits and pipeline, reports
  a margin of **+0.071 at one donning and +0.152 at ten** — the degenerate twin
  saturates at once while the real space keeps improving, so two vendors quoting
  either number can hold the same device. And holding the enrollment fixed while
  changing only the normalisation moves the one-donning margin from **+0.419 to
  -0.095**: a per-feature standard deviation is one free parameter per dimension,
  so any fitted step whose parameter count scales with `dim` penalises the richer
  space at small enrollment — the floor-by-`dim` R-11.5 already refuses, arriving
  through the back door with its sign reversed. R-11.5.1 requires the enrollment
  behind a published margin to be stated in donning sessions as well as samples;
  R-11.5.2 requires the frames-to-score transform to be stated and, where it
  contains such a step, the margin to be reported under a pipeline without one.
  Identical pipelines in both arms is necessary and not sufficient — the inverted
  row had them.
- **Not a fourth cross-user leg, and labelled as such.** CEMHSEY's transfer axis
  is within-user across days, not cross-user, so none of its margins are
  comparable with the DB5 / Hyser / EEG legs. What it isolates is the
  measurement's sensitivity to things R-11.5 did not constrain.
- **Loader note.** CEMHSEY ships raw `.mat` with no label files; labels come from
  its published fixed cue grid (11 gestures, 5 s rest then 10 s hold / 5 s rest).
  The grid was verified against the recordings before being trusted — on one
  file each of the eleven hold windows carries 1.3-4.6x the rectified amplitude
  of the gap beside it, and across all 66 the grid's best-fit time offset is
  0.0-0.8 s, i.e. reaction time and well inside the 1.5 s trimmed from each hold
  — because a fixed-order protocol turns a labelling error into a systematic one
  rather than noise.

Requirement count: 54 -> 56.

## 0.1 — 2026-08-01 (draft, unpublished) — §11.5 third knob, R-11.5.3

- **The task moves the margin, and it moves it across zero.** THINGS-EEG2, 10
  subjects, cross-user, space and pipeline held fixed while only the task
  definition varies. The vector `apps/replay` exports ranges **−0.0169 to
  +0.0126** and changes sign; the evoked-window space ranges +0.0005 to +0.1452.
  Three sub-knobs: trial depth (how many repetitions an exported frame averages —
  alone enough to move the exported vector from failing to clearing), decision
  cardinality (2-way through 100-way), and cue-set selection.
- **The exploitable direction is the hard task, not the easy one.** On the
  exported vector the 2-way task *fails* (−0.0169, 1/10 subjects positive) and
  the 100-way task passes. The channel-mean twin retains the coarse global
  component, which wins easy discriminations; the richer space only earns its
  keep where fine separation is required.
- **Cue selection is a magnitude knob, not a sign knob.** Cues selected on a
  donor half of the subjects and scored on the held-out half — generalising, not
  circular — roughly double the evoked margin (+0.0842 against +0.0413), and on
  the exported vector do not work at all: both selected sets fall below two
  random draws.
- **R-11.5.3** requires a published task to state its decision cardinality, its
  trial depth, and how the cue set was chosen; cardinality and depth SHOULD be
  the ones the product operates at.
- **R-11.5 stays SHOULD permanently, and §11.5 now says why.** Knobs 1 and 2
  were closed by disclosure. The task cannot be — every row in the new table is
  disclosable and honest — and it cannot be fixed by specification without ASE
  naming a transfer task and thereby naming a signal.
- **Scorer defect caught before it reached this document.** The first
  cardinality run reported a per-distractor win rate, which is identical for
  every *k*; the tell was 2-way, 5-way and 20-way returning the same number. A
  retrieval is a win only against *every* distractor. Nothing from that run
  survived into the spec.

Requirement count: 56 -> 57.
