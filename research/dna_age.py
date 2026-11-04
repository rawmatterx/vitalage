"""Does a blood score track DNA-methylation aging? (RESULTS.md section 9)

    .venv-research/bin/python research/dna_age.py build    # research/data/dna_age.csv
    .venv-research/bin/python research/dna_age.py lock     # once: research/locked_test_dna.txt
    .venv-research/bin/python research/dna_age.py cv       # 70% only -> research/dna_age_cv.json
    .venv-research/bin/python research/dna_age.py test     # once -> research/dna_age_test.json
"""

import hashlib
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
sys.path.insert(0, os.path.dirname(HERE))

from phenoage.core import phenoage_from_canonical  # noqa: E402

LOCK = os.path.join(HERE, "locked_test_dna.txt")
CV_OUT = os.path.join(HERE, "dna_age_cv.json")
TEST_OUT = os.path.join(HERE, "dna_age_test.json")
MARKERS = ["albumin", "creatinine", "glucose", "crp", "lymphocyte_pct", "mcv", "rdw", "alp", "wbc"]
PRIMARY = {"grimage2": "GrimAge2Mort", "dunedinpoam": "DunedinPoAm"}
SECONDARY = {"horvath": "HorvathAge", "hannum": "HannumAge", "dnam_phenoage": "PhenoAge",
             "telomere": "HorvathTelo"}
RIDGES = [0.01, 0.1, 1.0, 3.0, 10.0, 30.0, 100.0]
N_BOOT = 2000


def xpt(name):
    return pd.read_sas(os.path.join(DATA, name + ".xpt"), format="xport")


def build():
    cycles = [
        ("1999-2000", "DEMO", "LAB18", "LAB11", "LAB25", "BPX",
         {"LBXSAL": "alb", "LBXSCR": "cr", "LBXSGL": "glu", "LBXSAPSI": "alp"}),
        ("2001-2002", "DEMO_B", "L40_B", "L11_B", "L25_B", "BPX_B",
         {"LBXSAL": "alb", "LBDSCR": "cr", "LBXSGL": "glu", "LBDSAPSI": "alp"}),
    ]
    frames = []
    for cycle, demo, bio, crp, cbc, bpx, biomap in cycles:
        d = xpt(demo)[["SEQN", "RIDAGEYR", "RIAGENDR"]]
        b = xpt(bio)[["SEQN"] + list(biomap)].rename(columns=biomap)
        c = xpt(crp)[["SEQN", "LBXCRP"]]
        h = xpt(cbc)[["SEQN", "LBXWBCSI", "LBXLYPCT", "LBXMCVSI", "LBXRDW"]]
        p = xpt(bpx)[["SEQN", "BPXPLS"]]
        df = d.merge(b, on="SEQN").merge(c, on="SEQN").merge(h, on="SEQN").merge(p, on="SEQN", how="left")
        df = df.dropna(subset=["alb", "cr", "glu", "alp", "LBXCRP", "LBXWBCSI", "LBXLYPCT", "LBXMCVSI", "LBXRDW"])
        df = df[df.LBXCRP > 0]
        frames.append(pd.DataFrame({
            "SEQN": df.SEQN.astype(int), "cycle": cycle, "age": df.RIDAGEYR,
            "sex": np.where(df.RIAGENDR == 1, "male", "female"),
            "albumin": df.alb * 10, "creatinine": df.cr * 88.42, "glucose": df.glu / 18.016,
            "crp": df.LBXCRP, "lymphocyte_pct": df.LBXLYPCT, "mcv": df.LBXMCVSI,
            "rdw": df.LBXRDW, "alp": df.alp, "wbc": df.LBXWBCSI, "pulse": df.BPXPLS}))
    df = pd.concat(frames, ignore_index=True)
    dna = pd.read_sas(os.path.join(DATA, "dnmepi.sas7bdat"))
    dna["SEQN"] = dna.SEQN.astype(int)
    cols = list(PRIMARY.values()) + list(SECONDARY.values())
    dna = dna.dropna(subset=cols)[["SEQN"] + cols]
    df = df.merge(dna, on="SEQN")
    df = df[(df.age >= 50) & (df.age <= 84)]     # 85 means "85 or older" in 1999-2002
    df["phenoage"] = [phenoage_from_canonical(a, r).phenoage
                      for a, r in zip(df.age, df[MARKERS].to_dict("records"))]
    df.to_csv(os.path.join(DATA, "dna_age.csv"), index=False)
    print("wrote dna_age.csv: %d adults aged %d-%d" % (len(df), df.age.min(), df.age.max()))


def load():
    df = pd.read_csv(os.path.join(DATA, "dna_age.csv"))
    df["ln_crp"] = np.log(df.crp)
    return df.reset_index(drop=True)


