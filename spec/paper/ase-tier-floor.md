# Export Tiers for Body-Signal Devices

### Why a recognised-event interface cannot support cross-person, cross-vendor, or evidentiary use

**Author:** Lin, Xian-Jun (林羨鈞) — Akasara
**Version:** 1.0 — 2026-08-10
**DOI:** https://doi.org/10.5281/zenodo.21869421
**Cite as:** Lin, X.-J. (2026). *Export Tiers for Body-Signal Devices: Why a
Recognised-Event Interface Cannot Support Cross-Person, Cross-Vendor, or
Evidentiary Use.* Zenodo. https://doi.org/10.5281/zenodo.21869421
**Companion specification:** ASE-0.1, *Akasara Signal Export* — https://github.com/breadMSA/Akasara (branch `spec/ase-0.1`)
**Licence:** CC BY 4.0

**Disclosure of interest:** The author is the sole editor of ASE-0.1, the
specification whose central requirement this paper argues for, and has a
commercial interest in work built above the layer it describes. The argument is
offered to be checked, not deferred to. Where it depends on an empirical claim,
the claim is cited; where it depends on a definition, the definition is stated.

---

## Abstract

Consumer body-signal devices — surface-EMG bands, EEG headsets, eye and face
trackers, and the neural interfaces now entering consumer development — record a
continuous physiological signal and export a discrete recognised event: a
gesture, a keystroke, a command, a string of text. This paper argues that the
choice of export tier is not a quantitative privacy setting but a qualitative
boundary, and that three distinct classes of use are not degraded below that
boundary but are **structurally unavailable**: (i) processing two people's
signals in a common representation, (ii) adapting to a user or a vocabulary the
vendor did not train for, and (iii) re-analysing a recording under an
interpretation other than the vendor's own — the operation on which both
scientific replication and evidentiary challenge depend.

We define a four-tier model (T0 recognised event, T1 feature/latent vector, T2
filtered continuous stream, T3 raw samples), state the projection argument that
separates T0 from the rest, and derive three consequences. First, an event
record that does not identify the signal frames it was computed from is
unfalsifiable, and we describe a minimal mechanism (`t1_seq`) that makes it
falsifiable at negligible cost. Second, in jurisdictions applying a reliability
standard to expert evidence, a T0-only record can be neither corroborated nor
impeached, which is a problem for the party offering it and for the party
resisting it alike. Third — and contrary to a common intuition — the commercial
value of *interoperating* between vendors is an increasing function of tier: at
T0 the exported artefact is already a universal type (text or a label), so
bridging is trivial and therefore worth nothing, while the representations for
which bridging would be valuable exist only at T1 and above.

We note that the existing international work in this area (ISO/IEC TS
27571:2026; GB/T 47127—2026) standardises how a recording is *written down* and
leaves the tier floor, the export obligation, and cross-user processing terms
unaddressed. ASE-0.1 is an attempt to occupy that gap; this paper is its
argument, stated independently of the requirements text.

**Keywords:** brain-computer interface, biosignal, data portability, neural
data, interoperability, forensic evidence, standardisation

---

## 1. Introduction

A device that records a body signal must decide what to hand to software running
outside it. Current consumer practice is uniform: the raw signal stays on the
device and the interface emits recognised events. Vendors state the rationale in
privacy terms, and the rationale is real — a recognised event discloses far less
about the wearer than the signal it was computed from.

The claim of this paper is that the same choice has a second consequence which
is rarely stated, is independent of the privacy rationale, and is not a matter
of degree.

The usual mental model is that an export tier trades fidelity against privacy on
a continuous scale: a coarser export is a lossier version of the same thing. For
tiers T1 through T3 that model is correct. For the step from T1 to T0 it is
wrong, and the error matters because it makes an entire class of applications
look merely difficult when it is in fact closed.

## 2. The tier model

Every body-signal device, whatever the modality, passes internally through the
same stages:

