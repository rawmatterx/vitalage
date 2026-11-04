"""Command line: python -m phenoage --age 42 --albumin 4.3 g/dL ...

Every marker takes a value and a unit, exactly as printed on the report.
"""

import argparse
import sys

from .core import MARKERS, phenoage
from .explain import explain
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
        parser.add_argument("--" + marker, nargs=2, required=True,
                            metavar=("VALUE", "UNIT"),
                            # argparse treats % as a format character
                            help="units: " + ", ".join(accepted_units(marker)).replace("%", "%%"))
    parser.add_argument("--explain", action="store_true",
                        help="show how many years each marker adds or removes")
    return parser


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


def main(argv=None):
    args = build_parser().parse_args(argv)
    report = {}
    for marker in MARKERS:
        value, unit = getattr(args, marker)
        try:
            report[marker] = (float(value), unit)
        except ValueError:
            print("error: %s value '%s' is not a number" % (marker, value),
                  file=sys.stderr)
            return 2

    try:
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
    print("\nNot a diagnostic tool. Trained on US data; not validated for Indian populations.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
