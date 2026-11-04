"""Command line: python -m phenoage --age 42 --albumin 4.3 g/dL ...

Every marker takes a value and a unit, exactly as printed on the report.
Leave out up to 3 markers to get a range instead of a single number.
"""

import argparse
import sys

from .citations import short_phenoage_credit
from .core import MARKERS, phenoage
from .explain import explain
from .fitness import fitness_age
from .internal import internal_age_from_canonical, internal_age_range
from .partial import MAX_MISSING, describe_interval, phenoage_range
from .units import accepted_units, factor, to_canonical
from .vitalage import VERSION, vitalage

EXAMPLE = (
    "example:\n"
    "  python -m phenoage --age 42 --albumin 4.3 g/dL --creatinine 0.9 mg/dL \\\n"
    "    --glucose 95 mg/dL --crp 1.2 mg/L --lymphocyte_pct 32 % --mcv 88 fL \\\n"
    "    --rdw 13.1 % --alp 78 U/L --wbc 6800 cells/cumm"
)


def build_parser():
    parser = argparse.ArgumentParser(
        prog="phenoage",
        description="Estimate biological age (Levine PhenoAge) from a blood report.",
        epilog=EXAMPLE,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--age", type=float, required=True,
                        help="chronological age in years")
    for marker in MARKERS:
        parser.add_argument("--" + marker, nargs=2,
                            metavar=("VALUE", "UNIT"),
                            # argparse treats % as a format character
                            help="units: " + ", ".join(accepted_units(marker)).replace("%", "%%"))
    parser.add_argument("--explain", action="store_true",
                        help="show how many years each marker adds or removes")
    band = parser.add_argument_group("band (optional, for the combined VitalAge)")
    band.add_argument("--sex", choices=("male", "female"), help="needed for the VO2max reference")
    band.add_argument("--resting-hr", type=float, help="typical resting heart rate, bpm")
    band.add_argument("--steps", type=float, help="typical steps per day")
    band.add_argument("--sleep", type=float, help="typical sleep per night, hours")
    band.add_argument("--vo2max", type=float, help="band VO2max, mL/kg/min")
    return parser


def band_fitness(args):
    inputs = {"resting_hr": args.resting_hr, "steps": args.steps,
              "sleep_hours": args.sleep, "vo2max": args.vo2max}
    if all(v is None for v in inputs.values()):
        return None
    return fitness_age(args.age, args.sex, **inputs)


def print_vitalage(v, fit):
    print("\nVitalAge %s        : %.1f  (%+.1f years vs calendar age)" % (VERSION, v.vitalage, v.gap))
    print("  Internal age (blood)     : %+.1f yrs" % v.blood_years)
    if v.band_adjustment is not None:
        print("  Band adjustment          : %+.1f yrs  (half of Fitness Age gap %+.1f, capped at 3)"
              % (v.band_adjustment, fit.difference))
    for w in v.warnings:
        print("note: " + w)
    print("Beta: the blood part tracks DNA aging; the band weight is a judgment call until "
          "pilot data refits it.")


def print_explanation(result, report):
    exp = explain(result)
    print("\nWhy (vs a typical healthy adult of the same age):")
    print("  Same age, reference values : %.1f" % exp.baseline_phenoage)
    for c in exp.contributions:
        unit = report[c.marker][1]
        ref = c.reference / factor(c.marker, unit)
        years = round(c.years, 1) + 0.0  # avoid printing -0.0
        print("  %-15s %8g %-10s ref %-7g %+5.1f yrs"
              % (c.marker, report[c.marker][0], unit, round(ref, 2), years))
    print("  %-15s %38s %+5.1f yrs"
          % ("Total", "", sum(c.years for c in exp.contributions)))


def print_internal(r, show_explain):
    print("\nInternal age      : %.1f  (%+.1f years vs calendar age)" % (r.internal_age, r.gap))
    print("Pace estimate     : %.2f biological years per year (typical at your age %.2f)"
          % (r.pace, r.typical_pace))
    if show_explain:
        print("\nWhat moves your internal age (vs a typical healthy adult your age):")
        print("  Typical healthy adult your age: %+.1f yrs" % r.baseline_gap)
        for m, y in sorted(r.contributions.items(), key=lambda kv: -abs(kv[1])):
            print("  %-15s %+5.1f yrs" % (m, round(y, 1) + 0.0))
    for warning in r.warnings:
        print("warning: " + warning)
    print("Internal age tracks DNA-methylation aging (GrimAge2, r = 0.49 in NHANES); it is an "
          "estimate, not a DNA test.")


def print_range(r, show_explain, internal=None):
    print("Chronological age : %.1f" % r.chronological_age)
    print("PhenoAge          : %.1f to %.1f (middle estimate %.1f)"
          % (r.low, r.high, r.estimate))
    print("Difference        : %+.1f to %+.1f years"
          % (r.low - r.chronological_age, r.high - r.chronological_age))
    if internal is not None:
        print("Internal age      : %.1f to %.1f" % internal)
    print("\nMissing marker(s), assumed within a normal lab range:")
    for m in r.missing:
        print("  %-15s %s" % (m, describe_interval(m)))
    for warning in r.warnings:
        print("warning: " + warning)
    if show_explain:
        print("\n(--explain needs all 9 markers.)")
    print("\n" + short_phenoage_credit())
    print("Not a diagnostic tool. Trained on US data; not validated for Indian populations.")
    return 0


def main(argv=None):
    args = build_parser().parse_args(argv)
    report = {}
    for marker in MARKERS:
        if getattr(args, marker) is None:
            continue
        value, unit = getattr(args, marker)
        try:
            report[marker] = (float(value), unit)
        except ValueError:
            print("error: %s value '%s' is not a number" % (marker, value),
                  file=sys.stderr)
            return 2

    try:
        if len(report) < len(MARKERS):
            known = {m: to_canonical(m, *report[m]) for m in report}
            return print_range(phenoage_range(args.age, report), args.explain,
                               internal_age_range(args.age, known))
        result = phenoage(args.age, report)
    except ValueError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2

    print("Chronological age : %.1f" % result.chronological_age)
    print("PhenoAge          : %.1f" % result.phenoage)
    print("Difference        : %+.1f years" % result.acceleration)
    for warning in result.warnings:
        print("warning: " + warning)
    if args.explain:
        print_explanation(result, report)
    ia = internal_age_from_canonical(result.chronological_age, result.canonical_values)
    print_internal(ia, args.explain)
    fit = band_fitness(args)
    print_vitalage(vitalage(args.age, ia.internal_age,
                            None if fit is None else fit.fitness_age), fit)
    print("\n" + short_phenoage_credit())
    print("Not a diagnostic tool. Trained on US data; not validated for Indian populations.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
