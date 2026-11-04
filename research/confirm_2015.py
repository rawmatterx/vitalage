"""Confirmatory test of the marker-refit lead on NHANES 2015-2018.

    .venv-research/bin/python research/confirm_2015.py freeze   # 2003-06 only -> frozen JSON
    .venv-research/bin/python research/confirm_2015.py test     # once, on 2015-18
    .venv-research/bin/python research/confirm_2015.py report   # section 8 of RESULTS.md

`freeze` fits both models on NHANES 2003-2006 alone and writes
research/frozen_refit_2003_06.json, which is committed (with its SHA-256)
before any 2015-2018 file is downloaded:
- refit (R3b): Gompertz proportional hazards on age + the 9 PhenoAge markers
  (CRP as ln mg/dL), ridge penalty on standardized slopes chosen by 5-fold
  CV on Harrell's C over full follow-up;
- comparator: Gompertz on age + PhenoAge acceleration, acceleration = PhenoAge
  minus its linear trend on age in 2003-06, capped at its 2.5th/97.5th
  percentiles (the cap rule chosen by CV in the 2003-06 ladder).
Nothing is fitted on 2015-2018: every person there is test data.
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
sys.path.insert(0, HERE)

from ladder import c_index, fit_gompertz, km_risk  # noqa: E402
from phenoage.core import phenoage_from_canonical  # noqa: E402

FROZEN = os.path.join(HERE, "frozen_refit_2003_06.json")
TEST_OUT = os.path.join(HERE, "confirm_2015_test.json")
MARKERS = ["albumin", "creatinine", "glucose", "crp", "lymphocyte_pct", "mcv", "rdw", "alp", "wbc"]
FEATURES = ["age"] + MARKERS                       # crp enters as ln(mg/dL)
RIDGES = [0.0, 0.001, 0.003, 0.01, 0.03, 0.1]
CAP = 2.5
CAL_MONTHS = 24
N_BOOT = 2000
CYCLES = {"2015-2016": ("I", "NHANES_2015_2016_MORT_2019_PUBLIC.dat"),
          "2017-2018": ("J", "NHANES_2017_2018_MORT_2019_PUBLIC.dat")}


def X_of(df):
    X = df[FEATURES].astype(float).copy()
    X["crp"] = np.log(df.crp)
    return X.to_numpy()


def risk(model, X):
    return model["a"] + X @ np.asarray(model["b"])


def freeze():
    if os.path.exists(FROZEN):
        sys.exit("Already frozen: %s" % FROZEN)
    df = pd.read_csv(os.path.join(DATA, "analysis.csv"))
    df = df[df.permth_exm > 0].reset_index(drop=True)
    t, d = df.permth_exm.to_numpy(float), (df.mortstat == 1).to_numpy(int)
    X = X_of(df)

    folds = np.random.default_rng(2015).permutation(len(df)) % 5
    cv = {}
    for lam in RIDGES:
        r = np.zeros(len(df))
        for k in range(5):
            m = fit_gompertz(X[folds != k], t[folds != k], d[folds != k], lam)
            r[folds == k] = risk(m, X[folds == k])
        cv[lam] = c_index(r, t, d)
    lam = max(cv, key=cv.get)
    refit = fit_gompertz(X, t, d, lam)

    slope, icpt = np.polyfit(df.age, df.phenoage, 1)
    raw = df.phenoage - (icpt + slope * df.age)
    lo, hi = np.percentile(raw, [CAP, 100 - CAP])
    comp = fit_gompertz(np.column_stack([df.age, raw.clip(lo, hi)]), t, d)

    out = {
        "trained_on": "NHANES 2003-2004 and 2005-2006, adults 20-84 with all 9 markers, "
                      "NCHS linked mortality to 31 Dec 2019",
        "n": int(len(df)), "deaths": int(d.sum()),
        "refit": {"features": FEATURES, "crp_scale": "ln(mg/dL)",
                  "marker_units": {"albumin": "g/L", "creatinine": "umol/L", "glucose": "mmol/L",
                                   "crp": "mg/dL", "lymphocyte_pct": "%", "mcv": "fL",
                                   "rdw": "%", "alp": "U/L", "wbc": "10^3/uL"},
                  "ridge": lam, "ridge_cv_c": {str(k): v for k, v in cv.items()},
                  "a": float(refit["a"]), "b": [float(x) for x in refit["b"]],
                  "gamma_per_month": float(refit["g"])},
        "comparator": {"features": ["age", "pheno_accel"],
                       "accel_trend": {"intercept": float(icpt), "slope": float(slope)},
                       "accel_cap": [float(lo), float(hi)],
                       "a": float(comp["a"]), "b": [float(x) for x in comp["b"]],
                       "gamma_per_month": float(comp["g"])},
        "primary_test": "Harrell's C over all available follow-up in NHANES 2015-2018 "
                        "(ages 20-79), refit minus comparator, paired bootstrap 95%% CI "
                        "(%d resamples); success = CI excludes zero." % N_BOOT,
    }
    json.dump(out, open(FROZEN, "w"), indent=2)
    print(json.dumps(out, indent=2))
    print("sha256", hashlib.sha256(open(FROZEN, "rb").read()).hexdigest())


def xpt(name):
    return pd.read_sas(os.path.join(DATA, name + ".xpt"), format="xport")


def mortality(name):
    df = pd.read_fwf(os.path.join(DATA, name), header=None,
                     colspecs=[(0, 14), (14, 15), (15, 16), (45, 48)],
                     names=["SEQN", "eligstat", "mortstat", "permth_exm"], na_values=["."], dtype=str)
    for c in df.columns:
        df[c] = pd.to_numeric(df[c].str.strip(), errors="coerce")
    return df


def load_2015():
    frames = []
    for cycle, (s, mort) in CYCLES.items():
        demo = xpt("DEMO_" + s)[["SEQN", "RIDAGEYR"]]
        bio = xpt("BIOPRO_" + s)[["SEQN", "LBXSAL", "LBXSCR", "LBXSGL", "LBXSAPSI"]]
        cbc = xpt("CBC_" + s)[["SEQN", "LBXWBCSI", "LBXLYPCT", "LBXMCVSI", "LBXRDW"]]
        crp = xpt("HSCRP_" + s)[["SEQN", "LBXHSCRP"]]
        df = demo.merge(bio, on="SEQN").merge(cbc, on="SEQN").merge(crp, on="SEQN").dropna()
        df = df[(df.RIDAGEYR >= 20) & (df.RIDAGEYR <= 79) & (df.LBXHSCRP > 0)]   # 80 = "80 or older"
        df = df.merge(mortality(mort), on="SEQN")
        df = df[(df.eligstat == 1) & (df.permth_exm > 0)].dropna(subset=["mortstat"])
        frames.append(pd.DataFrame({
            "SEQN": df.SEQN.astype(int), "cycle": cycle, "age": df.RIDAGEYR,
            "albumin": df.LBXSAL * 10, "creatinine": df.LBXSCR * 88.42,
            "glucose": df.LBXSGL / 18.016, "crp": df.LBXHSCRP / 10,       # mg/L -> mg/dL
            "lymphocyte_pct": df.LBXLYPCT, "mcv": df.LBXMCVSI, "rdw": df.LBXRDW,
            "alp": df.LBXSAPSI, "wbc": df.LBXWBCSI,
            "t": df.permth_exm.astype(float), "d": (df.mortstat == 1).astype(int)}))
    df = pd.concat(frames, ignore_index=True)
    df["phenoage"] = [phenoage_from_canonical(a, r).phenoage
                      for a, r in zip(df.age, df[MARKERS].to_dict("records"))]
    return df


def mort_at(a, b, g, X, months):
    return -np.expm1(-np.exp(a + X @ np.asarray(b)) * np.expm1(g * months) / g)


def test():
    if os.path.exists(TEST_OUT):
        sys.exit("The confirmatory test has already been run: %s" % TEST_OUT)
    fz = json.load(open(FROZEN))
    df = load_2015()
    t, d = df.t.to_numpy(), df.d.to_numpy()
    X = X_of(df)
    rf, cp = fz["refit"], fz["comparator"]
    r_refit = rf["a"] + X @ np.asarray(rf["b"])
    tr = cp["accel_trend"]
    accel = (df.phenoage - (tr["intercept"] + tr["slope"] * df.age)).clip(*cp["accel_cap"]).to_numpy()
    Xc = np.column_stack([df.age, accel])
    r_comp = cp["a"] + Xc @ np.asarray(cp["b"])

    c1, c0 = c_index(r_refit, t, d), c_index(r_comp, t, d)
    rng = np.random.default_rng(2015)
    idx = np.arange(len(t))
    deltas, c0s, c1s = [], [], []
    for _ in range(N_BOOT):
        s = rng.choice(idx, len(idx))
        a, b = c_index(r_comp[s], t[s], d[s]), c_index(r_refit[s], t[s], d[s])
        c0s.append(a), c1s.append(b), deltas.append(b - a)
    se = float(np.std(deltas, ddof=1))

    def calib(a, bvec, g, Xm):
        p = mort_at(a, bvec, g, Xm, CAL_MONTHS)
        q = pd.qcut(p, 5, labels=False, duplicates="drop")
        return {"mean_predicted": float(p.mean()), "observed_km": float(km_risk(t, d, CAL_MONTHS)),
                "quintiles": [{"predicted": float(p[q == k].mean()),
                               "observed": float(km_risk(t[q == k], d[q == k], CAL_MONTHS))}
                              for k in sorted(set(q))]}

    res = {
        "n": int(len(df)), "deaths": int(d.sum()),
        "deaths_by_cycle": {c: int(df.d[df.cycle == c].sum()) for c in CYCLES},
        "median_followup_months": float(np.median(t)), "max_followup_months": float(t.max()),
        "c_refit": c1, "c_comparator": c0, "c_raw_phenoage": c_index(df.phenoage.to_numpy(), t, d),
        "c_refit_ci": [float(x) for x in np.percentile(c1s, [2.5, 97.5])],
        "c_comparator_ci": [float(x) for x in np.percentile(c0s, [2.5, 97.5])],
        "delta": c1 - c0, "delta_ci": [float(x) for x in np.percentile(deltas, [2.5, 97.5])],
        "delta_se": se, "min_detectable_delta_80pct_power": 2.8 * se,
        "calibration_months": CAL_MONTHS,
        "calibration_refit": calib(rf["a"], rf["b"], rf["gamma_per_month"], X),
        "calibration_comparator": calib(cp["a"], cp["b"], cp["gamma_per_month"], Xc),
        "frozen_sha256": hashlib.sha256(open(FROZEN, "rb").read()).hexdigest(),
    }
    res["success"] = res["delta_ci"][0] > 0 or res["delta_ci"][1] < 0
    json.dump(res, open(TEST_OUT, "w"), indent=2)
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    {"freeze": freeze, "test": test}.get(cmd, lambda: sys.exit(__doc__))()
