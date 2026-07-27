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
- Numbering, scope, and BCP 14 citation fixes: §3 requirements are now labelled
  R-3.1–R-3.3 (the suite already emitted "R-3"), conformance scope in R-11.1
  covers §§3–10 and Appendix A rather than §§4–7.