def lock():
    if os.path.exists(LOCK):
        sys.exit("already locked")
    df = load()
    rng = np.random.default_rng(1999)
    df["stratum"] = df.sex + (df.age // 10).astype(int).astype(str)
    test = []
    for _, g in df.groupby("stratum"):
        test.extend(rng.choice(g.SEQN.to_numpy(), int(round(0.3 * len(g))), replace=False).tolist())
    open(LOCK, "w").write("\n".join(str(int(s)) for s in sorted(test)) + "\n")
    print("locked %d of %d; sha256 %s" % (len(test), len(df),
                                         hashlib.sha256(open(LOCK, "rb").read()).hexdigest()))


def split():
    df = load()
    ids = set(int(x) for x in open(LOCK).read().split())
    m = df.SEQN.isin(ids)
    return df[~m].reset_index(drop=True), df[m].reset_index(drop=True)


# ------------------------------------------------------------------ models
class AgeResid:
    """Residual of a column on age, with the line fitted on training rows."""

    def __init__(self, train, col):
        self.col = col
        self.slope, self.icpt = np.polyfit(train.age, train[col], 1)

    def __call__(self, df):
        return (df[self.col] - (self.icpt + self.slope * df.age)).to_numpy()


def X_of(df, with_pulse):
    cols = ["age"] + [("ln_crp" if m == "crp" else m) for m in MARKERS] + (["pulse"] if with_pulse else [])
    return df[cols].to_numpy(float)


class Ridge:
    def __init__(self, lam):
        self.lam = lam

    def fit(self, X, y):
        self.mu, self.sd = X.mean(0), X.std(0)
        Z = (X - self.mu) / self.sd
        n, p = Z.shape
        self.beta = np.linalg.solve(Z.T @ Z / n + self.lam / n * np.eye(p), Z.T @ (y - y.mean()) / n)
        self.y0 = y.mean()
        return self

    def predict(self, X):
        return self.y0 + ((X - self.mu) / self.sd) @ self.beta


def corr(a, b):
    return float(np.corrcoef(a, b)[0, 1])


def score_resid(train, test, target_col, model):
    """Fit `model` ('S0', 'S1', 'S2') on train, return age-independent test scores."""
    if model == "S0":
        return AgeResid(train, "phenoage")(test)
    with_pulse = model == "S2"
    lam = model_lams[target_col][model]
    y = AgeResid(train, target_col)(train)
    r = Ridge(lam).fit(X_of(train, with_pulse), y)
    s_tr, s_te = r.predict(X_of(train, with_pulse)), r.predict(X_of(test, with_pulse))
    slope, icpt = np.polyfit(train.age, s_tr, 1)
    return s_te - (icpt + slope * test.age.to_numpy())


model_lams = {}


def choose_lams(train, target_col):
    out = {}
    for model, with_pulse in (("S1", False), ("S2", True)):
        df = train.dropna(subset=["pulse"]).reset_index(drop=True) if with_pulse else train
        folds = np.random.default_rng(5).permutation(len(df)) % 5
        best = {}
        for lam in RIDGES:
            pred = np.zeros(len(df))
            for k in range(5):
                tr, te = df[folds != k], df[folds == k]
                y = AgeResid(tr, target_col)(tr)
                pred[folds == k] = Ridge(lam).fit(X_of(tr, with_pulse), y).predict(X_of(te, with_pulse))
            best[lam] = corr(pred, AgeResid(df, target_col)(df))
        out[model] = {"chosen": max(best, key=best.get), "cv_r": {str(k): v for k, v in best.items()}}
    return out


def run_cv():
    train, _ = split()
    log = {"n_train": len(train), "targets": {}}
    for name, col in {**PRIMARY, **SECONDARY}.items():
        log["targets"][name] = choose_lams(train, col)
        print(name, {m: v["chosen"] for m, v in log["targets"][name].items()})
    json.dump(log, open(CV_OUT, "w"), indent=2)


def run_test():
    if os.path.exists(TEST_OUT):
        sys.exit("already tested")
    cv = json.load(open(CV_OUT))
    train, test = split()
    for name, col in {**PRIMARY, **SECONDARY}.items():
        model_lams[col] = {m: v["chosen"] for m, v in cv["targets"][name].items()}
    rng = np.random.default_rng(2002)
    res = {"n_train": len(train), "n_test": len(test), "targets": {}}
    for name, col in {**PRIMARY, **SECONDARY}.items():
        y = AgeResid(train, col)(test)
        s0 = score_resid(train, test, col, "S0")
        s1 = score_resid(train, test, col, "S1")
        tp = test.dropna(subset=["pulse"]).reset_index(drop=True)
        trp = train.dropna(subset=["pulse"]).reset_index(drop=True)
        s2 = score_resid(trp, tp, col, "S2")
        r0, r1 = corr(s0, y), corr(s1, y)
        idx = np.arange(len(y))
        deltas = []
        for _ in range(N_BOOT):
            s = rng.choice(idx, len(idx))
            deltas.append(corr(s1[s], y[s]) - corr(s0[s], y[s]))
        entry = {"r_S0_phenoage": r0, "r_S1_refit": r1,
                 "r_S2_refit_pulse": corr(s2, AgeResid(train, col)(tp)), "n_S2": len(tp),
                 "delta_S1_minus_S0": r1 - r0,
                 "delta_ci": [float(x) for x in np.percentile(deltas, [2.5, 97.5])],
                 "primary": name in PRIMARY}
        entry["success"] = entry["primary"] and (entry["delta_ci"][0] > 0 or entry["delta_ci"][1] < 0)
        # Final refit on all training rows, for reporting which markers drive it
        lam = model_lams[col]["S1"]
        rg = Ridge(lam).fit(X_of(train, False), AgeResid(train, col)(train))
        names = ["age"] + MARKERS
        entry["refit_std_coefs"] = {n: float(b) for n, b in zip(names, rg.beta)}
        res["targets"][name] = entry
        print("%-14s r PhenoAge %.3f  refit %.3f  refit+pulse %.3f  delta %+.3f (%+.3f to %+.3f)" % (
            name, r0, r1, entry["r_S2_refit_pulse"], r1 - r0, *entry["delta_ci"]))
    json.dump(res, open(TEST_OUT, "w"), indent=2)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    {"build": build, "lock": lock, "cv": run_cv, "test": run_test}.get(cmd, lambda: sys.exit(__doc__))()
