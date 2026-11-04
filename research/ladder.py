"""Guarded model ladder: does anything beat PhenoAge at predicting death?

    .venv-research/bin/python research/ladder.py lock    # once: lock the test set
    .venv-research/bin/python research/ladder.py cv      # all choices, training data only
    .venv-research/bin/python research/ladder.py test    # once: final comparison

Guardrails
1. `lock` draws a 30% test set from everyone with valid accelerometry,
   stratified by death, and writes its SEQNs to research/locked_test_seqn.txt.
   Nothing else reads the test rows until `test`.
2. `cv` makes every choice (PhenoAge acceleration cap, raw vs censored steps,
   ridge penalties, boosting length, which model to deploy) with 5-fold
   cross-validation inside the 70% training set, and writes
   research/ladder_cv.json plus the CV section of research/LADDER.md.
3. Every model tried is logged, including failures.
4. Primary metric: Harrell's C for 10-year all-cause mortality (follow-up
   truncated at 120 months), difference vs PhenoAge with a paired bootstrap
   95% CI, and calibration. Secondary: 5-year C.

Deployment rule (fixed before `test`): candidates are ordered by how many
band inputs they need. Start from PhenoAge; step up to a candidate only if
its out-of-fold 10-year C beats the current choice by >= 0.003 with the
bootstrap CI above zero, compared on the same people.
"""

import json
import os
import sys

import numpy as np
import pandas as pd
from scipy.optimize import minimize

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
LOCK = os.path.join(HERE, "locked_test_seqn.txt")
CV_OUT = os.path.join(HERE, "ladder_cv.json")
REPORT = os.path.join(HERE, "LADDER.md")
MARKERS = ["albumin", "creatinine", "glucose", "crp", "lymphocyte_pct", "mcv", "rdw", "alp", "wbc"]
N_BOOT = 200
MIN_GAIN = 0.003


# ------------------------------------------------------------------ data
def load_all():
    df = pd.read_csv(os.path.join(DATA, "analysis.csv"))
    df = df[(df.permth_exm > 0) & (df.valid_days >= 4) & (df.cpm > 0)].copy()
    df["t"] = df.permth_exm.astype(float)
    df["d"] = (df.mortstat == 1).astype(int)
    df["log_tac"] = np.log(df.tac_per_day)
    df["log_wear"] = np.log(df.wear_min_per_day)
    df["log_mvpa"] = np.log1p(df.mvpa_min_per_day)
    df["sed_frac"] = df.sed_min_per_day / df.wear_min_per_day
    df["log_steps_raw"] = np.log(df.steps_per_day.clip(lower=500))
    df["log_steps_c"] = np.log(df.steps_censored_per_day.clip(lower=500))
    df["log_crp"] = np.log(df.crp)
    return df.reset_index(drop=True)


def lock():
    if os.path.exists(LOCK):
        sys.exit("Test set already locked: %s" % LOCK)
    df = load_all()
    rng = np.random.default_rng(20261104)
    test = []
    for dead in (0, 1):
        ids = df.SEQN[df.d == dead].to_numpy()
        test.extend(rng.choice(ids, int(round(0.3 * len(ids))), replace=False).tolist())
    with open(LOCK, "w") as f:
        f.write("\n".join(str(int(s)) for s in sorted(test)) + "\n")
    print("locked %d of %d people as the test set" % (len(test), len(df)))


def split():
    df = load_all()
    test_ids = set(int(x) for x in open(LOCK).read().split())
    is_test = df.SEQN.astype(int).isin(test_ids)
    return df[~is_test].reset_index(drop=True), df[is_test].reset_index(drop=True)


# ------------------------------------------------------------------ models
def truncate(t, d, months):
    return np.minimum(t, months), (d == 1) & (t <= months)


def fit_gompertz(X, t, d, ridge=0.0):
    """Gompertz PH on months; ridge penalty on standardized slopes."""
    X = np.asarray(X, float)
    mu, sd = X.mean(0), X.std(0)
    sd[sd == 0] = 1
    Z = (X - mu) / sd
    n = len(t)

    def nll(p):
        a, b, g = p[0], p[1:-1], p[-1]
        eta = a + Z @ b
        H = np.exp(eta) * (np.expm1(g * t) / g if abs(g) > 1e-10 else t)
        return -(np.sum(d * (eta + g * t)) - np.sum(H)) / n + ridge * np.sum(b ** 2)

    p0 = np.zeros(Z.shape[1] + 2)
    p0[0], p0[-1] = np.log(d.sum() / t.sum()), 0.005
    res = minimize(nll, p0, method="L-BFGS-B")
    b = res.x[1:-1] / sd
    return {"a": res.x[0] - np.sum(res.x[1:-1] * mu / sd), "b": b, "g": res.x[-1]}


