import json
import math
import os
import unittest

from phenoage import combined
from phenoage.__main__ import main
from phenoage.combined import (BAND_TO_HIP_OFFSET, REFERENCE_HIP_STEPS,
                               pheno_acceleration, vitalage)
from tests.test_core import REPORT

PARAMS = os.path.join(os.path.dirname(__file__), "..", "research", "combined_params.json")


class ParamsTests(unittest.TestCase):
    def test_constants_match_fitted_params(self):
        with open(PARAMS) as f:
            p = json.load(f)
        self.assertTrue(p["ship"])
        self.assertGreater(p["heldout_c_change_ci"][0], 0)   # shipped only if it helped
        self.assertEqual(combined.AGE_MODEL, {"b0": p["age_model"]["b0"],
                                              "b_age": p["age_model"]["b_age"],
                                              "gamma": p["age_model"]["gamma"]})
        self.assertEqual(combined.COMBINED_MODEL, p["combined_model"])
        self.assertEqual(combined.K, p["K"])
        self.assertEqual(combined.ACCEL_INTERCEPT, p["accel_intercept"])
        self.assertEqual(combined.ACCEL_SLOPE, p["accel_slope"])
        self.assertEqual(list(combined.ACCEL_CLIP), p["accel_clip"])
        self.assertEqual(combined.REFERENCE_HIP_STEPS, p["reference_hip_steps"])
        self.assertEqual(combined.BAND_TO_HIP_OFFSET, p["band_to_hip_offset"])

    def test_k_is_the_gompertz_mapping_constant(self):
        a, c = combined.AGE_MODEL["gamma"], combined.COMBINED_MODEL["gamma"]
        k = math.log(math.expm1(120 * c) / c) - math.log(math.expm1(120 * a) / a)
        self.assertAlmostEqual(k, combined.K, places=12)


class VitalAgeTests(unittest.TestCase):
    def test_parts_add_up(self):
        for age, pa, steps in [(30, 25, 12000), (50, 58, 6000), (70, 80, 3000)]:
            r = vitalage(age, pa, steps)
            self.assertAlmostEqual(r.baseline + r.blood_years + r.steps_years, r.vitalage, places=9)

    def test_matches_ten_year_mortality_definition(self):
        # VitalAge is the age with the same 10-year mortality in the age-only model.
        age, pa, steps = 55, 60, 7000
        r = vitalage(age, pa, steps)
        c, a = combined.COMBINED_MODEL, combined.AGE_MODEL
        eta = (c["b0"] + c["b_age"] * age + c["b_pheno_accel"] * pheno_acceleration(age, pa)
               + c["b_log_steps"] * math.log(r.hip_steps))
        m = -math.expm1(-math.exp(eta) * math.expm1(120 * c["gamma"]) / c["gamma"])
        eta_age = a["b0"] + a["b_age"] * r.vitalage
        m_age = -math.expm1(-math.exp(eta_age) * math.expm1(120 * a["gamma"]) / a["gamma"])
        self.assertAlmostEqual(m, m_age, places=12)

    def test_typical_person_has_no_blood_or_steps_years(self):
        age = 45
        typical_pa = combined.ACCEL_INTERCEPT + combined.ACCEL_SLOPE * age
        r = vitalage(age, typical_pa, REFERENCE_HIP_STEPS + BAND_TO_HIP_OFFSET)
        self.assertAlmostEqual(r.blood_years, 0, places=12)
        self.assertAlmostEqual(r.steps_years, 0, places=12)
        self.assertAlmostEqual(r.vitalage, r.baseline, places=12)

    def test_directions(self):
        base = vitalage(50, 50, 8000).vitalage
        self.assertLess(vitalage(50, 50, 12000).vitalage, base)
        self.assertGreater(vitalage(50, 60, 8000).vitalage, base)

    def test_doubling_steps(self):
        with open(PARAMS) as f:
            per_doubling = json.load(f)["years_per_doubling_steps"]
        a = vitalage(50, 50, 4000 + BAND_TO_HIP_OFFSET)
        b = vitalage(50, 50, 8000 + BAND_TO_HIP_OFFSET)
        self.assertAlmostEqual(b.vitalage - a.vitalage, per_doubling, places=9)

    def test_acceleration_is_winsorized(self):
        lo, hi = combined.ACCEL_CLIP
        self.assertEqual(pheno_acceleration(50, 200), hi)
        self.assertEqual(pheno_acceleration(50, -50), lo)
        self.assertEqual(vitalage(50, 200, 8000).vitalage, vitalage(50, 150, 8000).vitalage)

    def test_steps_uncertainty_range(self):
        r = vitalage(50, 50, 8000)
        self.assertLessEqual(r.steps_range[0], r.vitalage)
        self.assertLessEqual(r.vitalage, r.steps_range[1])
        self.assertGreater(r.steps_range[1] - r.steps_range[0], 1)

    def test_low_steps_floor_and_errors(self):
        r = vitalage(50, 50, 600)
        self.assertEqual(r.hip_steps, combined.MIN_HIP_STEPS)
        self.assertTrue(r.warnings)
        with self.assertRaises(ValueError):
            vitalage(50, 50, 0)


class CliTests(unittest.TestCase):
    def test_cli_with_steps(self):
        argv = ["--age", "42", "--steps", "8400"]
        for marker, (value, unit) in REPORT.items():
            argv += ["--" + marker, str(value), unit]
        self.assertEqual(main(argv), 0)


if __name__ == "__main__":
    unittest.main()