```
 sensor  →  filtered stream  →  feature / latent vector  →  classifier  →  event
   T3            T2                      T1                                 T0
```

| Tier | What crosses the interface |
| --- | --- |
| **T0** | Discrete recognised events: gestures, keys, commands, text |
| **T1** | A fixed-dimension numeric feature or latent vector per analysis window |
| **T2** | A continuous per-channel stream after fixed, documented filtering |
| **T3** | Raw samples at ADC resolution and native rate |

The tiers are not a proprietary taxonomy; they are a description of a pipeline
that already exists inside every such device. T1 values are computed in the
normal course of operation, whether or not they are exported.

### 2.1 Text is the T0 of a language interface

Where the recogniser's output is language rather than a gesture label — a neural
or muscular interface that decodes to typed characters or to a sentence — the
exported artefact is a string. This is still T0. It is a recogniser output
projected onto a fixed vocabulary; the vocabulary happens to be a natural
language rather than a vendor's gesture set.

This case deserves separate statement because it is a *harder* case, in three
ways. It looks like full fidelity: the user receives the sentence they intended
and experiences no loss, and a regulator reading the export policy sees none.
The vocabulary is effectively unbounded, so the objection "your label set is too
small" is unavailable. And a natural language is a *public* alphabet whose
entire function is to mean the same thing across speakers — so projecting onto
it removes between-person structure more completely, not less, than a vendor's
private label set does.

## 3. The projection argument

A T0 event is not a lossy encoding of the signal. It is the image of the signal
under a projection onto the vendor's label set:

> f : S → L, where L is a finite (or lexical) set fixed at ship time.

Two consequences follow immediately, and neither is quantitative.

**Information outside the label set is not attenuated; it is absent.** Any
property of the signal that f does not vary with cannot be recovered from f(s)
at any data volume, at any sampling rate, over any observation period. Averaging
more events does not help, because the events are not noisy measurements of the
missing property — they are not measurements of it at all.

**The geometry is destroyed, not coarsened.** Operations that depend on
*distances and directions* in the signal's representation space — the
between-person structure that alignment methods exploit, the between-condition
structure that a re-analysis would test — do not survive the projection, because
L carries no metric that relates back to S.

This is what separates T0 from T1, T2 and T3. Among the latter three the
relationship really is one of fidelity: a T1 vector is a compressed, documented
summary of the T2 stream, which is a filtered version of the T3 samples. Each
retains a metric structure related to the original. T0 does not.

### 3.1 What is and is not novel here

The first consequence is an instance of the data processing inequality [12]: no
function of f(s) can carry more information about s than f(s) does, so
post-processing cannot recover what the projection discarded. Stated at that
level of generality the point is textbook, and this paper claims no novelty for
it.

Three things are added, and they are where any disagreement should be aimed.
First, the identification of *where* the discontinuity sits in a real device
pipeline — between the feature vector and the classifier output, not anywhere
among the signal tiers — which is an empirical claim about how these devices are
built, not a mathematical one. Second, the observation that the destroyed
property is specifically **metric structure**, which is what distinguishes the
T1→T0 step from ordinary lossy compression: a compressed signal supports
approximate distance queries, a label set supports none. Third, the mapping from
that structural fact onto three concrete failures — cross-person alignment,
out-of-distribution service, and adversarial re-analysis — of which the third has,
to the author's knowledge, not previously been raised in the context of consumer
biosignal export.

## 4. Three operations that close at T0

### 4.1 Cross-person processing

Aligning two people's signals into a common representation is the operation
underlying shared-response modelling and hyperalignment, and it is what any
person-to-person interface would need. It is defined over vectors: the methods
compute a mapping between two representation spaces. Run over event streams the
operation does not degrade — it does not exist, because two label sequences have
no space to map between. A recent cross-subject result on invasive recordings [6]
reports transfer of a pretrained decoder to a held-out subject via a
subject-specific projection into a shared space; the reported effect is modest
and the decoding target is a language-model embedding, so it should not be read
as establishing how much meaning the neural signal itself carries. What it does
illustrate is the shape of the operation: the projection is a map between feature
spaces, and there is no T0 analogue of it — not a weaker one, none.

