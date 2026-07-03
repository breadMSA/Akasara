# Akasara

Experiments in accessible, modality-agnostic input.

| Directory | What it is |
| --- | --- |
| `packages/inputsource/` | Zero-dependency TypeScript library: every input modality (typed, spoken, whatever comes next) enters as one `RawExpression` shape, and nothing downstream is allowed to know which modality produced it. Compiles strict; tested with `node --test`. |
| `apps/switchboard/` | Single-file web phrase board that is 100% operable by keyboard or a single switch. Ships with a built-in two-stage scan simulator (Space = the switch) so switch operability can be tested on any machine; also works with iOS/macOS Switch Control. Speech output, local-only storage, no account. |

## Why

Today's real brain-computer-interface users — implant trial patients driving
iOS through Switch Control — are switch users. Most software treats switch
scanning as an afterthought, if it works at all. These are experiments in
building for that input model first, not last.
