"""Recorded datasets, presented as ASE-0.1 signal sources.

A source answers exactly what a descriptor needs: what the signal is, how it was
worn, and where the session boundaries are. It does not know about frames,
tiers, windows or transports — that is `replay.py`'s job, and keeping the seam
there is what lets a second modality be added without touching the producer.

Nothing here rewrites the recording. Samples are scaled to normalised full
scale (ASE-0.1 §5.7: +-1.0 is the acquisition system's own full-scale range)
and otherwise passed through, because a producer that filters or re-references
on the way out is exporting its own opinion rather than the device's T1.
"""

import csv
import glob
import os

import numpy as np
import scipy.io as sio


class Session:
    """One contiguous recording: (T, C) normalised samples plus per-sample cue
    labels where the protocol has them (0 = rest / no cue)."""

    def __init__(self, session_id, samples, labels=None, label_names=None):
        self.session_id = session_id
        self.samples = samples
        self.labels = labels
        self.label_names = label_names or {}


class Db5Source:
    """Ninapro DB5 — 10 intact subjects, two Myo armbands, 16 sEMG channels.

    Montage, from the DB5 acquisition protocol: the first armband sits closest
    to the elbow with its first electrode on the radio-humeral joint; the second
    sits immediately distal, rotated 22.5 degrees. Eight equidistant electrodes
    per band, so 45 degrees apart within a band. Every subject's forearm
    circumference is recorded, which is what makes the electrode SPACING
    comparable across people and not merely the electrode count -- the
    distinction the spec's R-4.2.2 rests on.

    The one number here that is not measured is the axial separation of the two
    bands: DB5 records that band 2 is "just below" band 1 and nothing more. The
    nominal width of a Myo armband is used, and the descriptor says so, because
    R-4.2.3 exists precisely so a consumer can see that a placement claim is
    nominal rather than measured.
    """

    kind = "semg"
    sample_rate_hz = 200.0
    channels = 16
    full_scale = 128.0                 # Myo streams signed 8-bit
    mains_hz = 50.0                    # recorded in Italy
    MYO_WIDTH_MM = 40                  # nominal; see class docstring

    # R-3.3.1 — what the raw numbers ARE.
    #
    # The Myo's raw sEMG is signed 8-bit and Thalmic never published a microvolt
    # scale for it, so `count` with lsb_per_unit 1 is the only true answer: these
    # are uncalibrated ADC counts and any microvolt figure would be invented. The
    # clause makes that visible instead of letting a plausible "uV" slide through.
    t3 = {
        "adc_bits": 8,
        "unit": "count",
        "lsb_per_unit": 1,
        "akasara.note": "Myo raw sEMG; the vendor publishes no uV calibration, "
                        "so no physical unit is claimed",
    }
    # T2 is this producer's own documented chain, not the Myo's internal one
    # (which is undisclosed). 95 Hz rather than the usual 450 Hz upper corner
    # because Nyquist at 200 Hz is 100 Hz — a chain that cannot exist at this
    # sample rate must not be declared at it.
    t2_filters = [
        {"kind": "highpass", "hz": 20, "order": 4},
        {"kind": "notch", "hz": 50, "q": 30},
        {"kind": "lowpass", "hz": 95, "order": 4},
    ]
    # `count` is a T3-only answer (R-3.3.1): a filtered stream is no longer an
    # integer count of anything, and with no uV calibration to convert to, "a.u."
    # is what is left. The vocabulary having no `count` for T2 is what forces
    # this to be said rather than carried over from the line above.
    t2_unit = "a.u."

    EX_COUNTS = {1: 12, 2: 17, 3: 23}
    EX_OFFSET = {1: 0, 2: 12, 3: 29}

    def __init__(self, root, subject):
        self.root = root
        self.subject = subject
        self.subdir = os.path.join(root, subject)
        if not os.path.isdir(self.subdir):
            raise FileNotFoundError(self.subdir)
        self._meta = None

    # ------------------------------------------------------------------ meta
    def _load(self, exercise):
        sn = os.path.basename(self.subdir).lstrip("s")
        path = os.path.join(self.subdir, f"S{sn}_E{exercise}_A1.mat")
        return sio.loadmat(path) if os.path.exists(path) else None

    @property
    def meta(self):
        if self._meta is None:
            for e in (1, 2, 3):
                m = self._load(e)
                if m is not None:
                    self._meta = {
                        "circumference_mm": float(np.asarray(m["circumference"]).ravel()[0]) * 10.0,
                        "laterality": str(np.asarray(m["laterality"]).ravel()[0]),
                        "sensor": str(np.asarray(m["sensor"]).ravel()[0]),
                        "sample_rate_hz": float(np.asarray(m["frequency"]).ravel()[0]),
                    }
                    break
            if self._meta is None:
                raise FileNotFoundError(f"no exercise files under {self.subdir}")
        return self._meta

    def montage(self):
        circ = self.meta["circumference_mm"]
        spacing = circ / 8.0
        side = {"r": "right", "l": "left"}.get(self.meta["laterality"], "n/a")
        positions = []
        for band in (0, 1):
            for i in range(8):
                positions.append({
                    "ch": band * 8 + i,
                    "angle_deg": round(i * 45.0 + band * 22.5, 1),
                    "axial_mm": band * self.MYO_WIDTH_MM,
                })
        return {
            "system": "ase.limb.v1",
            "site": "forearm-proximal",
            "side": side,
            "arrangement": "circumferential",
            "reference": "differential-adjacent",
            "positions": positions,
            "akasara.spacing_mm": round(spacing, 1),
            "akasara.circumference_mm": round(circ, 1),
            "akasara.axial_mm_basis": "nominal armband width; DB5 records only "
                                      "that band 2 is immediately distal to band 1",
        }

    def sessions(self):
        """One session per exercise file. Exercises were recorded as separate
        acquisitions, so treating them as separate sessions is what the data
        actually is -- not a convenience."""
        names = dict(enumerate(GESTURE_NAMES, start=1))
        out = []
        for e in (1, 2, 3):
            m = self._load(e)
            if m is None:
                continue
            emg = np.asarray(m["emg"], dtype=np.float64) / self.full_scale
            rs = np.asarray(m["restimulus"]).ravel().astype(int)
            gid = np.where(rs > 0, rs + self.EX_OFFSET[e], 0)
            out.append(Session(f"{self.subject}-e{e}", emg, gid, names))
        return out


