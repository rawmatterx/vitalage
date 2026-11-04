"""Build the Phase 6 analysis file from NHANES 2003-2006.

    .venv-research/bin/python research/build_dataset.py

Reads the files fetched by fetch_nhanes.py (with PAXRAW_C/D unzipped to
paxraw_c.xpt / paxraw_d.xpt) and writes research/data/analysis.csv: one row
per adult with PhenoAge, accelerometer summaries and mortality follow-up.
No minute-level data is written.

Accelerometer processing (hip ActiGraph 7164, 1-minute epochs):
- Monitors flagged unreliable (PAXSTAT != 1) or out of calibration
  (PAXCAL != 1) are dropped.
- Non-wear: runs of 60 or more consecutive minutes with zero counts,
  following Troiano et al. 2008 but without their allowance for 1-2 minutes
  of low counts inside a run (a simplification).
- A valid day has at least 600 wear minutes (10 h); people need at least
  4 valid days.
- Features over valid days: mean counts per wear minute (cpm), minutes per
  day at >= 2020 counts/min (MVPA, Troiano 2008), and for 2005-06 mean steps
  per day, both raw and censored to minutes >= 500 counts (Tudor-Locke et
  al. 2009). Counts above 32767 are treated as missing (device ceiling).
"""

import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
sys.path.insert(0, os.path.dirname(HERE))

from phenoage.core import linear_predictor, phenoage_from_canonical  # noqa: E402

CYCLES = {
    "2003-2004": {"demo": "DEMO_C", "bio": "L40_C", "crp": "L11_C", "cbc": "L25_C",
                  "pax": "paxraw_c.xpt", "bpx": "BPX_C", "mort": "NHANES_2003_2004_MORT_2019_PUBLIC.dat"},
    "2005-2006": {"demo": "DEMO_D", "bio": "BIOPRO_D", "crp": "CRP_D", "cbc": "CBC_D",
                  "pax": "paxraw_d.xpt", "bpx": "BPX_D", "mort": "NHANES_2005_2006_MORT_2019_PUBLIC.dat"},
}

NONWEAR_RUN = 60
VALID_DAY_MIN = 600
MIN_DAYS = 4
MVPA_CPM = 2020
MAX_COUNT = 32767
CENSOR_CPM = 500
SED_CPM = 100


def xpt(name):
    return pd.read_sas(os.path.join(DATA, name + ".xpt"), format="xport")


def mortality(name):
    # NCHS 2019 public-use linked mortality layout (fixed width, 1-based):
    # SEQN 1-14, ELIGSTAT 15, MORTSTAT 16, UCOD_LEADING 17-19,
    # PERMTH_INT 43-45, PERMTH_EXM 46-48.
    df = pd.read_fwf(os.path.join(DATA, name), header=None,
                     colspecs=[(0, 14), (14, 15), (15, 16), (16, 19), (42, 45), (45, 48)],
                     names=["SEQN", "eligstat", "mortstat", "ucod", "permth_int", "permth_exm"],
                     na_values=["."], dtype=str)
    for c in df.columns:
        df[c] = pd.to_numeric(df[c].str.strip(), errors="coerce")
    return df


def blood(cycle, files):
    demo = xpt(files["demo"])[["SEQN", "RIDAGEYR", "RIAGENDR", "WTMEC2YR", "SDMVPSU", "SDMVSTRA"]]
    bio = xpt(files["bio"])[["SEQN", "LBXSAL", "LBXSCR", "LBXSGL", "LBXSAPSI"]]
    crp = xpt(files["crp"])[["SEQN", "LBXCRP"]]
    cbc = xpt(files["cbc"])[["SEQN", "LBXWBCSI", "LBXLYPCT", "LBXMCVSI", "LBXRDW"]]
    df = demo.merge(bio, on="SEQN").merge(crp, on="SEQN").merge(cbc, on="SEQN")
    df = df[(df.RIDAGEYR >= 20) & (df.RIDAGEYR <= 84)].dropna()
    df = df[df.LBXCRP > 0]
    df = pd.DataFrame({
        "SEQN": df.SEQN.astype(int), "cycle": cycle,
        "age": df.RIDAGEYR, "sex": np.where(df.RIAGENDR == 1, "male", "female"),
        "weight": df.WTMEC2YR, "psu": df.SDMVPSU, "strata": df.SDMVSTRA,
        "albumin": df.LBXSAL * 10, "creatinine": df.LBXSCR * 88.42,
        "glucose": df.LBXSGL / 18.016, "crp": df.LBXCRP,
        "lymphocyte_pct": df.LBXLYPCT, "mcv": df.LBXMCVSI, "rdw": df.LBXRDW,
        "alp": df.LBXSAPSI, "wbc": df.LBXWBCSI,
    })
    markers = ["albumin", "creatinine", "glucose", "crp", "lymphocyte_pct", "mcv", "rdw", "alp", "wbc"]
    rows = df[markers].to_dict("records")
    df["phenoage"] = [phenoage_from_canonical(a, r).phenoage for a, r in zip(df.age, rows)]
    df["phenoage_xb"] = [linear_predictor(a, r) for a, r in zip(df.age, rows)]
    return df