### 4.2 Out-of-distribution users and out-of-vocabulary intents

A user whose signal the vendor's classifier handles poorly, or an intent the
vendor never shipped a label for, cannot be served by anyone else at T0. Not
because the third party's model would be weak, but because the third party
receives only the classifier's own verdict. The failure is invisible in the
export: a misrecognition and a correct recognition are the same object.

### 4.3 Re-analysis under a different interpretation

This is the operation that scientific replication and adversarial legal
examination have in common. Both consist of taking a record and asking whether a
different interpretation fits it better. At T0 the record *is* the
interpretation. There is nothing left to re-interpret.

## 5. Making an event falsifiable

If T0 events are exported alongside T1 frames, one cheap mechanism converts an
assertion into a checkable claim. Each event carries `t1_seq`: the sequence
number of the last exported T1 frame the recogniser consumed before emitting it.

The mechanism costs a 4-byte field. What it buys is that a recipient can
re-derive the event from the frames it names, and can detect a device that emits
events not supported by the signal it exported. Without it, a device may ship a
feature stream and, beside it, an event stream computed from something else
entirely, and no external party can tell. Where the recogniser does not run on
exported frames, the correct behaviour is to omit the field rather than attach
the nearest sequence number and imply a provenance that does not exist.

A T0-only architecture structurally cannot offer this, because there is no
exported evidence for an event to point at.

## 6. Evidentiary consequence

Data from consumer wearables has already been offered in criminal proceedings.
As reported in the sources cited here: in an Australian homicide trial the
deceased's smartwatch record was used to fix the time of the attack and to
contradict the accused's account [7]; a Fitbit heart-rate record played a
comparable role in a Californian case, and a Garmin record in a Georgia case in
2024 [8]. A recent systematic review addresses the general question of whether
such a device is a reliable witness [9]. These are cited as evidence that the
category is already in use, not as authority on any point of law.

Everything offered so far is a *proxy* measurement — heart rate standing in for
fear, movement standing in for activity. A body-signal or neural device would
offer something nearer the state itself, and the inferential chain becomes
correspondingly more consequential in both directions.

Under a reliability standard for expert evidence — *Daubert v. Merrell Dow
Pharmaceuticals*, 509 U.S. 579 (1993), in US federal practice — the tribunal
must assess the chain from the instrument reading to the proposition it is
offered to prove [10]. The author is not a lawyer, the analysis below is offered
as a structural observation rather than as legal advice, and other jurisdictions
approach expert evidence differently; what does not vary between them is that
some assessment of reliability must be possible at all. A T0-only record defeats
that assessment symmetrically:

- The **proponent** cannot show the chain, because the first link is a
  proprietary classifier whose output is the whole record.
- The **opponent** cannot attack the chain, because there is no underlying
  observation against which to test an alternative explanation.

The result is not that T0 evidence is weak. It is that its reliability is not
assessable at all, which is a worse position for a legal system than either
admitting or excluding it on the merits. A tier floor is, among other things, a
precondition for such records ever being properly contestable.

## 7. Interoperability consequence, and a correction to the obvious intuition

It is tempting to argue that a vendor-neutral device could win users by talking
to everyone: if two dominant platforms decline to interoperate, a third device
that reads both becomes the only one whose user can reach the whole population.

The argument is correct in form and, at T0, empty in substance — and the reason
is worth stating because the intuition runs the other way.

