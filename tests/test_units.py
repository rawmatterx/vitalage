import unittest

from phenoage.units import to_canonical


class UnitConversionTests(unittest.TestCase):
    def test_indian_report_units(self):
        self.assertAlmostEqual(to_canonical("albumin", 4.3, "g/dL"), 43.0)
        self.assertAlmostEqual(to_canonical("creatinine", 1.0, "mg/dL"), 88.42)
        self.assertAlmostEqual(to_canonical("glucose", 90.08, "mg/dL"), 5.0, places=3)
        self.assertAlmostEqual(to_canonical("crp", 3.0, "mg/L"), 0.3)
        self.assertAlmostEqual(to_canonical("wbc", 6800, "cells/cumm"), 6.8)

    def test_canonical_units_pass_through(self):
        self.assertEqual(to_canonical("albumin", 43, "g/L"), 43)
        self.assertEqual(to_canonical("wbc", 6.8, "10^9/L"), 6.8)

    def test_unit_spelling_variants(self):
        for unit in ("cells/µL", "cells/uL", "/mm3", "/cu.mm", " cells / cumm "):
            self.assertAlmostEqual(to_canonical("wbc", 7000, unit), 7.0, msg=unit)
        self.assertAlmostEqual(to_canonical("creatinine", 80, "µmol/L"), 80)

    def test_wrong_unit_is_caught_by_range_check(self):
        # Albumin 4.3 typed as g/L instead of g/dL.
        with self.assertRaisesRegex(ValueError, "plausible range"):
            to_canonical("albumin", 4.3, "g/L")
        # WBC 6800 typed as 10^3/uL instead of cells/cumm.
        with self.assertRaisesRegex(ValueError, "plausible range"):
            to_canonical("wbc", 6800, "10^3/uL")

    def test_unknown_unit_and_marker(self):
        with self.assertRaisesRegex(ValueError, "not supported"):
            to_canonical("rdw", 42, "fL")  # RDW-SD, not RDW-CV
        with self.assertRaisesRegex(ValueError, "Unknown marker"):
            to_canonical("hba1c", 5.6, "%")

    def test_zero_crp_rejected(self):
        with self.assertRaisesRegex(ValueError, "detection limit"):
            to_canonical("crp", 0, "mg/L")


if __name__ == "__main__":
    unittest.main()