class PdEegSource:
    """ds007822 -- three-player prisoner's-dilemma EEG, 19 channels at 300 Hz.

    Here to make "signal-agnostic" mean something. It differs from DB5 in every
    axis the spec has a word for: a different montage SYSTEM (10-20 labels, not
    limb geometry), a different Appendix A quality band, a different sample
    rate, and a different T1 transform (log band power, not time-domain
    features) -- so R-5.4's pinning is exercised on arithmetic the consumer has
    never seen rather than on the same formula with more channels.

    The cue is the ROUND NUMBER. Three players sat through the same forty
    rounds, so the round index is a shared timeline that exists for both people
    and belongs to neither -- the EEG analogue of DB5's shared movement.

    FULL SCALE, and why it is a constant. The BIDS sidecar declares microvolts;
    the recorded values run to ~1e9, six orders of magnitude above anything
    physiological. The published unit is therefore not usable and no physical
    claim is made here. What ASE needs is a full-scale reference, so one fixed
    constant in dataset-native units is declared and applied to every subject
    identically. Deriving the scale per recording instead would have been more
    flattering and would have made the T1 transform per-user ADAPTIVE, which
    R-5.5 requires a device to declare and offer a way out of. A constant is the
    only version of this that is not quietly adaptive.
    """

    kind = "eeg"
    channels = 19
    sample_rate_hz = 300.0
    full_scale = 1.0e9                 # dataset-native units; see class docstring
    mains_hz = 50.0

    # R-3.3.1, and this is the interesting half of the clause: this source
    # DECLARES NO T3. It cannot. T3 is "raw samples at ADC resolution", and this
    # recording arrives as floats whose declared unit (microvolts) is wrong by
    # six orders of magnitude and whose true unit and ADC width are both unknown.
    # There is no honest `unit` and no honest `adc_bits`, so the badge is absent
    # rather than filled with a number that would make the descriptor look more
    # complete than the data is. The same producer declaring the badge on DB5 and
    # refusing it here is the clause doing its job.
    t3 = None
    # T2 IS offerable: the chain below is applied by this producer and documented,
    # and "a.u." is a true statement about a stream whose scale is unknown.
    t2_filters = [
        {"kind": "detrend"},
        {"kind": "notch", "hz": 50, "q": 30},
        {"kind": "bandpass", "hz_low": 1, "hz_high": 45, "order": 4},
    ]
    t2_unit = "a.u."
    EPOCH_USABLE_S = 4.0               # epochs are 5 s at 4 s spacing; the last
                                       # second overlaps the next round

    def __init__(self, root, subject, task="pddecision"):
        self.root = root
        self.subject = subject
        self.task = task
        self.base = os.path.join(root, subject, "eeg", f"{subject}_task-{task}")
        if not os.path.exists(self.base + "_eeg.set"):
            raise FileNotFoundError(self.base + "_eeg.set")
        self._set = None

    def _load(self):
        if self._set is None:
            self._set = sio.loadmat(self.base + "_eeg.set",
                                    squeeze_me=True, struct_as_record=False)
        return self._set

    def _labels(self):
        return [str(c.labels) for c in self._load()["chanlocs"]]

    def montage(self):
        """ase.eeg.1020.v1 wants a `label` per channel and nothing else -- the
        coordinate system IS the label set, which is exactly why a standard
        montage is comparable across devices in a way a wristband is not."""
        labels = self._labels()
        status = {}
        chpath = self.base + "_channels.tsv"
        if os.path.exists(chpath):
            with open(chpath, newline="", encoding="utf-8") as fh:
                for row in csv.DictReader(fh, delimiter="\t"):
                    status[row["name"]] = row.get("status", "n/a")
        m = {
            "system": "ase.eeg.1020.v1",
            "site": "scalp",
            "side": "bilateral",
            "arrangement": "scattered",
            "reference": str(self._load().get("ref", "unknown")),
            "positions": [{"ch": i, "label": lab} for i, lab in enumerate(labels)],
        }
        bad = [lab for lab in labels if status.get(lab, "good") != "good"]
        if bad:
            m["akasara.channels_marked_bad"] = bad
        return m

    def sessions(self):
        s = self._load()
        data = np.asarray(s["data"], dtype=np.float64)      # (chan, samp, trial)
        srate = float(s["srate"])
        usable = int(round(self.EPOCH_USABLE_S * srate))

        onsets, names = {}, {}
        evpath = self.base + "_events.tsv"
        with open(evpath, newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh, delimiter="\t"):
                t = int(row["trial"])
                onsets[t] = float(row["onset"])
                names[t] = f"round {t} ({row.get('triad_outcome', '?')})"

        n_trials = data.shape[2]
        span = int(round(max(onsets.values()) * srate)) + usable
        samples = np.zeros((span, self.channels))
        labels = np.zeros(span, dtype=int)
        for k in range(n_trials):
            trial = k + 1
            if trial not in onsets:
                continue
            start = int(round(onsets[trial] * srate))
            seg = data[:, :usable, k].T / self.full_scale
            end = min(start + usable, span)
            samples[start:end] = seg[:end - start]
            labels[start:end] = trial
        return [Session(f"{self.subject}-{self.task}", samples, labels, names)]


