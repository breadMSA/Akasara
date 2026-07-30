#!/usr/bin/env python3
"""A consumer: two people's exported frames, processed jointly.

This is the other half of the exercise. `replay.py` shows the spec can be
PRODUCED against; this shows it can be CONSUMED against — it reads nothing but
`capability.json` and `frames.jsonl`, never the dataset, and never any private
state of the producer. If the descriptor is enough to fit a cross-person map,
then the descriptor is doing its job.

It answers one question the spec asks vendors to answer about themselves,
R-11.5: does this feature space beat its own channel-mean reduction at
calibration-free cross-person retrieval? A number stated relatively, with a
subject-level interval, because a threshold drafted from one dataset is a guess
(the absolute floor drafted from DB5 alone did not survive Hyser).

Two things it is careful about, both learned the hard way:

  * the unit of replication is the SUBJECT, not the ordered pair. Pairs share
    subjects, so an interval resampled over pairs is narrower than the evidence
    warrants — that mistake once turned a real effect into a reported null.
  * the comparison is PAIRED. Full and reduced are scored on the same split of
    the same pair, and the interval is over the per-subject difference.

    python align.py out/db5-s1 out/db5-s2 ... --out out/cross_user_margin.json
"""

import argparse
import json
import os
from collections import defaultdict

import numpy as np


