import math
import unittest

from phenoage import phenoage, phenoage_from_canonical
from phenoage.__main__ import main

# A typical Indian report, in the units printed on it.
REPORT = {
    "albumin": (4.3, "g/dL"),
    "creatinine": (0.9, "mg/dL"),
    "glucose": (95, "mg/dL"),
    "crp": (1.2, "mg/L"),
    "lymphocyte_pct": (32, "%"),
    "mcv": (88, "fL"),
    "rdw": (13.1, "%"),
    "alp": (78, "U/L"),
    "wbc": (6800, "cells/cumm"),
}

CANONICAL = {
    "albumin": 43.0,
    "creatinine": 0.9 * 88.42,
    "glucose": 95 / 18.016,
    "crp": 0.12,
    "lymphocyte_pct": 32.0,
    "mcv": 88.0,
    "rdw": 13.1,
    "alp": 78.0,
    "wbc": 6.8,
}


def bioage_reference(age, v):
    """Transcription of the BioAge R package's original PhenoAge
    (R/phenoage_calc.R, orig = TRUE), kept separate from our implementation."""
    xb = (-19.90667 + (-0.03359355 * v["albumin"]) + (0.009506491 * v["creatinine"])
          + (0.1953192 * v["glucose"]) + (0.09536762 * math.log(v["crp"]))
          + (-0.01199984 * v["lymphocyte_pct"]) + (0.02676401 * v["mcv"])
          + (0.3306156 * v["rdw"]) + (0.001868778 * v["alp"])
          + (0.05542406 * v["wbc"]) + (0.08035356 * age))
    m = 1 - math.exp((-1.51714 * math.exp(xb)) / 0.007692696)
    return (math.log(-0.0055305 * math.log(1 - m)) / 0.090165) + 141.50225, m


class PhenoAgeTests(unittest.TestCase):
    def test_matches_bioage_reference(self):
        for age in (25, 42, 60, 80):
            expected, m = bioage_reference(age, CANONICAL)
            result = phenoage_from_canonical(age, CANONICAL)
            self.assertAlmostEqual(result.phenoage, expected, places=3)
            self.assertAlmostEqual(result.mortality_10yr, m, places=6)

    def test_report_units_give_same_answer_as_canonical(self):
        a = phenoage(42, REPORT).phenoage
        b = phenoage_from_canonical(42, CANONICAL).phenoage
        self.assertAlmostEqual(a, b, places=9)

    def test_healthy_profile_is_younger_than_calendar_age(self):
        result = phenoage(42, REPORT)
        self.assertLess(result.acceleration, 0)
        self.assertAlmostEqual(result.acceleration,
                               result.phenoage - result.chronological_age)

    def test_markers_move_age_in_the_published_direction(self):
        base = phenoage_from_canonical(50, CANONICAL).phenoage
        worse = {
            "crp": 0.8, "glucose": 9.0, "rdw": 16.0, "wbc": 11.0,
            "albumin": 35.0, "lymphocyte_pct": 15.0,
        }
        for marker, value in worse.items():
            values = dict(CANONICAL, **{marker: value})
            self.assertGreater(phenoage_from_canonical(50, values).phenoage, base,
                               msg=marker)

    def test_one_year_older_adds_about_one_year(self):
        a = phenoage_from_canonical(50, CANONICAL).phenoage
        b = phenoage_from_canonical(51, CANONICAL).phenoage
        self.assertAlmostEqual(b - a, 0.08035356 / 0.090165, places=6)

    def test_stable_for_extreme_values(self):
        # Very sick profile: 10-year mortality rounds to 1.0, but the age
        # must still be finite.
        values = dict(CANONICAL, crp=25.0, glucose=30.0, rdw=28.0, albumin=16.0)
        result = phenoage_from_canonical(84, values)
        self.assertTrue(math.isfinite(result.phenoage))
        self.assertGreater(result.phenoage, 84)

    def test_missing_marker(self):
        report = dict(REPORT)
        del report["crp"]
        with self.assertRaisesRegex(ValueError, "Missing markers: crp"):
            phenoage(42, report)

    def test_warnings(self):
        self.assertIn("outside", phenoage(18, REPORT).warnings[0])
        high_crp = dict(REPORT, crp=(15, "mg/L"))
        self.assertIn("CRP", phenoage(42, high_crp).warnings[0])
        self.assertEqual(phenoage(42, REPORT).warnings, [])


class CliTests(unittest.TestCase):
    def args(self, **overrides):
        argv = ["--age", "42"]
        for marker, (value, unit) in dict(REPORT, **overrides).items():
            argv += ["--" + marker, str(value), unit]
        return argv

    def test_cli_runs(self):
        self.assertEqual(main(self.args()), 0)

    def test_cli_rejects_bad_unit(self):
        self.assertEqual(main(self.args(albumin=(4.3, "g/L"))), 2)


if __name__ == "__main__":
    unittest.main()