class ThingsEeg2Source:
    """THINGS-EEG2 test partition -- 10 people, 17 posterior channels, 100 Hz.

    Here because of what ds007822 could NOT do. Its cue was the round number,
    and a round is not a state: across all 33 subjects only two categorical
    states are genuinely shared, so a cross-person retrieval question with
    eight or more alternatives cannot be asked of it at all. That is a property
    of the recording, not of the code, and no estimator fixes it.

    This dataset removes the ceiling by construction. All ten participants view
    the SAME 200 test images, 80 repetitions each, so there are 200 shared cues,
    consecutive cues are different states rather than the same state repeated,
    and the correspondence between two people's cue k is the stimulus itself
    rather than a shared clock.

        200 image conditions x 80 repetitions x 17 channels x 100 time points,
        epochs -0.2 .. 0.8 s around onset, resampled to 100 Hz.

    THE ORDER IS THE DISTRIBUTION'S, NOT THE RECORDING'S. The preprocessed
    release is indexed [condition][repetition] and does not carry acquisition
    order, so no reordering here could restore it and none is attempted: the
    stream is laid out condition-major and the descriptor says so. The analysis
    window is exactly one epoch and the stride equals it, so no window ever
    spans two epochs and no frame is an average of two different moments.

    WHY THIS SOURCE DECLARES ITSELF ADAPTIVE. The released samples have been
    multivariate-noise-normalised: a whitening matrix is estimated from each
    participant's own recording and applied to that participant's data. That is
    per-user adaptation, it reaches the exported T1 values, and R-5.5 says a
    device must not apply it without declaring it. So it is declared -- and
    declaring it truthfully is what exposed the hole in R-5.5, because the
    clause also requires a non-adaptive mode and this producer has none to
    offer: the un-whitened samples are not in the distribution. See R-5.5.1.
    """

    kind = "eeg"
    channels = 17
    sample_rate_hz = 100.0
    # Dataset-native units. Whitening leaves the samples in units of estimated
    # noise standard deviation, which is not a physical scale and not an
    # acquisition full scale either; one constant is declared, applied to every
    # subject identically, and chosen so that no subject clips. Deriving it per
    # recording would have made the export doubly per-user adaptive.
    full_scale = 128.0
    mains_hz = 50.0                    # Berlin; at 100 Hz this sits AT Nyquist

    # R-3.3.1 -- no badge, on both counts. T3 cannot be claimed: these are not
    # raw samples at ADC resolution and neither the unit nor the ADC width
    # survives the preprocessing. T2 cannot be claimed either, and that is the
    # part worth stating: T2 is the stream "after fixed, documented filtering",
    # and the filtering that produced these samples ends in a step that is not
    # fixed across users. A whitened stream is not this producer's T2.
    t3 = None
    t2_filters = None

    # R-5.5 / R-5.5.1. The adaptation is fitted once, off-line, by the dataset's
    # own preprocessing and is then frozen for the life of the export, so
    # `adapt_state` is constant per subject rather than per frame.
    adaptive = True
    adapt_scope = "frozen"
    adapt_fitted_on = (
        "multivariate noise normalisation (MVNN): a whitening matrix estimated "
        "from this participant's own EEG, averaged over image conditions and "
        "over both data partitions, applied to every epoch of that participant"
    )

    EPOCH_SAMPLES = 100

    def __init__(self, root, subject, meta="image_metadata.npy"):
        self.root = root
        self.subject = subject
        self.path = os.path.join(root, f"{subject}_test.npy")
        if not os.path.exists(self.path):
            raise FileNotFoundError(self.path)
        self.meta_path = os.path.join(root, meta)
        self._d = None

    def _load(self):
        if self._d is None:
            self._d = np.load(self.path, allow_pickle=True).item()
        return self._d

    @property
    def adapt_state(self):
        """R-5.5 wants the frame to identify WHICH adaptation produced it. One
        whitening matrix per participant, so the identifier is the participant
        and the fact that it never changes -- not a counter that would imply a
        state this export does not have."""
        return f"mvnn-frozen-{self.subject}"

    def montage(self):
        labels = [str(c) for c in self._load()["ch_names"]]
        return {
            "system": "ase.eeg.1020.v1",
            "site": "scalp",
            "side": "bilateral",
            "arrangement": "scattered",
            # Not "unknown" as a shrug: the preprocessed release genuinely does
            # not carry it, and whitening mixes the channels anyway, so any
            # reference named here would describe a stream that no longer exists.
            "reference": "unknown (not carried by the preprocessed release)",
            "positions": [{"ch": i, "label": lab} for i, lab in enumerate(labels)],
            "akasara.note": "occipital and parietal subset retained by the "
                            "dataset's preprocessing; the other 46 channels of "
                            "the original cap are not in this release",
        }

    def _cue_names(self):
        if not os.path.exists(self.meta_path):
            return {}
        m = np.load(self.meta_path, allow_pickle=True).item()
        con = [str(c) for c in np.asarray(m["test_img_concepts"])]
        return {i + 1: con[i].split("_", 1)[-1].replace("_", " ")
                for i in range(len(con))}

    def sessions(self):
        x = np.asarray(self._load()["preprocessed_eeg_data"], dtype=np.float64)
        n_cond, n_rep, n_ch, n_t = x.shape
        if n_ch != self.channels or n_t != self.EPOCH_SAMPLES:
            raise SystemExit(f"unexpected THINGS-EEG2 shape {x.shape}")
        peak = float(np.abs(x).max())
        if peak >= self.full_scale:
            raise SystemExit(
                f"{self.subject} peaks at {peak:.1f} in dataset units, at or "
                f"above the declared full scale {self.full_scale} -- §5.7 wants "
                "normalised samples inside +-1.0, and clipping them silently "
                "would be exporting an opinion")
        samples = (x.transpose(0, 1, 3, 2).reshape(-1, n_ch)) / self.full_scale
        labels = np.repeat(np.arange(1, n_cond + 1), n_rep * n_t)
        return [Session(f"{self.subject}-test", samples, labels,
                        self._cue_names())]


