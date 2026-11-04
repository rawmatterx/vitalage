"""Read daily band data from a CSV and summarise the last 30 days.

Expected columns (header names are case-insensitive, any may be blank):

    date,resting_hr,steps,sleep_hours,vo2max
    2026-10-01,62,8450,7.1,41

Most band apps (Apple Health, Google Health Connect, Fitbit, Garmin, Mi
Fitness) can export these as daily values; copy them into this layout.

Command line:
    python -m phenoage.band --age 42 --sex male --csv band.csv
    python -m phenoage.band --age 42 --sex male --resting-hr 62 --steps 8400
"""

import argparse
import csv
import statistics
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Dict, List, Optional

from .citations import FITNESS
from .fitness import fitness_age

WINDOW_DAYS = 30
MIN_DAYS = 14             # fewer valid days than this and the metric is skipped
NON_WEAR_STEPS = 500      # days below this are treated as not wearing the band

DAILY_METRICS = ("resting_hr", "steps", "sleep_hours")
PLAUSIBLE = {
    "resting_hr": (30.0, 120.0),
    "steps": (NON_WEAR_STEPS, 60000.0),
    "sleep_hours": (2.0, 14.0),
    "vo2max": (10.0, 90.0),
}


@dataclass
class BandSummary:
    start: date
    end: date
    values: Dict[str, Optional[float]]     # median per metric, None if skipped
    days: Dict[str, int]                   # valid days used per metric
    notes: List[str]


def _parse_float(text):
    text = (text or "").strip()
    if not text:
        return None
    try:
        return float(text.replace(",", ""))
    except ValueError:
        return None


def read_rows(path):
    """Return a list of (date, {metric: value}) from the CSV."""
    rows = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError("%s is empty" % path)
        header = {name.strip().lower(): name for name in reader.fieldnames}
        if "date" not in header:
            raise ValueError("%s needs a 'date' column" % path)
        for line in reader:
            day = date.fromisoformat(line[header["date"]].strip())
            values = {}
            for metric in DAILY_METRICS + ("vo2max",):
                if metric in header:
                    values[metric] = _parse_float(line[header[metric]])
            rows.append((day, values))
    if not rows:
        raise ValueError("%s has no data rows" % path)
    return rows


def summarise(rows, end=None):
    """Medians of the WINDOW_DAYS days up to `end` (default: the latest day),
    with non-wear and bad values dropped."""
    if end is None:
        end = max(day for day, _ in rows)
    start = end - timedelta(days=WINDOW_DAYS - 1)
    recent = [(d, v) for d, v in rows if start <= d <= end]

    values, days, notes = {}, {}, []
    for metric in DAILY_METRICS + ("vo2max",):
        low, high = PLAUSIBLE[metric]
        good = [v[metric] for _, v in recent
                if v.get(metric) is not None and low <= v[metric] <= high]
        dropped = sum(1 for _, v in recent if v.get(metric) is not None) - len(good)
        days[metric] = len(good)
        if dropped:
            notes.append("%s: ignored %d day(s) outside %g-%g."
                         % (metric, dropped, low, high))
        needed = 1 if metric == "vo2max" else MIN_DAYS
        if len(good) >= needed:
            values[metric] = statistics.median(good)
        else:
            values[metric] = None
            if len(good):
                notes.append("%s: only %d valid day(s) in the last %d; need %d."
                             % (metric, len(good), WINDOW_DAYS, needed))
    return BandSummary(start, end, values, days, notes)


def build_parser():
    parser = argparse.ArgumentParser(
        prog="phenoage.band",
        description="Fitness Age from band data (literature-based score, "
                    "not a validated clock).")
    parser.add_argument("--age", type=float, required=True)
    parser.add_argument("--sex", choices=("male", "female"),
                        help="needed for the VO2max reference")
    parser.add_argument("--csv", help="daily band data, see module docs")
    parser.add_argument("--resting-hr", type=float, help="bpm, 30-day typical")
    parser.add_argument("--steps", type=float, help="steps per day, 30-day typical")
    parser.add_argument("--sleep", type=float, help="hours per night, 30-day typical")
    parser.add_argument("--vo2max", type=float, help="mL/kg/min from the band")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    inputs = {"resting_hr": args.resting_hr, "steps": args.steps,
              "sleep_hours": args.sleep, "vo2max": args.vo2max}
    if args.csv:
        try:
            summary = summarise(read_rows(args.csv))
        except (OSError, ValueError) as exc:
            print("error: %s" % exc, file=sys.stderr)
            return 2
        print("Band data %s to %s" % (summary.start, summary.end))
        for note in summary.notes:
            print("note: " + note)
        for metric, value in summary.values.items():
            if inputs[metric] is None:      # command-line values win
                inputs[metric] = value

    try:
        result = fitness_age(args.age, args.sex, **inputs)
    except ValueError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2

    print("Chronological age : %.1f" % result.chronological_age)
    print("Fitness Age       : %.1f" % result.fitness_age)
    print("Difference        : %+.1f years" % result.difference)
    print()
    for c in result.components:
        years = round(c.years, 1) + 0.0  # avoid printing -0.0
        print("  %-12s %8g   ref %-16s %+5.1f yrs" % (c.metric, round(c.value, 1),
                                                     c.reference, years))
    for warning in result.warnings:
        print("warning: " + warning)
    print("\nLiterature-based score from separate studies, not a validated "
          "clock. Not a diagnostic tool.")
    print("Sources: " + "; ".join("%s (doi:%s)" % (label, doi)
                                  for label, _, doi in FITNESS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
