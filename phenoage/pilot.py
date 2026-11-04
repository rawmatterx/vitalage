"""Build a de-identified pilot record for the VitalAge validation study.

    python -m phenoage.pilot --born 1984-05-10 --sex male --smoking never \
        --blood blood_history.csv --band band.csv --dna dna_tests.csv \
        --device "Fitbit Charge 6" --out vitalage_pilot.json

What is kept: birth year (not date), sex, smoking status, band brand/model,
blood marker values, monthly band medians, DNA-age test results, and the
VitalAge outputs. Every date becomes "days since the first blood test", so
no calendar dates leave the device. The participant ID is random and is
printed for the participant to keep; nothing links it to a name.

DNA test CSV columns: date,vendor,clock,value
(e.g. 2026-10-30,TruDiagnostic,DunedinPACE,0.92).

See research/PILOT_PROTOCOL.md for consent, storage and the analysis plan.
"""

import argparse
import csv
import json
import statistics
import sys
import uuid
from datetime import date

from .band import read_rows
from .core import MARKERS
from .history import (age_on, blood_trend, fitness_trend, read_blood_history,
                      vitalage_history)
from .units import to_canonical
from .vitalage import VERSION

SCHEMA = "vitalage-pilot-v1"
BAND_METRICS = ("resting_hr", "steps", "sleep_hours", "vo2max")


def read_dna(path):
    rows = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        for line in csv.DictReader(f):
            rows.append({"date": date.fromisoformat(line["date"].strip()),
                         "vendor": line["vendor"].strip(), "clock": line["clock"].strip(),
                         "value": float(line["value"])})
    return rows


def monthly_band(rows, t0):
    """Median of each band metric per 30-day block, counted from t0."""
    blocks = {}
    for day, values in rows:
        k = (day - t0).days // 30
        b = blocks.setdefault(k, {m: [] for m in BAND_METRICS})
        for m in BAND_METRICS:
            v = values.get(m)
            if v is not None:
                b[m].append(v)
    out = []
    for k in sorted(blocks):
        entry = {"block": k, "days_from_first_blood_start": 30 * k}
        for m, vals in blocks[k].items():
            entry[m + "_median"] = statistics.median(vals) if vals else None
            entry[m + "_days"] = len(vals)
        out.append(entry)
    return out


def build_record(born, sex, smoking, tests, band_rows=None, dna=None, device=None):
    if not tests:
        raise ValueError("The pilot needs at least one blood test.")
    t0 = tests[0][0]
    points = blood_trend(tests, born)
    fitness = fitness_trend(band_rows, born, sex) if band_rows else []
    v_by_date = dict(vitalage_history(points, fitness))
    blood = []
    for (day, report), p in zip(tests, points):
        blood.append({
            "days_from_first": (day - t0).days,
            "age": round(age_on(born, day), 1),
            "markers": {m: round(to_canonical(m, *report[m]), 4) for m in MARKERS if m in report},
            "phenoage": round(p.phenoage, 3),
            "internal_age": round(p.internal_age, 3),
            "vitalage": None if day not in v_by_date else round(v_by_date[day].vitalage, 3),
        })
    return {
        "schema": SCHEMA,
        "participant_id": str(uuid.uuid4()),
        "vitalage_version": VERSION,
        "birth_year": born.year,
        "sex": sex,
        "smoking": smoking,
        "band_device": device,
        "units": "canonical: albumin g/L, creatinine umol/L, glucose mmol/L, crp mg/dL, "
                 "lymphocyte_pct %, mcv fL, rdw %, alp U/L, wbc 10^3/uL",
        "blood_tests": blood,
        "band_monthly": monthly_band(band_rows, t0) if band_rows else [],
        "dna_tests": [{"days_from_first": (d["date"] - t0).days, "vendor": d["vendor"],
                       "clock": d["clock"], "value": d["value"]} for d in (dna or [])],
    }


def main(argv=None):
    ap = argparse.ArgumentParser(prog="phenoage.pilot", description=__doc__.split("\n")[0])
    ap.add_argument("--born", required=True, help="birth date YYYY-MM-DD (only the year is kept)")
    ap.add_argument("--sex", choices=("male", "female"), required=True)
    ap.add_argument("--smoking", choices=("never", "former", "current"), required=True)
    ap.add_argument("--blood", required=True)
    ap.add_argument("--band")
    ap.add_argument("--dna")
    ap.add_argument("--device", help="band brand and model")
    ap.add_argument("--out", default="vitalage_pilot.json")
    args = ap.parse_args(argv)
    try:
        rec = build_record(date.fromisoformat(args.born), args.sex, args.smoking,
                           read_blood_history(args.blood),
                           read_rows(args.band) if args.band else None,
                           read_dna(args.dna) if args.dna else None, args.device)
    except (OSError, ValueError) as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2
    with open(args.out, "w") as f:
        json.dump(rec, f, indent=2)
    print("Wrote %s. Your participant ID is %s; keep it if you want to withdraw later."
          % (args.out, rec["participant_id"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
