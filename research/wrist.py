"""Wrist study: NHANES 2011-2014, 24-hour wrist accelerometry (pre-registered
in research/RESULTS.md section 5).

    .venv-research/bin/python research/wrist.py build    # research/data/wrist.csv
    .venv-research/bin/python research/wrist.py lock     # once: research/locked_test_wrist.txt
    .venv-research/bin/python research/wrist.py cv       # 70% only -> research/wrist_cv.json
    .venv-research/bin/python research/wrist.py test     # once -> research/wrist_test.json
    .venv-research/bin/python research/wrist.py report   # section 6 of RESULTS.md
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

from ladder import (Accel, boot_delta, c_index, fit_gompertz, km_risk, lin,  # noqa: E402
                    mort, truncate)
from phenoage.core import phenoage_from_canonical  # noqa: E402
from phenoage.explain import REFERENCE_PROFILE  # noqa: E402

CYCLES = {"2011-2012": "G", "2013-2014": "H"}
MORT = {"2011-2012": "NHANES_2011_2012_MORT_2019_PUBLIC.dat",
        "2013-2014": "NHANES_2013_2014_MORT_2019_PUBLIC.dat"}
LOCK = os.path.join(HERE, "locked_test_wrist.txt")
CV_OUT = os.path.join(HERE, "wrist_cv.json")
TEST_OUT = os.path.join(HERE, "wrist_test.json")
MARKERS8 = ["albumin", "creatinine", "glucose", "lymphocyte_pct", "mcv", "rdw", "alp", "wbc"]
VALID_WEAR_MIN = 960
MIN_DAYS = 4
HORIZON = 60
N_BOOT = 200
MIN_GAIN = 0.003


def xpt(name):
    return pd.read_sas(os.path.join(DATA, name + ".xpt"), format="xport")


def mortality(name):
    df = pd.read_fwf(os.path.join(DATA, name), header=None,
                     colspecs=[(0, 14), (14, 15), (15, 16), (45, 48)],
                     names=["SEQN", "eligstat", "mortstat", "permth_exm"],
                     na_values=["."], dtype=str)
    for c in df.columns:
        df[c] = pd.to_numeric(df[c].str.strip(), errors="coerce")
    return df


def to_text(s):
    return s.str.decode("utf-8") if s.dtype == object and isinstance(s.iloc[0], bytes) else s


# ------------------------------------------------------------------ build
def blood(cycle, s):
    demo = xpt("DEMO_" + s)[["SEQN", "RIDAGEYR", "RIAGENDR"]]
    bio = xpt("BIOPRO_" + s)[["SEQN", "LBXSAL", "LBXSCR", "LBXSGL", "LBXSAPSI"]]
    cbc = xpt("CBC_" + s)[["SEQN", "LBXWBCSI", "LBXLYPCT", "LBXMCVSI", "LBXRDW"]]
    bpx = xpt("BPX_" + s)[["SEQN", "BPXPLS"]]
    df = demo.merge(bio, on="SEQN").merge(cbc, on="SEQN").merge(bpx, on="SEQN", how="left")
    df = df[(df.RIDAGEYR >= 20) & (df.RIDAGEYR <= 79)]     # 80 means "80 or older" in 2011-14
    df = df.dropna(subset=["LBXSAL", "LBXSCR", "LBXSGL", "LBXSAPSI",
                           "LBXWBCSI", "LBXLYPCT", "LBXMCVSI", "LBXRDW"])
    out = pd.DataFrame({
        "SEQN": df.SEQN.astype(int), "cycle": cycle, "age": df.RIDAGEYR,
        "sex": np.where(df.RIAGENDR == 1, "male", "female"),
        "albumin": df.LBXSAL * 10, "creatinine": df.LBXSCR * 88.42,
        "glucose": df.LBXSGL / 18.016, "lymphocyte_pct": df.LBXLYPCT,
        "mcv": df.LBXMCVSI, "rdw": df.LBXRDW, "alp": df.LBXSAPSI, "wbc": df.LBXWBCSI,
        "pulse": df.BPXPLS,
    })
    rows = out[MARKERS8].to_dict("records")
    crp_ref = REFERENCE_PROFILE["crp"]
    out["phenoage"] = [phenoage_from_canonical(a, dict(r, crp=crp_ref)).phenoage
                       for a, r in zip(out.age, rows)]
    return out


def daily_features(s):
    d = xpt("PAXDAY_" + s)
    d["wear"] = d.PAXWWMD + d.PAXSWMD
    valid = d[(d.PAXTMD == 1440) & (d.wear >= VALID_WEAR_MIN)]
    g = valid.groupby("SEQN")
    out = pd.DataFrame({
        "valid_days": g.size(),
        "mims_per_day": g.PAXMTSD.mean(),
        "sleep_min": g.PAXSWMD.mean(),
        "sleep_sd": g.PAXSWMD.std(),
        "wake_wear_min": g.PAXWWMD.mean(),
    })
    valid_keys = set(zip(valid.SEQN, to_text(valid.PAXDAYD).astype(int)))
    return out.reset_index(), valid_keys


def hourly_features(s, valid_keys):
    h = xpt("PAXHR_" + s)
    h["day"] = to_text(h.PAXDAYH).astype(int)
    # Clock hour = monitor start time (PAXHD) + samples since start / 80 Hz
    hd = xpt("PAXHD_" + s)[["SEQN", "PAXFTIME"]]
    hms = to_text(hd.PAXFTIME).str.strip().str.split(":", expand=True)
    hms = hms.apply(pd.to_numeric, errors="coerce")
    hd["start_s"] = hms[0] * 3600 + hms[1] * 60 + hms[2]
    hd = hd.dropna(subset=["start_s"])
    h = h.merge(hd[["SEQN", "start_s"]], on="SEQN")
    h["hour"] = (((h.start_s + h.PAXSSNHP / 80) // 3600) % 24).astype(int)
    keep = [k in valid_keys for k in zip(h.SEQN, h.day)]
    h = h[keep]
    rows = []
    for seqn, g in h.groupby("SEQN", sort=False):
        g = g.sort_values(["day", "hour"])
        x = g.PAXMTSH.to_numpy(float)
        hours = g.hour.to_numpy()
        prof = np.array([x[hours == k].mean() if (hours == k).any() else np.nan for k in range(24)])
        r = {"SEQN": int(seqn)}
        if not np.isnan(prof).any() and len(x) >= 96:
            ext = np.concatenate([prof, prof])
            l5 = min(ext[i:i + 5].mean() for i in range(24))
            m10 = max(ext[i:i + 10].mean() for i in range(24))
            mean, var = x.mean(), ((x - x.mean()) ** 2).sum()
            n = len(x)
            r.update({"ra": (m10 - l5) / (m10 + l5),
                      "is": n * ((prof - mean) ** 2).sum() / (24 * var),
                      "iv": n * (np.diff(x) ** 2).sum() / ((n - 1) * var)})
        # Sleep midpoint per noon-to-noon night, weighted by sleep minutes
        t = (g.day.to_numpy() - 1) * 24 + hours + 0.5          # hours since day 1 midnight
        night = np.floor((t - 12) / 24)
        sleep = g.PAXSWMH.to_numpy(float)
        mids = []
        for k in np.unique(night):
            m = night == k
            if sleep[m].sum() >= 120:
                mids.append(((t[m] - 12) % 24 * sleep[m]).sum() / sleep[m].sum() + 12)
        if len(mids) >= 3:
            r["sleep_mid"] = float(np.mean(mids))      # noon-to-noon clock: 24 = midnight, 27.5 = 03:30
            r["sleep_mid_sd"] = float(np.std(mids, ddof=1))
        rows.append(r)
    return pd.DataFrame(rows)


def build():
    frames = []
    for cycle, s in CYCLES.items():
        print(cycle, flush=True)
        df = blood(cycle, s).merge(mortality(MORT[cycle]), on="SEQN", how="left")
        df = df[df.eligstat == 1].dropna(subset=["mortstat", "permth_exm"])
        daily, keys = daily_features(s)
        df = df.merge(daily, on="SEQN", how="inner")
        df = df[df.valid_days >= MIN_DAYS]
        hourly = hourly_features(s, {k for k in keys if k[0] in set(df.SEQN)})
        df = df.merge(hourly, on="SEQN", how="left")
        print("  %d adults, %d deaths" % (len(df), (df.mortstat == 1).sum()), flush=True)
        frames.append(df)
    out = pd.concat(frames, ignore_index=True)
    out.to_csv(os.path.join(DATA, "wrist.csv"), index=False)
    print("wrote wrist.csv (%d rows)" % len(out))


# ------------------------------------------------------------------ analysis
FEATURES = {
    "W1": ["log_mims"],
    "W2": ["sleep_h", "sleep_h2"],
    "W3": ["sleep_sd", "mid_c", "sleep_mid_sd"],
    "W4": ["is", "iv", "ra"],
    "W5": ["pulse"],
}
ALL_WRIST = FEATURES["W1"] + FEATURES["W2"] + FEATURES["W3"] + FEATURES["W4"]
CANDIDATES = [
    ("B0 Blood: age + PhenoAge (CRP at reference)", ["accel"], "gompertz"),
    ("B1 Blood: ridge refit of 8 markers", ["markers"], "ridge"),
    ("W5 + exam pulse", ["accel"] + FEATURES["W5"], "gompertz"),
    ("W1 + daily wrist activity volume (MIMS)", ["accel"] + FEATURES["W1"], "gompertz"),
    ("W2 + sleep duration", ["accel"] + FEATURES["W2"], "gompertz"),
    ("W3 + sleep regularity and midpoint", ["accel"] + FEATURES["W3"], "gompertz"),
    ("W4 + rest-activity rhythm", ["accel"] + FEATURES["W4"], "gompertz"),
    ("W6 + MIMS + sleep duration + pulse", ["accel"] + FEATURES["W1"] + FEATURES["W2"] + FEATURES["W5"], "gompertz"),
    ("W7 + all wrist features + pulse (ridge)", ["accel"] + ALL_WRIST + FEATURES["W5"], "ridge"),
    ("W8 Ridge refit: 8 markers + all wrist + pulse", ["markers"] + ALL_WRIST + FEATURES["W5"], "ridge"),
]
ORDER = [c[0] for c in CANDIDATES[2:]]
BASE = CANDIDATES[0][0]
RIDGES = [0.0, 0.001, 0.003, 0.01, 0.03]
CAPS = [0, 1, 2.5, 5]


def load():
    df = pd.read_csv(os.path.join(DATA, "wrist.csv"))
    df = df[df.permth_exm > 0].copy()
    df["t"] = df.permth_exm.astype(float)
    df["d"] = (df.mortstat == 1).astype(int)
    df["log_mims"] = np.log(df.mims_per_day)
    df["sleep_h"] = df.sleep_min / 60
    df["sleep_h2"] = (df.sleep_h - 7.5) ** 2
    df["mid_c"] = (df.sleep_mid - 27.5) ** 2     # squared distance from a 03:30 midpoint
    return df.reset_index(drop=True)


def need(cols):
    return [c for c in cols if c not in ("accel", "markers")]


def design(df, accel, cols):
    X = pd.DataFrame({"age": df.age})
    for c in cols:
        if c == "accel":
            X["accel"] = accel(df)
        elif c == "markers":
            for m in MARKERS8:
                X[m] = df[m]
        else:
            X[c] = df[c]
    return X.to_numpy(float)


def c5(r, t, d):
    return c_index(r, *truncate(t, d, HORIZON))


def fit_predict(tr, te, cols, kind, cap, ridge):
    accel = Accel(tr, cap)
    m = fit_gompertz(design(tr, accel, cols), tr.t.to_numpy(), tr.d.to_numpy(),
                     ridge if kind == "ridge" else 0.0)
    X = design(te, accel, cols)
    return lin(m, X), m, X


def oof(df, cols, kind, cap, ridge, seed):
    folds = np.random.default_rng(seed).permutation(len(df)) % 5
    r = np.zeros(len(df))
    for k in range(5):
        tr, te = df[folds != k].reset_index(drop=True), df[folds == k].reset_index(drop=True)
        r[folds == k] = fit_predict(tr, te, cols, kind, cap, ridge)[0]
    return r


def lock():
    if os.path.exists(LOCK):
        sys.exit("already locked")
    df = load()
    rng = np.random.default_rng(20261105)
    test = []
    for dead in (0, 1):
        ids = df.SEQN[df.d == dead].to_numpy()
        test.extend(rng.choice(ids, int(round(0.3 * len(ids))), replace=False).tolist())
    open(LOCK, "w").write("\n".join(str(int(s)) for s in sorted(test)) + "\n")
    print("locked %d of %d; sha256 %s" % (len(test), len(df),
                                         hashlib.sha256(open(LOCK, "rb").read()).hexdigest()))


def split():
    df = load()
    ids = set(int(x) for x in open(LOCK).read().split())
    m = df.SEQN.astype(int).isin(ids)
    return df[~m].reset_index(drop=True), df[m].reset_index(drop=True)


def run_cv():
    train, _ = split()
    rng = np.random.default_rng(7)
    log = {"n_train": len(train), "deaths_5y_train": int(((train.d == 1) & (train.t <= HORIZON)).sum()),
           "models": {}, "choices": {}}
    base = train
    cap_c = {cap: c5(oof(base, ["accel"], "gompertz", cap, 0, 1), base.t.to_numpy(), base.d.to_numpy())
             for cap in CAPS}
    cap = max(cap_c, key=cap_c.get)
    log["choices"]["accel_cap_percent"] = {"tried": {str(k): v for k, v in cap_c.items()}, "chosen": cap}
    risks = {}
    for name, cols, kind in CANDIDATES:
        df = train.dropna(subset=need(cols)).reset_index(drop=True)
        t, d = df.t.to_numpy(), df.d.to_numpy()
        ridge = 0.0
        if kind == "ridge":
            rc = {r: c5(oof(df, cols, kind, cap, r, 3), t, d) for r in RIDGES}
            ridge = max(rc, key=rc.get)
        r = oof(df, cols, kind, cap, ridge, 5)
        r0 = oof(df, ["accel"], "gompertz", cap, 0, 5)
        e = {"inputs": cols, "kind": kind, "ridge": ridge, "n": len(df),
             "deaths_5y": int(((d == 1) & (t <= HORIZON)).sum()),
             "c5": c5(r, t, d), "c5_base_same_rows": c5(r0, t, d)}
        e["delta"] = e["c5"] - e["c5_base_same_rows"]
        e["delta_ci"] = boot_delta(r0, r, t, d, rng, fn=c5)
        log["models"][name] = e
        risks[name] = (df.SEQN.to_numpy(), r)
        print("%-48s n%5d C5 %.4f vs %.4f  delta %+.4f (%+.4f to %+.4f)" % (
            name, e["n"], e["c5"], e["c5_base_same_rows"], e["delta"], *e["delta_ci"]), flush=True)
    chosen, steps = BASE, []
    for name in ORDER:
        if chosen == BASE:
            gain, ci = log["models"][name]["delta"], log["models"][name]["delta_ci"]
        else:
            s0, r0 = risks[chosen]
            s1, r1 = risks[name]
            common = np.intersect1d(s0, s1)
            a = pd.Series(r0, index=s0).loc[common].to_numpy()
            b = pd.Series(r1, index=s1).loc[common].to_numpy()
            sub = train.set_index("SEQN").loc[common]
            t, d = sub.t.to_numpy(), sub.d.to_numpy()
            gain = c5(b, t, d) - c5(a, t, d)
            ci = boot_delta(a, b, t, d, rng, fn=c5)
        ok = gain >= MIN_GAIN and ci[0] > 0
        steps.append({"candidate": name, "vs": chosen, "gain": gain, "ci": ci, "accepted": bool(ok)})
        if ok:
            chosen = name
    log["choices"]["deploy_steps"] = steps
    log["choices"]["deployed_model"] = chosen
    json.dump(log, open(CV_OUT, "w"), indent=2, default=float)
    print("deployed (CV):", chosen)


def run_test():
    log = json.load(open(CV_OUT))
    train, test = split()
    cap = log["choices"]["accel_cap_percent"]["chosen"]
    rng = np.random.default_rng(11)
    res = {"n_test": len(test), "deaths_5y_test": int(((test.d == 1) & (test.t <= HORIZON)).sum()),
           "models": {}, "deployed_model": log["choices"]["deployed_model"]}
    for name, cols, kind in CANDIDATES:
        e = log["models"][name]
        tr = train.dropna(subset=need(cols)).reset_index(drop=True)
        te = test.dropna(subset=need(cols)).reset_index(drop=True)
        r, m, X = fit_predict(tr, te, cols, kind, cap, e["ridge"])
        r0, _, _ = fit_predict(tr, te, ["accel"], "gompertz", cap, 0)
        t, d = te.t.to_numpy(), te.d.to_numpy()
        p = mort(m, X, HORIZON)
        out = {"n": len(te), "c5": c5(r, t, d), "c5_base": c5(r0, t, d),
               "mean_predicted_5y": float(p.mean()), "observed_5y_km": float(km_risk(t, d, HORIZON)),
               "calibration_slope": float(fit_gompertz(r[:, None], t, d)["b"][0])}
        out["delta"] = out["c5"] - out["c5_base"]
        out["delta_ci"] = boot_delta(r0, r, t, d, rng, fn=c5)
        res["models"][name] = out
        print("%-48s test C5 %.4f vs %.4f  delta %+.4f (%+.4f to %+.4f)" % (
            name, out["c5"], out["c5_base"], out["delta"], *out["delta_ci"]), flush=True)
    json.dump(res, open(TEST_OUT, "w"), indent=2, default=float)


MAPPING = [
    ("Daily activity volume", "PAXMTSD, daily sum of MIMS units (wrist GT3X+)",
     "Consumer bands do not report MIMS; they report steps, \"active minutes\" or proprietary "
     "scores. Open-source MIMS can be computed from raw band acceleration where a band exports "
     "it (few do). No validated conversion from band steps to MIMS. High uncertainty."),
    ("Sleep duration", "PAXSWMD, minutes classified as sleep wear by the NHANES algorithm",
     "Bands report sleep time from their own algorithms (often heart rate + motion); they "
     "typically differ from actigraphy by tens of minutes a night. Moderate uncertainty."),
    ("Sleep midpoint and regularity", "from hourly sleep-wear minutes (PAXHR), noon-to-noon nights",
     "Bands report bedtime and wake time, so midpoint and its night-to-night SD are directly "
     "computable; hourly resolution here limits precision to about 30 minutes. Moderate uncertainty."),
    ("Rest-activity rhythm (IS, IV, RA)", "from hourly MIMS (PAXHR)",
     "Computable from any band's hourly step or activity counts, but values depend on the "
     "activity measure used. Moderate to high uncertainty."),
    ("Resting heart rate", "BPXPLS, 60-second seated exam pulse",
     "Band resting HR is lower than a seated clinic pulse; no conversion fitted. Moderate uncertainty."),
]


def report():
    cv, te = json.load(open(CV_OUT)), json.load(open(TEST_OUT))
    sha = hashlib.sha256(open(LOCK, "rb").read()).hexdigest()
    L = []
    o = L.append
    f = lambda x, ci: "%+.4f (%+.4f to %+.4f)" % (x, ci[0], ci[1])  # noqa: E731
    o("## 6. Wrist study results, NHANES 2011-2014")
    o("")
    o("Test set: %d of %d adults (%d deaths within 5 years), SHA-256 `%s`, locked in commit "
      "63ca11d before any model was fitted. Training: %d adults (%d deaths within 5 years). "
      "PhenoAge acceleration cap chosen in CV: %s/%s percentiles."
      % (te["n_test"], te["n_test"] + cv["n_train"], te["deaths_5y_test"], sha, cv["n_train"],
         cv["deaths_5y_train"], cv["choices"]["accel_cap_percent"]["chosen"],
         100 - cv["choices"]["accel_cap_percent"]["chosen"]))
    o("")
    o("| Model | CV n | CV change in 5-y C | Test n | Test change in 5-y C | Test calibration slope | Test predicted / observed 5-y mortality |")
    o("|---|---|---|---|---|---|---|")
    for name, *_ in CANDIDATES:
        c, t = cv["models"][name], te["models"][name]
        o("| %s | %d | %s | %d | %s | %.2f | %.1f%% / %.1f%% |" % (
            name, c["n"], f(c["delta"], c["delta_ci"]), t["n"], f(t["delta"], t["delta_ci"]),
            t["calibration_slope"], 100 * t["mean_predicted_5y"], 100 * t["observed_5y_km"]))
    o("")
    o("Blood baseline 5-year C: %.4f in CV, %.4f on the test set. Changes are against the "
      "blood baseline refitted on the same people." % (
          cv["models"][BASE]["c5"], te["models"][BASE]["c5"]))
    o("")
    o("**Deployment decision (CV only):**")
    o("")
    for s in cv["choices"]["deploy_steps"]:
        o("- %s vs %s: %s → %s" % (s["candidate"], s["vs"], f(s["gain"], s["ci"]),
                                  "accepted" if s["accepted"] else "rejected"))
    dep = cv["choices"]["deployed_model"]
    t = te["models"][dep]
    o("")
    o("Deployed: **%s**. Locked test: %s." % (dep, f(t["delta"], t["delta_ci"])))
    o("")
    if t["delta_ci"][0] > 0:
        o("**Verdict: the deployed model beats the blood baseline on the locked test set.**")
    else:
        o("**Verdict: no combined VitalAge is shipped.** The model chosen in cross-validation "
          "did not beat the blood baseline on the locked test set; its 95%% CI includes zero. "
          "With %d deaths within 5 years the test set has limited power, so small real "
          "gains cannot be ruled out." % te["deaths_5y_test"])
    o("")
    o("**A pattern across both studies (hypothesis, not a result).** Penalised refits of the "
      "blood markers did better on both locked test sets than in cross-validation: in "
      "2003-2006, R3b (+0.0058) and D7 (+0.0165); here B1 (%s) and W8 (%s). They were not "
      "chosen by the pre-registered rules, so they are not shipped. A future study could "
      "pre-register a marker refit as the primary candidate and test it on fresh data "
      "(for example NHANES 2015-2018, which has hs-CRP)." % (
          f(te["models"][CANDIDATES[1][0]]["delta"], te["models"][CANDIDATES[1][0]]["delta_ci"]),
          f(te["models"][CANDIDATES[-1][0]]["delta"], te["models"][CANDIDATES[-1][0]]["delta_ci"])))
    o("")
    o("**CRP.** Fixing CRP at the reference value shifts every PhenoAge by the same amount, so "
      "the CRP sensitivity analysis at 0.2 or 10 mg/L leaves every C-index above unchanged; "
      "only the PhenoAge level (calibration) would move.")
    o("")
    o("### How wrist features map to consumer bands")
    o("")
    o("| Feature | NHANES variable | Mapping and uncertainty |")
    o("|---|---|---|")
    for a, b, c in MAPPING:
        o("| %s | %s | %s |" % (a, b, c))
    o("")
    o("Minutes of moderate-to-vigorous activity could not be computed: the hourly and daily "
      "files have no minute-level intensities, and the minute files were not downloaded.")
    text = "\n".join(L) + "\n"
    path = os.path.join(HERE, "RESULTS.md")
    body = open(path).read()
    marker = "## 6. Wrist study results, NHANES 2011-2014"
    if marker in body:
        body = body[:body.index(marker)].rstrip() + "\n"
    open(path, "w").write(body + "\n" + text)
    print(text)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    {"build": build, "lock": lock, "cv": run_cv, "test": run_test,
     "report": report}.get(cmd, lambda: sys.exit(__doc__))()