def lin(m, X):
    return m["a"] + np.asarray(X, float) @ m["b"]


def mort(m, X, months=120):
    g = m["g"]
    return -np.expm1(-np.exp(lin(m, X)) * np.expm1(g * months) / g)


def c_index(risk, t, d):
    risk, t, d = np.asarray(risk), np.asarray(t), np.asarray(d)
    conc = ties = total = 0.0
    for i in np.flatnonzero(d):
        later = t > t[i]
        n = later.sum()
        if n:
            r = risk[later]
            conc += (risk[i] > r).sum()
            ties += (risk[i] == r).sum()
            total += n
    return (conc + 0.5 * ties) / total


def c10(risk, t, d):
    return c_index(risk, *truncate(t, d, 120))


def c5(risk, t, d):
    return c_index(risk, *truncate(t, d, 60))


def boot_delta(r0, r1, t, d, rng, fn=c10):
    idx = np.arange(len(t))
    out = []
    for _ in range(N_BOOT):
        s = rng.choice(idx, len(idx))
        out.append(fn(r1[s], t[s], d[s]) - fn(r0[s], t[s], d[s]))
    return [float(x) for x in np.percentile(out, [2.5, 97.5])]


# ------------------------------------------------------------------ features
class Accel:
    """PhenoAge minus its trend on age, fitted and capped on training rows."""

    def __init__(self, train, cap):
        self.slope, self.icpt = np.polyfit(train.age, train.phenoage, 1)
        raw = train.phenoage - (self.icpt + self.slope * train.age)
        self.cap = cap
        self.lo, self.hi = (np.percentile(raw, [cap, 100 - cap]) if cap else (-np.inf, np.inf))

    def __call__(self, df):
        return (df.phenoage - (self.icpt + self.slope * df.age)).clip(self.lo, self.hi)


def design(df, accel, cols):
    X = pd.DataFrame({"age": df.age})
    for c in cols:
        if c == "accel":
            X["accel"] = accel(df)
        elif c == "markers":
            for m in MARKERS:
                X[m] = df["log_crp"] if m == "crp" else df[m]
        else:
            X[c] = df[c]
    return X.to_numpy(float)


# ------------------------------------------------------------------ boosting (ceiling only)
def cox_grad(eta, t, d):
    order = np.argsort(-t, kind="stable")
    e = np.exp(eta[order] - eta.max())
    S = np.cumsum(e)                        # risk-set sums, descending time
    dd = d[order].astype(float)
    # sum over events j with t_j <= t_i of 1/S_j, in descending-time order
    inv = np.where(dd == 1, 1.0 / S, 0.0)
    tail = np.cumsum(inv[::-1])[::-1]
    g = dd - e * tail
    out = np.empty_like(g)
    out[order] = g
    return out


def stump_tree(X, r, depth=2, min_leaf=40):
    """Tiny regression tree on residuals r, splits at feature quantiles."""
    def best(idx):
        best_s = (0.0, None)
        rr = r[idx]
        tot, n = rr.sum(), len(idx)
        for j in range(X.shape[1]):
            x = X[idx, j]
            qs = np.unique(np.nanpercentile(x, np.linspace(5, 95, 19)))
            for q in qs:
                left = x <= q
                nl = left.sum()
                if nl < min_leaf or n - nl < min_leaf:
                    continue
                sl = rr[left].sum()
                gain = sl ** 2 / nl + (tot - sl) ** 2 / (n - nl) - tot ** 2 / n
                if gain > best_s[0]:
                    best_s = (gain, (j, q))
        return best_s[1]

    def grow(idx, level):
        split_ = best(idx) if level < depth else None
        if split_ is None:
            return ("leaf", r[idx].mean())
        j, q = split_
        left = idx[X[idx, j] <= q]
        right = idx[X[idx, j] > q]
        return ("node", j, q, grow(left, level + 1), grow(right, level + 1))

    return grow(np.arange(len(r)), 0)