At T0 the exported artefact is text or a label. Text is *already* a universal
type. Anything can read it, everything already does, and cross-platform text
messaging is a solved problem. Bridging two T0 exports is therefore trivial —
and worth nothing, because the incompatibility it resolves does not exist. What
does exist at T0 is *platform* lock-in at the application layer, which is a
different problem with a different remedy, and one that the platform owners
themselves have historically solved when it suited them. The precedent is
Matter: begun as Project Connected Home over IP in December 2019 and released as
Matter 1.0 on 4 October 2022 under the Connectivity Standards Alliance, it was
built by the incumbent platform vendors — Apple, Google, Amazon and Samsung
among them — once interoperating at that layer stopped threatening anything they
valued [13]. The lesson is not that interoperability never arrives; it is that
it arrives, from the incumbents, precisely at the layers where it is cheap to
them, and therefore that a third party should not plan to be paid for supplying
it there.

The exchanges for which a bridge would be genuinely valuable — a representation
of intent or state richer than the words it would be flattened into, shared
between two people or two devices — exist only at T1 and above. Which yields a
compact statement:

> **The value of interoperating between vendors is an increasing function of the
> export tier. At T0 it is trivial and worthless; the case where it is worth
> money is exactly the case where it is not permitted.**

The corollary is that a tier floor is not only a research or evidentiary
question. It determines whether a market above the platform layer can contain
anything but tenants.

## 8. Cost of conformance

The tier floor is cheap in a way that distinguishes it from most standardisation
proposals: it requires no hardware change. T1 values already exist inside the
pipeline; exporting them adds an output path, sequence numbering, session
identifiers and a quality field, all bookkeeping.

Two obligations cost real engineering. A **self-test path**, in which the device
runs its exact production T1 transform over a fixed synthetic input and publishes
the result, is what makes the declared feature space verifiable by a third party
rather than merely asserted; the reference specification budgets days for it.
And keeping the **previous feature space obtainable** after a change protects
downstream users from silent redefinition; it is satisfiable with a downgrade
image rather than two live pipelines.

Three vendor objections are worth answering directly rather than dismissing.
*Privacy liability*: feature frames are more disclosing than events, which is
why the export must be user-directed, locally reachable, and revocable rather
than open. *Competitor cloning*: T1 features do help a competitor train a
recogniser, and the honest bound is that this is per-subject rather than
population-scale, that labels never leave, so the recipient still pays for ground
truth, and that a non-adaptive export mode lets a vendor keep personalisation on
the device. *SDK gating*: an export conditioned on an approved-developer
programme is not an export, because the user's choice of software is precisely
what is being conditioned.

## 9. Relation to existing standards work

ISO/IEC JTC 1/SC 43 (Brain-computer interfaces, formed March 2022) published
**ISO/IEC TS 27571:2026**, *BCI data format for non-invasive brain information
collection*, in April 2026 [1][2]: basic data elements, technology-specific
metadata, a modular structure and naming conventions for EEG, MEG, fNIRS and
fMRI. (The description here is taken from the published scope; the author has
not obtained the full text, which is behind a paywall, and any characterisation
of its detailed provisions should be checked against it.) China's SAC/TC28/SC43
published **GB/T 47127—2026** (multimodal data format) on the same layer [3].

The legal environment runs on a third track again. European data-access law
gives a user the right to obtain data generated by a connected product and to
direct it to a third party [4], which secures a *pipe* but says nothing about
what travels through it — a right to receive whatever the vendor chooses to emit
is satisfied by a T0 export. Conversely, the AI Act's prohibition on inferring
emotions in workplaces and educational institutions [5] restricts who may
lawfully receive an inference, without touching the tier question either. Access
law, prohibition law and format standards leave the same gap between them: none
of them states a fidelity.

These standardise **how a recording is written down**. They do not oblige a
device to provide an export path, do not state a fidelity at which it must do
so, and do not address whether two consenting people may have their signals
processed together. The layers stack rather than conflict: a format standard
says how to write the file; a tier floor says who is entitled to obtain one, and
containing what.

The claim "nobody is standardising this" would be false. The narrower claim is
the accurate one: **the rights layer is unclaimed.**

## 10. Limitations

Three, stated so that they are not presented as discoveries by a reader.

