# Akasara

Experiments in accessible, modality-agnostic input.

| Directory | What it is |
| --- | --- |
| `packages/inputsource/` | Zero-dependency TypeScript library: every input modality (typed, spoken, whatever comes next) enters as one `RawExpression` shape, and nothing downstream is allowed to know which modality produced it. Compiles strict; tested with `node --test`. |
| `spec/` | **ASE — Akasara Signal Export.** Open specification for body-signal wearables (EMG, EEG, and whatever comes next): export feature-level frames over a local interface in a version-pinned feature space, with no term forbidding a user from processing their own data alongside another consenting person's. Ships a zero-dependency conformance suite and test vectors. |
| `apps/gate/` | **Reference client for the spec, and the consent gate in front of it.** Single-file web app: the phone's IMU stands in for a body-signal wearable, producing real ASE T1 frames in a pinned feature space with a working R-5.7 self-test, and nothing leaves the device except under a grant that names a recipient, a purpose, and an expiry. Its exports pass `spec/conformance/check.mjs`; a zero-dependency Node bridge supplies the §10.3 loopback transport a browser cannot bind itself. |
| `apps/brainflow/` | **Third implementation, and the adoption route.** An ASE producer backed by [BrainFlow](https://brainflow.org), which is one acquisition API in front of 64 boards — OpenBCI, Muse, Neurosity Crown, g.tec Unicorn, OYMotion gForce sEMG, Ant Neuro, EmotiBit. A vendor on that list becomes an ASE producer by running one file, not by writing firmware. Emits the *same* pinned feature spaces as `apps/replay`, so a live board and a Ninapro capture are directly comparable. Runs with no hardware on BrainFlow's synthetic and playback boards; 12 tests. |
| `apps/switchboard/` | Single-file web phrase board that is 100% operable by keyboard or a single switch. Ships with a built-in two-stage scan simulator (Space = the switch) so switch operability can be tested on any machine; also works with iOS/macOS Switch Control. Speech output, local-only storage, no account. |

## Licensing

Code in this repository is **Apache-2.0** (`LICENSE`), which carries an express
patent grant — a vendor's engineer can copy from `apps/gate/` or the conformance
suite without their lawyer having to negotiate first. Two exceptions:

- **Specification text** in `spec/` is under `spec/LICENSE`; the code and test
  vectors that ship with it are Apache-2.0 under `spec/LICENSE-CODE`.
- **`packages/inputsource/`** declares MIT in its own `package.json` and stays
  MIT.

## Why

Today's real brain-computer-interface users — implant trial patients driving
iOS through Switch Control — are switch users. Most software treats switch
scanning as an afterthought, if it works at all. These are experiments in
building for that input model first, not last.