def tree_predict(tree, X):
    if tree[0] == "leaf":
        return np.full(len(X), tree[1])
    _, j, q, l, r = tree
    out = np.empty(len(X))
    m = X[:, j] <= q
    out[m] = tree_predict(l, X[m])
    out[~m] = tree_predict(r, X[~m])
    return out


def boost(X, t, d, n_iter, lr=0.05):
    eta, trees = np.zeros(len(t)), []
    for _ in range(n_iter):
        tree = stump_tree(X, cox_grad(eta, t, d))
        eta += lr * tree_predict(tree, X)
        trees.append(tree)
    return trees


def boost_predict(trees, X, lr=0.05):
    eta = np.zeros(len(X))
    for tree in trees:
        eta += lr * tree_predict(tree, X)
    return eta


# ------------------------------------------------------------------ ladder definition
BOTH = "both cycles"
D05 = "2005-06 only"
HIP_ONLY = ["log_tac", "log_wear", "tlac_per_day", "sed_frac", "astp", "satp", "m10", "is", "iv"]
CANDIDATES = [
    # name, inputs beyond age + blood, rows, band-transferable, kind
    ("D0 PhenoAge", ["accel"], BOTH, True, "gompertz"),
    ("D1 PhenoAge + resting pulse", ["accel", "pulse"], BOTH, True, "gompertz"),
    ("D2 PhenoAge + MVPA", ["accel", "log_mvpa"], BOTH, True, "gompertz"),
    ("D3 PhenoAge + steps", ["accel", "STEPS"], D05, True, "gompertz"),
    ("D4 PhenoAge + MVPA + pulse", ["accel", "log_mvpa", "pulse"], BOTH, True, "gompertz"),
    ("D5 PhenoAge + steps + pulse", ["accel", "STEPS", "pulse"], D05, True, "gompertz"),
    ("D6 PhenoAge + steps + peak cadence + pulse", ["accel", "STEPS", "peak30_cadence", "pulse"], D05, True, "gompertz"),
    ("D7 Refit 9 markers + steps + pulse (ridge)", ["markers", "STEPS", "pulse"], D05, True, "ridge"),
    ("R1 PhenoAge + total activity + wear time", ["accel", "log_tac", "log_wear"], BOTH, False, "gompertz"),
    ("R2 PhenoAge + all hip features (ridge)", ["accel", "log_mvpa"] + HIP_ONLY, BOTH, False, "ridge"),
    ("R3 Refit 9 markers + all hip features (ridge)", ["markers", "log_mvpa"] + HIP_ONLY, BOTH, False, "ridge"),
    ("R3b Refit 9 markers only (ridge)", ["markers"], BOTH, False, "ridge"),
    ("R5 Ceiling: boosted trees, all features + pulse", ["markers", "log_mvpa", "pulse"] + HIP_ONLY, BOTH, False, "boost"),
]
DEPLOY_ORDER = ["D1 PhenoAge + resting pulse", "D2 PhenoAge + MVPA", "D3 PhenoAge + steps",
                "D4 PhenoAge + MVPA + pulse", "D5 PhenoAge + steps + pulse",
                "D6 PhenoAge + steps + peak cadence + pulse",
                "D7 Refit 9 markers + steps + pulse (ridge)"]
RIDGES = [0.0, 0.001, 0.003, 0.01, 0.03]
BOOST_ITERS = [50, 100, 200, 400]
CAPS = [0, 1, 2.5, 5]


def rows(df, which, cols):
    sub = df if which == BOTH else df[df.cycle == "2005-2006"]
    need = [c for c in cols if c not in ("accel", "markers", "STEPS")]
    if "STEPS" in cols:
        need.append("log_steps_c")
    return sub.dropna(subset=need).reset_index(drop=True)


def resolve(cols, steps_col):
    return [steps_col if c == "STEPS" else c for c in cols]