# ------------------------------------------------------------------- loading
def load_capture(path):
    with open(os.path.join(path, "capability.json"), encoding="utf-8") as fh:
        cap = json.load(fh)
    frames = []
    with open(os.path.join(path, "frames.jsonl"), encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                frames.append(json.loads(line))
    return cap, [f for f in frames if f.get("tier") == "t1"]


def trials(frames, min_frames=2):
    """Group frames into cued trials: a maximal run of consecutive frames in
    one session carrying the same cue. Gaps in `seq` break a run, which is the
    whole reason R-5.3 makes them visible."""
    out = defaultdict(list)
    run, cue, sess, last_seq = [], None, None, None
    def flush():
        if cue is not None and len(run) >= min_frames:
            out[cue].append(np.mean(np.array(run), axis=0))
    for f in frames:
        c = f.get("akasara.cue")
        broken = (f["session_id"] != sess or c != cue
                  or (last_seq is not None and f["seq"] != last_seq + 1))
        if broken:
            flush()
            run, cue, sess = [], c, f["session_id"]
        if c is not None:
            run.append(f["values"])
        last_seq = f["seq"]
    flush()
    return out


def prototypes(frames):
    """cue -> mean feature vector over that cue's trials."""
    t = trials(frames)
    return {c: np.mean(np.array(v), axis=0) for c, v in t.items() if v}


# R-5.4.1 exists because of this function. The identifier pins WHICH transform
# ran; it does not pin the order of the answer, and reducing a feature-major
# vector as if it were channel-major averages RMS together with waveform length
# and reports the result as a baseline without failing anything. Descriptors
# written before that clause have no `t1.layout`, so the known ids are kept here
# as a fallback -- and an id that is in neither is refused rather than guessed.
LAYOUTS = {
    "akasara.replay.semg16.tdfeat.v1": "feature-major",
    "akasara.replay.eeg19.bandpower.v1": "feature-major",   # band-major
    "akasara.imu.tdfeat.v1": "channel-major",               # apps/gate
}


def channel_mean_reduction(X, channels, layout):
    """The degenerate space R-11.5 asks a vendor to beat: every channel
    collapsed to the array mean, so the per-channel structure that makes two
    forearms comparable is gone while the feature TYPES survive."""
    n_feat = X.shape[1] // channels
    if layout == "feature-major":
        cols = [X[:, i * channels:(i + 1) * channels] for i in range(n_feat)]
    elif layout == "channel-major":
        cols = [X[:, i::n_feat] for i in range(n_feat)]
    else:
        raise SystemExit(f"unknown layout {layout!r}")
    return np.stack([c.mean(axis=1) for c in cols], axis=1)


# ------------------------------------------------------------------ the fit
def fit_and_score(Xa, Xb, train_idx, test_idx, ridge=1.0):
    """Calibration-free direction A -> B: the map is fitted on gestures the
    test never sees, and no sample from the test gestures touches the
    standardisation either."""
    mu_a, sd_a = Xa[train_idx].mean(0), Xa[train_idx].std(0) + 1e-9
    mu_b, sd_b = Xb[train_idx].mean(0), Xb[train_idx].std(0) + 1e-9
    A = (Xa - mu_a) / sd_a
    B = (Xb - mu_b) / sd_b

    At, Bt = A[train_idx], B[train_idx]
    G = At.T @ At + ridge * np.eye(At.shape[1])
    W = np.linalg.solve(G, At.T @ Bt)

    pred = A[test_idx] @ W
    target = B[test_idx]
    pn = pred / (np.linalg.norm(pred, axis=1, keepdims=True) + 1e-12)
    tn = target / (np.linalg.norm(target, axis=1, keepdims=True) + 1e-12)
    sim = pn @ tn.T
    return float(np.mean(np.argmax(sim, axis=1) == np.arange(len(test_idx))))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("captures", nargs="+", help="directories written by replay.py")
    ap.add_argument("--out", help="write cross_user_margin.json here")
    ap.add_argument("--splits", type=int, default=20)
    ap.add_argument("--boots", type=int, default=5000)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--group-regex",
                    help="extract a group id from each model name; pairs are "
                         "then formed only WITHIN a group")
    ap.add_argument("--cross-group", action="store_true",
                    help="with --group-regex, form only BETWEEN-group pairs. "
                         "S11.5 warns a margin can be earned from generic "
                         "transferable structure; this is how you find out")
    ap.add_argument("--null", action="store_true",
                    help="break the cue correspondence between the two people "
                         "before fitting; a real effect must collapse to chance")
    ap.add_argument("--layout", choices=sorted(set(LAYOUTS.values())),
                    help="which axis of values[] runs over channels, for a "
                         "feature space this tool has not been told about")
    args = ap.parse_args()

    people = []
    space, channels, declared = None, None, set()
    for path in args.captures:
        cap, frames = load_capture(path)
        fs = cap["t1"]["feature_space"]
        if cap["t1"].get("layout"):
            declared.add(cap["t1"]["layout"])
        if space is None:
            space, channels = fs, cap["signal"]["channels"]
        elif fs != space:
            raise SystemExit(
                f"{path} exports {fs}, not {space} — R-5.4 says these are not "
                "the same space and a map must not be fitted across them")
        protos = prototypes(frames)
        people.append((cap["model"], protos))
        print(f"{cap['model']}: {len(frames)} frames -> {len(protos)} cued gestures")

    shared = sorted(set.intersection(*[set(p.keys()) for _, p in people]))
    if len(shared) < 8:
        raise SystemExit(f"only {len(shared)} gestures shared across captures")
    if len(declared) > 1:
        raise SystemExit(
            f"captures declare conflicting t1.layout {sorted(declared)} for one "
            "pinned feature space — R-5.4.1 makes that a contradiction, not a "
            "difference of opinion")
    layout = args.layout or (declared.pop() if declared else LAYOUTS.get(space))
    if layout == "opaque":
        raise SystemExit(
            "t1.layout is opaque: the producer states values[] does not factor "
            "into channels x features, so the R-11.5 channel-mean baseline does "
            "not exist for it")
    if layout is None:
        raise SystemExit(
            f"no layout known for feature space {space}, and no t1.layout in the "
            "descriptor (R-5.4.1) — pass --layout. The R-11.5 baseline collapses "
            "channels, and guessing which axis they run on is worse than stopping.")

    print(f"\n{len(people)} people, {len(shared)} shared cues, space {space} "
          f"({layout})")

    mats = []
    for k, (name, protos) in enumerate(people):
        X = np.array([protos[c] for c in shared], dtype=np.float64)
        if args.null and k > 0:
            # Same rows, same statistics, wrong partner: every person after the
            # first has their cues permuted, so "gesture i of A" no longer means
            # "gesture i of B". Anything the map can still recover this way was
            # never about the shared movement.
            perm = np.random.default_rng(args.seed + 77 + k).permutation(len(shared))
            X = X[perm]
        mats.append((name, X, channel_mean_reduction(X, channels, layout)))

    rng = np.random.default_rng(args.seed)
    n = len(shared)
    n_train = max(4, n // 2)
    n_test = n - n_train

    groups = None
    if args.group_regex:
        import re
        groups = []
        for name, _, _ in mats:
            m = re.search(args.group_regex, name)
            if not m:
                raise SystemExit(f"--group-regex does not match model {name!r}")
            groups.append(m.group(1))
        print("groups: " + ", ".join(f"{n}={g}" for (n, _, _), g in zip(mats, groups)))

    # per ordered pair: paired full-vs-reduced on identical splits
    per_pair = {}
    for i, (na, Xa, Ra) in enumerate(mats):
        for j, (nb, Xb, Rb) in enumerate(mats):
            if i == j:
                continue
            if groups is not None:
                same = groups[i] == groups[j]
                if same == bool(args.cross_group):
                    continue
            f, r = [], []
            for s in range(args.splits):
                perm = np.random.default_rng(args.seed + 1000 * i + 10 * j + s).permutation(n)
                tr, te = perm[:n_train], perm[n_train:]
                f.append(fit_and_score(Xa, Xb, tr, te))
                r.append(fit_and_score(Ra, Rb, tr, te))
            per_pair[(i, j)] = (float(np.mean(f)), float(np.mean(r)))

    # aggregate to the SUBJECT, then bootstrap over subjects
    subj_full = np.zeros(len(mats))
    subj_red = np.zeros(len(mats))
    keep = []
    for k in range(len(mats)):
        vals = [v for (i, j), v in per_pair.items() if i == k or j == k]
        if not vals:
            continue
        subj_full[k] = np.mean([v[0] for v in vals])
        subj_red[k] = np.mean([v[1] for v in vals])
        keep.append(k)
    if not per_pair:
        raise SystemExit("no pairs survived the grouping filter")
    subj_full, subj_red = subj_full[keep], subj_red[keep]
    delta = subj_full - subj_red

    boots = np.array([
        np.mean(delta[rng.integers(0, len(delta), len(delta))])
        for _ in range(args.boots)
    ])
    lo, hi = np.percentile(boots, [2.5, 97.5])
    chance = 1.0 / n_test

    print(f"\nfull feature space   P@1 {subj_full.mean():.3f}  "
          f"({subj_full.mean()/chance:.1f}x chance)")
    print(f"channel-mean reduced P@1 {subj_red.mean():.3f}  "
          f"({subj_red.mean()/chance:.1f}x chance)")
    print(f"margin {delta.mean():+.3f}  95% CI [{lo:+.3f}, {hi:+.3f}]  "
          f"over {len(delta)} subjects, {len(per_pair)} ordered pairs")
    print(f"chance {chance:.3f} ({n_test}-way, {n_train} gestures fitted on)")
    positives = int(np.sum(delta > 0))
    print(f"{positives}/{len(delta)} subjects positive")

    margin = {
        "margin": round(float(delta.mean()), 4),
        "ci_low": round(float(lo), 4),
        "ci_high": round(float(hi), 4),
        "task": (f"calibration-free cross-subject retrieval of held-out cues, "
                 f"{n_test}-way, fitted on {n_train} disjoint cues, "
                 f"{args.splits} random splits"),
        "subjects": int(len(delta)),
        "bootstrap_unit": "subject",
        "akasara.full_p1": round(float(subj_full.mean()), 4),
        "akasara.reduced_p1": round(float(subj_red.mean()), 4),
        "akasara.chance": round(float(chance), 4),
    }
    if args.out:
        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(margin, fh, indent=2)
        print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
