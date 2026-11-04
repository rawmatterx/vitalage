import itertools
import unittest

from phenoage import phenoage_from_canonical
from phenoage.__main__ import main
from phenoage.core import MARKERS
from phenoage.partial import (NORMAL_RANGES, describe_interval,
                              phenoage_range, phenoage_range_from_canonical)
from tests.test_core import CANONICAL, REPORT


def without(d, *markers):
    return {k: v for k, v in d.items() if k not in markers}


class RangeTests(unittest.TestCase):
    def test_range_brackets_any_value_in_the_normal_interval(self):
        r = phenoage_range_from_canonical(50, without(CANONICAL, "crp"))
        lo, hi = NORMAL_RANGES["crp"]
        for i in range(11):
            value = lo * (hi / lo) ** (i / 10)       # log-spaced across the interval
            pa = phenoage_from_canonical(50, dict(CANONICAL, crp=value)).phenoage
            self.assertLessEqual(r.low - 1e-9, pa)
            self.assertLessEqual(pa, r.high + 1e-9)
        self.assertLess(r.low, r.estimate)
        self.assertLess(r.estimate, r.high)

    def test_range_ends_are_reached(self):
        # The extremes are real: PhenoAge at the interval ends equals low/high.
        r = phenoage_range_from_canonical(50, without(CANONICAL, "albumin"))
        ends = sorted(phenoage_from_canonical(50, dict(CANONICAL, albumin=v)).phenoage
                      for v in NORMAL_RANGES["albumin"])
        self.assertAlmostEqual(r.low, ends[0], places=9)
        self.assertAlmostEqual(r.high, ends[1], places=9)

    def test_multiple_missing_corners(self):
        missing = ("crp", "rdw", "wbc")
        r = phenoage_range_from_canonical(60, without(CANONICAL, *missing))
        corners = []
        for combo in itertools.product(*(NORMAL_RANGES[m] for m in missing)):
            values = dict(CANONICAL, **dict(zip(missing, combo)))
            corners.append(phenoage_from_canonical(60, values).phenoage)
        self.assertAlmostEqual(r.low, min(corners), places=9)
        self.assertAlmostEqual(r.high, max(corners), places=9)
        self.assertEqual(r.missing, list(missing))

    def test_true_value_inside_range(self):
        full = phenoage_from_canonical(42, CANONICAL).phenoage
        for m in MARKERS:
            r = phenoage_range_from_canonical(42, without(CANONICAL, m))
            self.assertTrue(r.low <= full <= r.high, msg=m)

    def test_limits(self):
        with self.assertRaisesRegex(ValueError, "at most 3"):
            phenoage_range_from_canonical(42, without(CANONICAL, "crp", "rdw", "wbc", "mcv"))
        with self.assertRaisesRegex(ValueError, "No markers are missing"):
            phenoage_range_from_canonical(42, CANONICAL)

    def test_wide_range_warning(self):
        r = phenoage_range_from_canonical(42, without(CANONICAL, "rdw", "glucose", "crp"))
        self.assertGreater(r.width, 5)
        self.assertTrue(any("wider than 5" in w for w in r.warnings))

    def test_report_units(self):
        r = phenoage_range(42, without(REPORT, "crp"))
        self.assertEqual(r.missing, ["crp"])
        self.assertEqual(describe_interval("crp"), "0.2-10 mg/L")
        self.assertEqual(describe_interval("glucose"), "70-100 mg/dL")
        self.assertEqual(describe_interval("wbc"), "4000-11000 cells/cumm")


class CliRangeTests(unittest.TestCase):
    def args(self, report):
        argv = ["--age", "42"]
        for marker, (value, unit) in report.items():
            argv += ["--" + marker, str(value), unit]
        return argv

    def test_cli_with_missing_marker(self):
        self.assertEqual(main(self.args(without(REPORT, "crp"))), 0)
        self.assertEqual(main(self.args(without(REPORT, "crp")) + ["--explain"]), 0)

    def test_cli_too_many_missing(self):
        self.assertEqual(main(self.args(without(REPORT, "crp", "rdw", "wbc", "mcv"))), 2)


if __name__ == "__main__":
    unittest.main()