def fit_predict(train, test, cols, kind, cap, ridge=0.0, iters=0):
    accel = Accel(train, cap)
    Xtr, Xte = design(train, accel, cols), design(test, accel, cols)
    t, d = train.t.to_numpy(), train.d.to_numpy()
    if kind == "boost":
        med = np.nanmedian(Xtr, axis=0)
        Xtr = np.where(np.isnan(Xtr), med, Xtr)
        Xte = np.where(np.isnan(Xte), med, Xte)
        trees = boost(Xtr, *truncate(t, d, 120), iters)
        return boost_predict(trees, Xte), None, None
    m = fit_gompertz(Xtr, t, d, ridge)
    return lin(m, Xte), m, (accel, Xte)


def oof(df, cols, kind, cap, rng_seed, ridge=0.0, iters=0):
    folds = np.random.default_rng(rng_seed).permutation(len(df)) % 5
    risk = np.zeros(len(df))
    for k in range(5):
        tr, te = df[folds != k].reset_index(drop=True), df[folds == k].reset_index(drop=True)
        risk[folds == k] = fit_predict(tr, te, cols, kind, cap, ridge, iters)[0]
    return risk


def run_cv():
    train, _ = split()          # the test rows are dropped here and never touched
    rng = np.random.default_rng(7)
    log = {"n_train": len(train), "deaths_train": int(train.d.sum()), "models": {}, "choices": {}}

    # Choice 1: PhenoAge acceleration cap (on D0 rows)
    base = rows(train, BOTH, ["accel"])
    cap_c = {cap: c10(oof(base, ["accel"], "gompertz", cap, 1), base.t.to_numpy(), base.d.to_numpy())
             for cap in CAPS}
    cap = max(cap_c, key=cap_c.get)
    log["choices"]["accel_cap_percent"] = {"tried": {str(k): v for k, v in cap_c.items()}, "chosen": cap}

    # Choice 2: raw vs censored steps (on 2005-06 rows)
    st = rows(train, D05, ["accel", "STEPS"]).dropna(subset=["log_steps_raw"]).reset_index(drop=True)
    sc = {col: c10(oof(st, ["accel", col], "gompertz", cap, 2), st.t.to_numpy(), st.d.to_numpy())
          for col in ("log_steps_c", "log_steps_raw")}
    steps_col = max(sc, key=sc.get)
    log["choices"]["steps"] = {"tried": sc, "chosen": steps_col}

    # Every candidate: out-of-fold risk, compared with D0 refitted on the same rows
    oof_risk = {}
    for name, cols, which, transferable, kind in CANDIDATES:
        cols_r = resolve(cols, steps_col)
        df = rows(train, which, cols)
        t, d = df.t.to_numpy(), df.d.to_numpy()
        ridge, iters = 0.0, 0
        if kind == "ridge":
            rc = {r: c10(oof(df, cols_r, kind, cap, 3, ridge=r), t, d) for r in RIDGES}
            ridge = max(rc, key=rc.get)
        if kind == "boost":
            bc = {n: c10(oof(df, cols_r, kind, cap, 4, iters=n), t, d) for n in BOOST_ITERS}
            iters = max(bc, key=bc.get)
        r = oof(df, cols_r, kind, cap, 5, ridge=ridge, iters=iters)
        r0 = oof(df, ["accel"], "gompertz", cap, 5)
        entry = {
            "inputs": cols_r, "rows": which, "band_transferable": transferable, "kind": kind,
            "n": len(df), "deaths": int(d.sum()), "ridge": ridge, "boost_iters": iters,
            "c10": c10(r, t, d), "c10_phenoage_same_rows": c10(r0, t, d),
            "c5": c5(r, t, d), "c5_phenoage_same_rows": c5(r0, t, d),
        }
        entry["delta_c10"] = entry["c10"] - entry["c10_phenoage_same_rows"]
        entry["delta_c10_ci"] = boot_delta(r0, r, t, d, rng)
        entry["delta_c5"] = entry["c5"] - entry["c5_phenoage_same_rows"]
        if kind == "ridge":
            entry["ridge_tried"] = {str(k): v for k, v in rc.items()}
        if kind == "boost":
            entry["boost_tried"] = {str(k): v for k, v in bc.items()}
        log["models"][name] = entry
        oof_risk[name] = (df.SEQN.to_numpy(), r)
        print("%-50s C10 %.4f vs %.4f  delta %+.4f (%+.4f to %+.4f)" % (
            name, entry["c10"], entry["c10_phenoage_same_rows"], entry["delta_c10"],
            *entry["delta_c10_ci"]), flush=True)

    # Deployment rule, applied on out-of-fold predictions only
    chosen = "D0 PhenoAge"
    steps_log = []
    for name in DEPLOY_ORDER:
        cand = log["models"][name]
        if chosen == "D0 PhenoAge":
            gain, ci = cand["delta_c10"], cand["delta_c10_ci"]
        else:
            # compare with the current choice on the people both models cover
            s0, r0 = oof_risk[chosen]
            s1, r1 = oof_risk[name]
            common = np.intersect1d(s0, s1)
            a = pd.Series(r0, index=s0).loc[common].to_numpy()
            b = pd.Series(r1, index=s1).loc[common].to_numpy()
            sub = train.set_index("SEQN").loc[common]
            t, d = sub.t.to_numpy(), sub.d.to_numpy()
            gain = c10(b, t, d) - c10(a, t, d)
            ci = boot_delta(a, b, t, d, rng)
        ok = gain >= MIN_GAIN and ci[0] > 0
        steps_log.append({"candidate": name, "vs": chosen, "gain": gain, "ci": ci, "accepted": ok})
        if ok:
            chosen = name
    log["choices"]["deploy_steps"] = steps_log
    log["choices"]["deployed_model"] = chosen
    with open(CV_OUT, "w") as f:
        json.dump(log, f, indent=2, default=float)
    print("deployed model (chosen in CV):", chosen)