**The tier model is a description of current device architectures, not a
theorem.** A device that exposed a learned representation which was neither a
documented feature space nor a label set would not sit cleanly on it. Nothing in
the argument breaks, but the mapping would need restating.

**The evidentiary argument is structural and untested.** No decided case is known
to the author in which a body-signal or neural device record was admitted or
excluded on the reasoning given in §6; the cited cases all concern proxy
measurements such as heart rate. The argument predicts a difficulty; it does not
report one.

**The interoperability argument in §7 depends on an unfalsified assumption** —
that consumer read hardware capable of producing representations richer than
language will exist. If it does not, the tier floor retains its research and
evidentiary value and loses its commercial one. That assumption is stated here
rather than buried, because it is the load-bearing one.

## 11. Conclusion

The export tier of a body-signal device is usually presented as a privacy
setting. It is also, and independently, the decision that determines whether
anyone other than the vendor can ever compute anything on the signal — including
the wearer, a researcher attempting replication, a court assessing reliability,
and a second person the wearer wishes to communicate with.

T1 is the lowest tier at which those operations exist at all. It is available at
the cost of an output path and a terms clause. The specification accompanying
this paper [11] states the requirement in testable form, with a machine-checkable
schema, a reference conformance suite and a royalty-free patent commitment; this
paper is offered so that the argument can be cited, examined and disagreed with
independently of that document.

---

## References

[1] ISO/IEC TS 27571:2026, *Information technology — Brain-computer interfaces —
Data format for noninvasive brain information collection*. Edition 1.0,
2026-04. ISO/IEC JTC 1/SC 43. https://webstore.iec.ch/en/publication/85035

[2] ISO/IEC JTC 1/SC 43, Brain-computer Interfaces.
https://jtc1info.org/technology/subcommittees/brain-computer-interfaces/

[3] GB/T 47127—2026, 腦機接口 多模態數據格式 (multimodal data format),
SAC/TC28/SC43, published 2026-01-28, in force 2026-08-01.

[4] Regulation (EU) 2022/868 and Regulation (EU) 2023/2854 (Data Act), on
user-directed access to data generated by connected products.

[5] Regulation (EU) 2024/1689 (AI Act), Art. 5(1)(f), prohibiting inference of
emotions in the workplace and in educational institutions, applicable from
2025-02-02.

[6] Heo, Wisniewska, Lee & Lee, *Cross-Subject Semantic Decoding with
Shared-Space Alignment*, arXiv:2607.19394.

[7] *Apple Watch heart rate data used as evidence in Australian murder trial*.
https://www.digitaltrends.com/wearables/apple-watch-health-data-murder-trial/

[8] *The Rise of Smartwatch Data in Criminal Cases*, Harvard Undergraduate Law
Review. https://hulr.org/law-in-the-news/the-rise-of-smartwatch-data-in-criminal-cases

[9] *Is my smartwatch a valid witness? A systematic review and meta-analysis*,
Forensic Science International, article PII S0379073826000885. Publisher page:
https://www.sciencedirect.com/science/article/pii/S0379073826000885 (cited from
the publisher's listing; the author was unable to obtain the full text)

[10] *The Admissibility of Data Collected from Wearable Devices*, Stetson
Journal of Advocacy and the Law.
https://www2.stetson.edu/advocacy-journal/the-admissibility-of-data-collected-from-wearable-devices/

[11] ASE-0.1, *Akasara Signal Export*. Specification text CC BY 4.0, reference
code Apache-2.0. https://github.com/breadMSA/Akasara/tree/spec/ase-0.1/spec

[12] T. M. Cover and J. A. Thomas, *Elements of Information Theory*, 2nd ed.,
Wiley, 2006 — the data processing inequality, §2.8.

[13] Connectivity Standards Alliance, *Matter*. Announced as Project Connected
Home over IP, December 2019; Matter 1.0 released 4 October 2022.
https://csa-iot.org/all-solutions/matter/