def person_features(seqn, counts, steps, hours=None):
    """Summaries for one person's 10,080 minutes (7 days)."""
    counts = counts.astype(float)
    counts[counts > MAX_COUNT] = np.nan
    zero = counts == 0
    # Mark runs of >= NONWEAR_RUN zeros as non-wear
    nonwear = np.zeros(len(counts), bool)
    edges = np.diff(np.concatenate(([0], zero.astype(int), [0])))
    starts, ends = np.where(edges == 1)[0], np.where(edges == -1)[0]
    for s, e in zip(starts, ends):
        if e - s >= NONWEAR_RUN:
            nonwear[s:e] = True
    wear = ~nonwear & ~np.isnan(counts)

    n_days = len(counts) // 1440
    valid = []
    for d in range(n_days):
        sl = slice(d * 1440, (d + 1) * 1440)
        if wear[sl].sum() >= VALID_DAY_MIN:
            valid.append(sl)
    out = {"SEQN": int(seqn), "valid_days": len(valid)}
    if len(valid) < MIN_DAYS:
        return out
    c = np.concatenate([counts[sl][wear[sl]] for sl in valid])
    out["wear_min_per_day"] = len(c) / len(valid)
    out["cpm"] = c.mean()
    out["mvpa_min_per_day"] = (c >= MVPA_CPM).sum() / len(valid)
    out["sed_min_per_day"] = (c < SED_CPM).sum() / len(valid)
    # Smirnova et al. 2020 style: total and log-total activity per day, and
    # transition probabilities between active (>= 100 counts) and sedentary bouts
    out["tac_per_day"] = c.sum() / len(valid)
    out["tlac_per_day"] = np.log1p(c).sum() / len(valid)
    astp, satp = [], []
    for sl in valid:
        a = counts[sl][wear[sl]] >= SED_CPM
        if len(a) < 2:
            continue
        runs = np.diff(np.flatnonzero(np.diff(np.concatenate(([-1], a.astype(int), [-1]))) != 0))
        kinds = a[np.concatenate(([0], np.cumsum(runs)[:-1]))]
        if kinds.any():
            astp.append(1.0 / runs[kinds].mean())
        if (~kinds).any():
            satp.append(1.0 / runs[~kinds].mean())
    out["astp"] = np.mean(astp) if astp else np.nan
    out["satp"] = np.mean(satp) if satp else np.nan
    if hours is not None:
        out.update(rhythm(counts, wear, hours, valid))
    if steps is not None:
        s = np.concatenate([steps[sl][wear[sl]] for sl in valid]).astype(float)
        out["steps_per_day"] = np.nansum(s) / len(valid)
        # Tudor-Locke et al. 2009: count steps only in minutes >= 500 counts,
        # which removes the 7164's spurious steps during light movement
        out["steps_censored_per_day"] = np.nansum(np.where(c >= CENSOR_CPM, s, 0)) / len(valid)
        # Peak 30-minute cadence: mean of each valid day's 30 highest step-minutes
        peaks = []
        for sl in valid:
            day = np.where(wear[sl], steps[sl], 0).astype(float)
            day = np.nan_to_num(day)
            peaks.append(np.sort(day)[-30:].mean())
        out["peak30_cadence"] = float(np.mean(peaks))
    return out