def km_risk(t, d, months=120):
    order = np.argsort(t)
    t, d = t[order], d[order]
    s, n = 1.0, len(t)
    for i in range(n):
        if t[i] > months:
            break
        if d[i]:
            s *= 1 - 1 / (n - i)
    return 1 - s


def run_test():
    log = json.load(open(CV_OUT))
    train, test = split()
    cap = log["choices"]["accel_cap_percent"]["chosen"]
    steps_col = log["choices"]["steps"]["chosen"]
    rng = np.random.default_rng(11)
    res = {"n_test": len(test), "deaths_test": int(test.d.sum()), "models": {}}
    for name, cols, which, transferable, kind in CANDIDATES:
        e = log["models"][name]
        cols_r = resolve(cols, steps_col)
        tr, te = rows(train, which, cols), rows(test, which, cols)
        r, m, extra = fit_predict(tr, te, cols_r, kind, cap, e["ridge"], e["boost_iters"])
        r0, m0, extra0 = fit_predict(tr, te, ["accel"], "gompertz", cap)
        t, d = te.t.to_numpy(), te.d.to_numpy()
        out = {"n": len(te), "deaths": int(d.sum()),
               "c10": c10(r, t, d), "c10_phenoage": c10(r0, t, d),
               "c5": c5(r, t, d), "c5_phenoage": c5(r0, t, d)}
        out["delta_c10"] = out["c10"] - out["c10_phenoage"]
        out["delta_c10_ci"] = boot_delta(r0, r, t, d, rng)
        out["delta_c5"] = out["c5"] - out["c5_phenoage"]
        out["delta_c5_ci"] = boot_delta(r0, r, t, d, rng, fn=c5)
        if m is not None:
            p = mort(m, extra[1])
            out["mean_predicted_10y"] = float(p.mean())
            out["observed_10y_km"] = float(km_risk(t, d))
            # calibration slope: refit Gompertz on the linear predictor in the test rows
            out["calibration_slope"] = float(fit_gompertz(r[:, None], t, d)["b"][0])
            q = pd.qcut(p, 5, labels=False, duplicates="drop")
            out["calibration_quintiles"] = [
                {"predicted": float(p[q == k].mean()), "observed": float(km_risk(t[q == k], d[q == k]))}
                for k in sorted(set(q))]
        res["models"][name] = out
        print("%-50s test C10 %.4f vs %.4f  delta %+.4f (%+.4f to %+.4f)" % (
            name, out["c10"], out["c10_phenoage"], out["delta_c10"], *out["delta_c10_ci"]), flush=True)
    res["deployed_model"] = log["choices"]["deployed_model"]
    with open(os.path.join(HERE, "ladder_test.json"), "w") as f:
        json.dump(res, f, indent=2, default=float)


