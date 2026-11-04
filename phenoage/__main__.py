"""Command line: python -m phenoage --age 42 --albumin 4.3 g/dL ...

Every marker takes a value and a unit, exactly as printed on the report.
"""

import argparse
import sys

from .core import MARKERS, phenoage
from .units import accepted_units

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
    return parser


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
    print("\nNot a diagnostic tool. Trained on US data; not validated for Indian populations.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
