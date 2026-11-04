"""Turn repeated blood tests and daily band data into trends over time.

Blood history CSV: one row per test, a `date` column, and one column per
marker named "marker (unit)", using the units printed on the report. A blank
cell (or a missing column) means "not tested"; up to 3 can be missing per
test, and that test then shows as a range:

    date,albumin (g/dL),creatinine (mg/dL),glucose (mg/dL),crp (mg/L),...
    2025-11-02,4.3,0.9,95,1.2,...
"""

import csv
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Dict, List, Optional

from .band import summarise
from .core import MARKERS, phenoage
from .explain import REFERENCE_PROFILE, explain, marker_years
from .fitness import fitness_age
from .partial import phenoage_range

_HEADER = re.compile(r"^\s*([a-z_]+)\s*\(([^)]+)\)\s*$", re.IGNORECASE)


def age_on(born, day):
    """Age in years (with fraction) on a given day."""
    return (day - born).days / 365.2425


@dataclass
class BloodPoint:
    date: date
    age: float
    phenoage: float                     # middle estimate when markers are missing
    contributions: Dict[str, float]     # measured marker -> years vs reference
    warnings: List[str]
    low: float = None                   # range when markers are missing
    high: float = None
    missing: List[str] = field(default_factory=list)

    def __post_init__(self):
        if self.low is None:
            self.low = self.high = self.phenoage

    @property
    def difference(self):
        return self.phenoage - self.age


@dataclass
class FitnessPoint:
    date: date
    age: float
    fitness_age: float
    components: Dict[str, float]        # metric -> years

    @property
    def difference(self):
        return self.fitness_age - self.age


def read_blood_history(path):
    """Return [(date, {marker: (value, unit)})] sorted by date."""
    tests = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError("%s is empty" % path)
        columns = {}
        date_col = None
        for name in reader.fieldnames:
            if name.strip().lower() == "date":
                date_col = name
                continue
            match = _HEADER.match(name)
            if not match:
                raise ValueError("Column '%s' should look like 'albumin (g/dL)'" % name)
            marker = match.group(1).lower()
            if marker not in MARKERS:
                raise ValueError("Unknown marker column '%s'" % name)
            columns[marker] = (name, match.group(2).strip())
        if date_col is None:
            raise ValueError("%s needs a 'date' column" % path)
        for line in reader:
            day = date.fromisoformat(line[date_col].strip())
            report = {}
            for marker, (col, unit) in columns.items():
                text = (line[col] or "").strip()
                if text:          # blank = not tested; becomes a range later
                    report[marker] = (float(text), unit)
            tests.append((day, report))
    tests.sort(key=lambda t: t[0])
    return tests


def blood_trend(tests, born):
    points = []
    for day, report in tests:
        age = age_on(born, day)
        try:
            if len(report) == len(MARKERS):
                result = phenoage(age, report)
                exp = explain(result)
                points.append(BloodPoint(day, age, result.phenoage,
                                         {c.marker: c.years for c in exp.contributions},
                                         result.warnings))
            else:
                r = phenoage_range(age, report)
                parts = {m: marker_years(m, v, REFERENCE_PROFILE[m])
                         for m, v in r.known_values.items()}
                points.append(BloodPoint(day, age, r.estimate, parts, r.warnings,
                                         r.low, r.high, r.missing))
        except ValueError as exc:
            raise ValueError("Test on %s: %s" % (day, exc))
    return points


def fitness_trend(rows, born, sex, step_days=7):
    """Fitness Age every `step_days`, each from the 30 days before it."""
    if not rows:
        return []
    first = min(d for d, _ in rows)
    last = max(d for d, _ in rows)
    points = []
    day = last
    while day >= first:
        summary = summarise(rows, end=day)
        inputs = {k: v for k, v in summary.values.items() if v is not None}
        if inputs:
            age = age_on(born, day)
            result = fitness_age(age, sex, **inputs)
            points.append(FitnessPoint(day, age, result.fitness_age,
                                       {c.metric: c.years for c in result.components}))
        day -= timedelta(days=step_days)
    points.reverse()
    # Drop leading points whose 30-day window was mostly before the data began.
    return [p for p in points if (p.date - first).days >= 13]


def change_since_previous(points: List[BloodPoint]) -> Optional[Dict[str, float]]:
    """Per-marker change in years between the last two blood tests."""
    if len(points) < 2:
        return None
    a, b = points[-2].contributions, points[-1].contributions
    return {m: b[m] - a[m] for m in b if m in a}
