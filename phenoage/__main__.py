"""Command line: python -m phenoage --age 42 --albumin 4.3 g/dL ...

Every marker takes a value and a unit, exactly as printed on the report.
Leave out up to 3 markers to get a range instead of a single number.
"""

import argparse
import sys

from .citations import short_phenoage_credit
from .core import MARKERS, phenoage
from .combined import vitalage
from .explain import explain
from .partial import MAX_MISSING, describe_interval, phenoage_range
from .units import accepted_units, factor

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
    parser.add_argument("--steps", type=float,
                        help="typical daily steps from your band, to add the combined VitalAge")
    return parser


def print_vitalage(r):
    print("\nVitalAge (blood + steps): %.1f  (%+.1f years)" % (r.vitalage, r.difference))
    print("  Typical person your age : %.1f" % r.baseline)
    print("  Blood (PhenoAge)        : %+.1f yrs" % (round(r.blood_years, 1) + 0.0))
    print("  Steps                   : %+.1f yrs" % (round(r.steps_years, 1) + 0.0))
    print("  Band-to-hip step conversion is uncertain; VitalAge could be %.1f to %.1f."
          % r.steps_range)
    for warning in r.warnings:
        print("warning: " + warning)
    print("  Model: Gompertz fit on NHANES 2005-06 with mortality to 2019; see research/RESULTS.md.")


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


def print_range(r, show_explain):
    print("Chronological age : %.1f" % r.chronological_age)
    print("PhenoAge          : %.1f to %.1f (middle estimate %.1f)"
          % (r.low, r.high, r.estimate))
    print("Difference        : %+.1f to %+.1f years"
          % (r.low - r.chronological_age, r.high - r.chronological_age))
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
            return print_range(phenoage_range(args.age, report), args.explain)
        result = phenoage(args.age, report)
    except ValueError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2

    print("Chronological age : %.1f" % result.chronological_age)
    print("PhenoAge          : %.1f" % result.phenoage)
    print("Difference        : %+.1f years" % result.acceleration)
    print("10-yr mortality   : %.1f%% (model estimate)" % (100 * result.mortality_10yr))
    for warning in result.warnings:
        print("warning: " + warning)
    if args.explain:
        print_explanation(result, report)
    if args.steps is not None:
        try:
            print_vitalage(vitalage(result.chronological_age, result.phenoage, args.steps))
        except ValueError as exc:
            print("error: %s" % exc, file=sys.stderr)
            return 2
    print("\n" + short_phenoage_credit())
    print("Not a diagnostic tool. Trained on US data; not validated for Indian populations.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
