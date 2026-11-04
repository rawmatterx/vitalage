import json
import math
import os
import unittest
from datetime import date

from phenoage.__main__ import main
from phenoage.core import MARKERS
from phenoage.explain import REFERENCE_PROFILE
from phenoage.history import blood_trend, internal_pace, read_blood_history
from phenoage.internal import (PARAMS, internal_age, internal_age_from_canonical,
                               internal_age_range, pace_from_history)
from phenoage.partial import NORMAL_RANGES
from tests.test_core import CANONICAL, REPORT

HERE = os.path.dirname(__file__)
RESEARCH = os.path.join(HERE, "..", "research", "internal_age_params.json")
BLOOD = os.path.join(HERE, "..", "examples", "blood_history.csv")


class ParamsTests(unittest.TestCase):
    def test_package_copy_matches_research_export(self):
        with open(RESEARCH) as f:
            self.assertEqual(PARAMS, json.load(f))

    def test_reproduces_research_predictions(self):
        for ex in PARAMS["examples"]:
            values = {m: ex[m] for m in MARKERS}
            r = internal_age_from_canonical(ex["age"], values)
            self.assertAlmostEqual(r.gap, ex["grimage2"], places=9)
            self.assertAlmostEqual(r.pace - r.typical_pace, ex["dunedinpoam"], places=9)


class InternalAgeTests(unittest.TestCase):
    def test_parts_add_up(self):
        for age in (52, 65, 80):
            r = internal_age_from_canonical(age, CANONICAL)
            self.assertAlmostEqual(r.baseline_gap + sum(r.contributions.values()), r.gap, places=9)

    def test_reference_profile_has_no_marker_years(self):
        r = internal_age_from_canonical(60, REFERENCE_PROFILE)
        for y in r.contributions.values():
            self.assertAlmostEqual(y, 0.0, places=12)
        self.assertAlmostEqual(r.gap, r.baseline_gap, places=12)

    def test_directions_match_aging_biology(self):
        base = internal_age_from_canonical(60, CANONICAL).internal_age
        worse = {"crp": 0.8, "rdw": 16.0, "wbc": 11.0, "lymphocyte_pct": 15.0}
        for m, v in worse.items():
            self.assertGreater(internal_age_from_canonical(60, dict(CANONICAL, **{m: v})).internal_age,
                               base, msg=m)

    def test_report_units(self):
        a = internal_age(60, REPORT).internal_age
        b = internal_age_from_canonical(60, CANONICAL).internal_age
        self.assertAlmostEqual(a, b, places=9)

    def test_age_warning(self):
        self.assertTrue(internal_age_from_canonical(40, CANONICAL).warnings)
        self.assertFalse(internal_age_from_canonical(60, CANONICAL).warnings)

    def test_range_brackets_values_in_normal_interval(self):
        known = {m: v for m, v in CANONICAL.items() if m != "crp"}
        lo, hi = internal_age_range(60, known)
        a, b = NORMAL_RANGES["crp"]
        for i in range(11):
            v = a * (b / a) ** (i / 10)
            ia = internal_age_from_canonical(60, dict(known, crp=v)).internal_age
            self.assertTrue(lo - 1e-9 <= ia <= hi + 1e-9)
        self.assertLess(lo, hi)


class PaceTests(unittest.TestCase):
    def test_needs_three_tests_over_a_year(self):
        self.assertIsNone(pace_from_history([(0, 50), (1, 51)]))
        self.assertIsNone(pace_from_history([(0, 50), (0.3, 50.2), (0.6, 50.5)]))
        self.assertIsNotNone(pace_from_history([(0, 50), (0.6, 50.5), (1.2, 51.1)]))

    def test_slope_and_ci(self):
        pts = [(0, 60.0), (1, 60.8), (2, 61.6), (3, 62.4)]
        p = pace_from_history(pts)
        self.assertAlmostEqual(p.pace, 0.8, places=9)
        self.assertAlmostEqual(p.ci[0], 0.8, places=9)   # perfect line, no residual
        noisy = pace_from_history([(0, 60.0), (1, 61.5), (2, 61.2), (3, 63.0)])
        self.assertLess(noisy.ci[0], noisy.pace)
        self.assertGreater(noisy.ci[1], noisy.pace)

    def test_history_uses_complete_tests_only(self):
        points = blood_trend(read_blood_history(BLOOD), date(1984, 5, 10))
        pace = internal_pace(points)
        self.assertEqual(pace.n_tests, sum(1 for p in points if not p.missing))
        partial = [p for p in points if p.missing][0]
        self.assertLess(partial.internal_low, partial.internal_high)


class CliTests(unittest.TestCase):
    def test_cli_shows_internal_age(self):
        argv = ["--age", "60", "--explain"]
        for marker, (value, unit) in REPORT.items():
            argv += ["--" + marker, str(value), unit]
        self.assertEqual(main(argv), 0)


if __name__ == "__main__":
    unittest.main()