def rhythm(counts, wear, hours, valid):
    """Non-parametric rest-activity rhythm (van Someren 1999) on hourly means.

    NHANES 2003-06 asked people to remove the monitor at night, so non-wear
    minutes count as zero activity here; the rhythm measures therefore mix
    true rest with time the monitor was off.
    """
    x = np.where(wear, np.nan_to_num(counts), 0.0)
    hourly, hod = [], []
    for sl in valid:
        h = hours[sl].astype(int)
        v = x[sl]
        for hr in range(24):
            m = h == hr
            if m.any():
                hourly.append(v[m].mean())
                hod.append(hr)
    hourly, hod = np.array(hourly), np.array(hod)
    profile = np.array([hourly[hod == hr].mean() if (hod == hr).any() else np.nan for hr in range(24)])
    if np.isnan(profile).any() or len(hourly) < 48:
        return {}
    ext = np.concatenate([profile, profile])
    l5 = min(ext[i:i + 5].mean() for i in range(24))
    m10 = max(ext[i:i + 10].mean() for i in range(24))
    mean = hourly.mean()
    var = ((hourly - mean) ** 2).sum()
    n, p = len(hourly), 24
    is_ = n * ((profile - mean) ** 2).sum() / (p * var) if var > 0 else np.nan
    iv = n * (np.diff(hourly) ** 2).sum() / ((n - 1) * var) if var > 0 else np.nan
    return {"l5": l5, "m10": m10, "ra": (m10 - l5) / (m10 + l5) if m10 + l5 > 0 else np.nan,
            "is": is_, "iv": iv}


def activity(files, eligible):
    path = os.path.join(DATA, files["pax"])
    reader = pd.read_sas(path, format="xport", chunksize=2_000_000)
    results, carry = [], None
    for i, chunk in enumerate(reader):
        if carry is not None:
            chunk = pd.concat([carry, chunk], ignore_index=True)
        last = chunk.SEQN.iloc[-1]
        carry = chunk[chunk.SEQN == last]
        chunk = chunk[chunk.SEQN != last]
        results.extend(_summarise(chunk, eligible))
        print("  chunk %d: %d people so far" % (i + 1, len(results)), flush=True)
    if carry is not None:
        results.extend(_summarise(carry, eligible))
    return pd.DataFrame(results)


def _summarise(chunk, eligible):
    out = []
    has_steps = "PAXSTEP" in chunk.columns
    chunk = chunk[chunk.SEQN.isin(eligible)]
    for seqn, g in chunk.groupby("SEQN", sort=False):
        if (g.PAXSTAT.round() != 1).any() or (g.PAXCAL.round() != 1).any():
            continue
        g = g.sort_values("PAXN")
        counts = g.PAXINTEN.round().to_numpy()
        steps = g.PAXSTEP.round().to_numpy() if has_steps else None
        out.append(person_features(seqn, counts, steps, g.PAXHOUR.round().to_numpy()))
    return out


def main():
    frames = []
    for cycle, files in CYCLES.items():
        print("%s: blood and demographics" % cycle, flush=True)
        df = blood(cycle, files)
        mort = mortality(files["mort"])
        df = df.merge(mort, on="SEQN", how="left")
        df = df[df.eligstat == 1].dropna(subset=["mortstat", "permth_exm"])
        print("  %d adults with all 9 markers and mortality follow-up" % len(df), flush=True)
        print("%s: accelerometer" % cycle, flush=True)
        act = activity(files, set(df.SEQN))
        df = df.merge(act, on="SEQN", how="left")
        # Exam pulse: 60-second seated pulse after 5 minutes' rest
        bpx = xpt(files["bpx"])[["SEQN", "BPXPLS"]].rename(columns={"BPXPLS": "pulse"})
        bpx["SEQN"] = bpx.SEQN.astype(int)
        df = df.merge(bpx, on="SEQN", how="left")
        print("  %d with >= %d valid days" % ((df.valid_days >= MIN_DAYS).sum(), MIN_DAYS), flush=True)
        frames.append(df)
    out = pd.concat(frames, ignore_index=True)
    path = os.path.join(DATA, "analysis.csv")
    out.to_csv(path, index=False)
    print("wrote %s (%d rows)" % (path, len(out)))


if __name__ == "__main__":
    main()
