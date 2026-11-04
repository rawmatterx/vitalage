import math
import unittest

from phenoage import phenoage_from_canonical
from phenoage.explain import (REFERENCE_PROFILE, explain, marker_years,
                              years_per_unit, years_per_year_of_age)
from phenoage.units import factor
from tests.test_core import CANONICAL


class ExplainTests(unittest.TestCase):
    def test_contributions_add_up_exactly(self):
        for age in (30, 55, 75):
            result = phenoage_from_canonical(age, CANONICAL)
            exp = explain(result)
            total = exp.baseline_phenoage + sum(c.years for c in exp.contributions)
            self.assertAlmostEqual(total, result.phenoage, places=9)

    def test_reference_profile_has_zero_contributions(self):
        exp = explain(phenoage_from_canonical(50, REFERENCE_PROFILE))
        for c in exp.contributions:
            self.assertAlmostEqual(c.years, 0.0, places=12)
        self.assertAlmostEqual(exp.baseline_phenoage, exp.phenoage)

    def test_matches_changing_one_marker_at_a_time(self):
        # Because PhenoAge is linear in xb, moving one marker from reference
        # to its value changes PhenoAge by exactly its contribution.
        base = phenoage_from_canonical(50, REFERENCE_PROFILE).phenoage
        for marker, value in CANONICAL.items():
            values = dict(REFERENCE_PROFILE, **{marker: value})
            shifted = phenoage_from_canonical(50, values).phenoage
            self.assertAlmostEqual(shifted - base,
                                   marker_years(marker, value, REFERENCE_PROFILE[marker]),
                                   places=9, msg=marker)

    def test_sorted_by_size(self):
        exp = explain(phenoage_from_canonical(50, CANONICAL))
        sizes = [abs(c.years) for c in exp.contributions]
        self.assertEqual(sizes, sorted(sizes, reverse=True))

    def test_known_sensitivities(self):
        # RDW is the strongest marker: about 3.7 years per 1 % point.
        self.assertAlmostEqual(years_per_unit("rdw"), 3.667, places=3)
        # Doubling CRP adds about 0.73 years.
        self.assertAlmostEqual(years_per_unit("crp"), 0.733, places=3)
        self.assertAlmostEqual(years_per_year_of_age(), 0.891, places=3)

    def test_crp_uses_log_scale(self):
        a = marker_years("crp", 0.2, 0.1)
        b = marker_years("crp", 0.4, 0.2)
        self.assertAlmostEqual(a, b, places=12)
        self.assertTrue(math.isclose(a, years_per_unit("crp")))

    def test_custom_reference_changes_split_not_total(self):
        result = phenoage_from_canonical(50, CANONICAL)
        other = dict(REFERENCE_PROFILE, rdw=12.0, crp=0.05)
        a, b = explain(result), explain(result, other)
        self.assertNotAlmostEqual(a.baseline_phenoage, b.baseline_phenoage)
        for exp in (a, b):
            self.assertAlmostEqual(
                exp.baseline_phenoage + sum(c.years for c in exp.contributions),
                result.phenoage, places=9)

    def test_missing_reference_marker(self):
        result = phenoage_from_canonical(50, CANONICAL)
        bad = dict(REFERENCE_PROFILE)
        del bad["rdw"]
        with self.assertRaisesRegex(ValueError, "missing: rdw"):
            explain(result, bad)


class FactorTests(unittest.TestCase):
    def test_factor(self):
        self.assertEqual(factor("albumin", "g/dL"), 10.0)
        self.assertAlmostEqual(factor("wbc", "cells/cumm"), 0.001)
        with self.assertRaisesRegex(ValueError, "not supported"):
            factor("rdw", "fL")


if __name__ == "__main__":
    unittest.main()