# canonical DB5 movement names in global-id order, used only as human-readable
# labels on the vendor-extension cue field. Text from the Ninapro exercise
# descriptions.
GESTURE_NAMES = [
    "index finger flexion", "index finger extension",
    "middle finger flexion", "middle finger extension",
    "ring finger flexion", "ring finger extension",
    "little finger flexion", "little finger extension",
    "thumb adduction", "thumb abduction",
    "thumb flexion", "thumb extension",
    "thumb up", "flexion of index and middle, extension of the others",
    "flexion of ring and little finger, extension of the others",
    "thumb opposing base of little finger",
    "abduction of all fingers", "fingers flexed together in a fist",
    "pointing index", "adduction of extended fingers",
    "wrist supination (axis middle finger)",
    "wrist pronation (axis middle finger)",
    "wrist supination (axis little finger)",
    "wrist pronation (axis little finger)",
    "wrist flexion", "wrist extension",
    "wrist radial deviation", "wrist ulnar deviation",
    "wrist extension with closed hand",
    "large diameter grasp", "small diameter grasp (tool)",
    "fixed hook grasp", "index finger extension grasp",
    "medium wrap", "ring grasp", "prismatic four fingers grasp",
    "stick grasp", "writing tripod grasp", "power sphere grasp",
    "three finger sphere grasp", "precision sphere grasp",
    "tripod grasp", "prismatic pinch grasp", "tip pinch grasp",
    "quadpod grasp", "lateral grasp", "parallel extension grasp",
    "extension type grasp", "power disk grasp",
    "open a bottle with a tripod grasp", "turn a screw", "cut something",
]


def subjects(root):
    return [os.path.basename(p) for p in
            sorted(glob.glob(os.path.join(root, "s*")),
                   key=lambda p: int(os.path.basename(p).lstrip("s")))]