MAPPING = [
    ("Steps", "PAXSTEP, counted in minutes >= 500 counts (hip ActiGraph 7164)",
     "Wrist bands count about 1,400 more steps/day than hip ActiGraphs, limits of agreement "
     "about -2,300 to +5,200; the studies used the newer GT3X and raw steps. High uncertainty."),
    ("MVPA minutes", "minutes >= 2020 counts/min on the hip (Troiano 2008)",
     "No validated mapping. Band \"active minutes\" use heart rate or cadence rules that differ "
     "by brand; a cadence of about 100 steps/min is a common moderate-intensity threshold, but "
     "the count cut-point and band minutes are not interchangeable. Very high uncertainty."),
    ("Resting heart rate", "BPXPLS, 60-second seated pulse after 5 minutes' rest at the exam",
     "Band resting HR is usually measured during sleep or long rest and runs several bpm lower "
     "than a seated clinic pulse; no conversion was fitted. Moderate uncertainty."),
    ("Peak 30-min cadence", "mean of each day's 30 highest step-minutes (hip)",
     "Bands can report cadence, but rarely this summary; same step-count caveats. High uncertainty."),
    ("Sleep duration and timing", "not available: NHANES 2003-06 asked people to remove the "
     "monitor at night", "Cannot be tested with these data."),
]


def fmt(x, ci=None):
    s = "%+.4f" % x
    return s + (" (%+.4f to %+.4f)" % tuple(ci) if ci else "")


def report():
    cv = json.load(open(CV_OUT))
    te = json.load(open(os.path.join(HERE, "ladder_test.json")))
    sha = __import__("hashlib").sha256(open(LOCK, "rb").read()).hexdigest()
    L = []
    o = L.append
    o("## 4. Guarded model ladder (final)")
    o("")
    o("This section supersedes the steps model in sections 3 and 'The combined VitalAge "
      "model' above. That model was chosen after looking at results that included its "
      "evaluation data, so its gain was preliminary.")
    o("")
    o("**Guardrails.** A 30%% test set (%d of %d adults with valid accelerometry, %d deaths, "
      "stratified by death) was drawn and committed (`research/locked_test_seqn.txt`, "
      "SHA-256 `%s`, commit 6c8ab38) before any ladder model was fitted. Every choice below "
      "was made with 5-fold cross-validation in the other 70%% (%d adults, %d deaths). "
      "The test set was used once, after the deployed model was fixed. Primary metric: "
      "Harrell's C for 10-year mortality; secondary: 5-year C; plus calibration."
      % (te["n_test"], te["n_test"] + cv["n_train"], te["deaths_test"], sha,
         cv["n_train"], cv["deaths_train"]))
    o("")
    ch = cv["choices"]
    o("**Choices made in CV.** PhenoAge acceleration cap: %s (tried %s). Steps: `%s` "
      "(tried %s). Ridge penalties and boosting length per model, listed in "
      "`research/ladder_cv.json`. Rest-activity L5 and relative amplitude were computed but "
      "dropped before modelling: with the monitor off at night, L5 is 0 for most people and "
      "amplitude is 1." % (
          "%s/%s percentiles" % (ch["accel_cap_percent"]["chosen"], 100 - ch["accel_cap_percent"]["chosen"]),
          ", ".join("%s%%: C10 %.4f" % (k, v) for k, v in ch["accel_cap_percent"]["tried"].items()),
          ch["steps"]["chosen"],
          ", ".join("%s: %.4f" % (k, v) for k, v in ch["steps"]["tried"].items())))
    o("")
    o("### Every model tried")
    o("")
    o("10-year C change vs PhenoAge (age + capped acceleration) refitted on the same people, "
      "with paired bootstrap 95% CIs. D = band-transferable inputs, R = research-only "
      "(hip-specific counts or a refit that needs no band).")
    o("")
    o("| Model | Rows | CV n (deaths) | CV change in 10-y C | Test n (deaths) | Test change in 10-y C | Test change in 5-y C | Test calibration slope |")
    o("|---|---|---|---|---|---|---|---|")
    for name, *_ in CANDIDATES:
        c, t = cv["models"][name], te["models"][name]
        slope = t.get("calibration_slope")
        o("| %s | %s | %d (%d) | %s | %d (%d) | %s | %s | %s |" % (
            name, c["rows"], c["n"], c["deaths"], fmt(c["delta_c10"], c["delta_c10_ci"]),
            t["n"], t["deaths"], fmt(t["delta_c10"], t["delta_c10_ci"]),
            fmt(t["delta_c5"], t["delta_c5_ci"]), "%.2f" % slope if slope else "n/a"))
    o("")
    o("Test 10-year C for PhenoAge alone: %.4f (all test rows)." % te["models"]["D0 PhenoAge"]["c10"])
    o("")
    o("### Deployment decision (made in CV, before the test)")
    o("")
    for s in ch["deploy_steps"]:
        o("- %s vs %s: %s → %s" % (s["candidate"], s["vs"], fmt(s["gain"], s["ci"]),
                                  "accepted" if s["accepted"] else "rejected"))
    dep = ch["deployed_model"]
    o("")
    o("Deployed by the rule: **%s**." % dep)
    o("")
    t = te["models"][dep]
    o("### Result on the locked test set")
    o("")
    helps = t["delta_c10_ci"][0] > 0
    o("%s: 10-year C %.4f vs PhenoAge %.4f, change %s; 5-year change %s. Mean predicted "
      "10-year mortality %.1f%% vs %.1f%% observed (Kaplan-Meier), calibration slope %.2f "
      "(PhenoAge alone: %.1f%%, slope %.2f)." % (
          dep, t["c10"], t["c10_phenoage"], fmt(t["delta_c10"], t["delta_c10_ci"]),
          fmt(t["delta_c5"], t["delta_c5_ci"]), 100 * t["mean_predicted_10y"],
          100 * t["observed_10y_km"], t["calibration_slope"],
          100 * te["models"]["D0 PhenoAge"]["mean_predicted_10y"],
          te["models"]["D0 PhenoAge"]["calibration_slope"]))
    o("")
    o("| Quintile of predicted risk | Predicted 10-y mortality | Observed (KM) |")
    o("|---|---|---|")
    for i, q in enumerate(t["calibration_quintiles"], 1):
        o("| %d | %.1f%% | %.1f%% |" % (i, 100 * q["predicted"], 100 * q["observed"]))
    o("")
    o("### Verdict")
    o("")
    if helps:
        o("**The deployed model beats PhenoAge on the locked test set.**")
    else:
        o("**No combined model is shipped.** The model the pre-registered rule chose did not "
          "beat PhenoAge on the locked test set: the 95% CI of the 10-year C change includes "
          "zero. The steps model shipped earlier (D3) also fails this test. Blood age "
          "(PhenoAge) and the literature-based Fitness Age stay as they are.")
        o("")
        o("Some models not chosen in CV did well on the test set (notably D7, a ridge refit "
          "of the 9 markers with steps and pulse, and the research-only refits R3/R3b). "
          "Choosing one of them now would use the test set for selection, so they are "
          "reported but not shipped. They are reasonable candidates for a future study with "
          "a fresh test set, for example NHANES 2011-2014 wrist accelerometry.")
    o("")
    o("The boosted-tree ceiling (R5, a simple stump-boosted Cox model written for this study) "
      "did worse than PhenoAge in CV and on the test set, so it says little about how much "
      "signal a simple model misses; a tuned random survival forest would be a better ceiling.")
    o("")
    o("### How deployable inputs map from NHANES to a wrist band")
    o("")
    o("| Band input | NHANES variable used | Mapping and uncertainty |")
    o("|---|---|---|")
    for a, b, c in MAPPING:
        o("| %s | %s | %s |" % (a, b, c))
    o("")
    o("Feature definitions follow Troiano et al. 2008 (wear, MVPA), Tudor-Locke et al. 2009 "
      "(censored steps), van Someren et al. 1999 (rest-activity rhythm) and Smirnova et al. "
      "2020, *J Gerontol A* 75(9):1779-1785, doi:10.1093/gerona/glz193 (total activity and "
      "active/sedentary transition probabilities in NHANES 2003-06).")
    text = "\n".join(L) + "\n"

    path = os.path.join(HERE, "RESULTS.md")
    body = open(path).read()
    marker = "## 4. Guarded model ladder (final)"
    if marker in body:
        start = body.index(marker)
        end = body.index("## Methods", start)
        body = body[:start] + body[end:]
    body = body.replace("## Methods", text + "\n## Methods", 1)
    open(path, "w").write(body)
    print(text)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    {"lock": lock, "cv": run_cv, "test": run_test, "report": report}.get(cmd, lambda: sys.exit(__doc__))()
