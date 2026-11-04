import math
import os
import tempfile
import unittest
from datetime import date, timedelta

from phenoage.band import main, read_rows, summarise
from phenoage.fitness import (MAX_TOTAL_YEARS, fitness_age, hr_to_years,
                              resting_hr_years, sleep_years, steps_years,
                              vo2max_reference, vo2max_years)

SAMPLE = os.path.join(os.path.dirname(__file__), "..", "examples", "band_sample.csv")


class ConversionTests(unittest.TestCase):
    def test_hazard_ratio_to_years(self):
        # Mortality doubles roughly every 7.7 years under PhenoAge's Gompertz rate.
        self.assertAlmostEqual(hr_to_years(2.0), 7.69, places=2)
        self.assertEqual(hr_to_years(1.0), 0.0)

    def test_resting_hr(self):
        self.assertEqual(resting_hr_years(65), 0.0)
        self.assertAlmostEqual(resting_hr_years(75), math.log(1.09) / 0.090165)
        # Clamped at 100 bpm.
        self.assertEqual(resting_hr_years(130), resting_hr_years(100))

    def test_steps_curve_matches_paluch_quartiles(self):
        # Q1 median vs Q4 median: HR 0.47.
        diff = steps_years(10901, 40) - steps_years(3553, 40)
        self.assertAlmostEqual(diff, math.log(0.47) / 0.090165, places=9)
        self.assertAlmostEqual(steps_years(7000, 40), 0.0, places=12)
        # Flat outside the studied range.
        self.assertEqual(steps_years(2000, 40), steps_years(3553, 40))
        self.assertEqual(steps_years(20000, 40), steps_years(10901, 40))

    def test_steps_plateau_for_60_plus(self):
        self.assertEqual(steps_years(12000, 65), steps_years(8000, 65))
        self.assertLess(steps_years(12000, 45), steps_years(8000, 45))

    def test_vo2max_reference_is_friend_median(self):
        self.assertEqual(vo2max_reference(45, "male"), 37.8)
        self.assertEqual(vo2max_reference(45, "female"), 26.7)
        self.assertAlmostEqual(vo2max_reference(40, "male"), (42.4 + 37.8) / 2)
        with self.assertRaises(ValueError):
            vo2max_reference(45, "other")

    def test_vo2max_one_met_above_reference(self):
        years = vo2max_years(37.8 + 3.5, 45, "male")
        self.assertAlmostEqual(years, math.log(0.87) / 0.090165)
        # Capped at 4 METs either side.
        self.assertEqual(vo2max_years(90, 45, "male"), vo2max_years(37.8 + 14, 45, "male"))

    def test_sleep_u_shape(self):
        self.assertEqual(sleep_years(7.5), 0.0)
        self.assertAlmostEqual(sleep_years(5.0), math.log(1.12) / 0.090165)
        self.assertAlmostEqual(sleep_years(6.5), math.log(1.12) / 0.090165 / 2)
        self.assertAlmostEqual(sleep_years(10.0), math.log(1.30) / 0.090165)


class FitnessAgeTests(unittest.TestCase):
    def test_components_add_up(self):
        r = fitness_age(42, "male", resting_hr=60, steps=9000, sleep_hours=7.2,
                        vo2max=44)
        self.assertAlmostEqual(r.fitness_age - 42, sum(c.years for c in r.components))
        self.assertLess(r.difference, 0)

    def test_total_is_capped(self):
        r = fitness_age(50, "male", resting_hr=95, steps=2000, sleep_hours=4.5,
                        vo2max=20)
        self.assertGreater(r.uncapped_years, MAX_TOTAL_YEARS)
        self.assertEqual(r.difference, MAX_TOTAL_YEARS)
        self.assertTrue(any("capped" in w for w in r.warnings))

    def test_partial_inputs(self):
        r = fitness_age(42, resting_hr=70)
        self.assertEqual([c.metric for c in r.components], ["resting_hr"])

    def test_vo2max_without_sex_is_skipped(self):
        r = fitness_age(42, resting_hr=70, vo2max=40)
        self.assertNotIn("vo2max", [c.metric for c in r.components])
        self.assertTrue(any("sex" in w for w in r.warnings))

    def test_no_inputs(self):
        with self.assertRaises(ValueError):
            fitness_age(42, "male")


class BandCsvTests(unittest.TestCase):
    def write_csv(self, text):
        f = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False)
        f.write(text)
        f.close()
        self.addCleanup(os.remove, f.name)
        return f.name

    def test_sample_file(self):
        summary = summarise(read_rows(SAMPLE))
        self.assertEqual((summary.end - summary.start).days, 29)
        self.assertEqual(summary.days["steps"], 28)   # two non-wear days dropped
        self.assertEqual(summary.days["resting_hr"], 30)
        self.assertIsNotNone(summary.values["vo2max"])

    def test_window_and_minimum_days(self):
        start = date(2026, 1, 1)
        lines = ["Date,Resting_HR,Steps,Sleep_Hours"]
        for i in range(60):
            day = start + timedelta(days=i)
            # Old data is 90 bpm, recent 30 days are 60 bpm.
            rhr = 90 if i < 30 else 60
            steps = "" if i % 3 else "9,000"   # only every 3rd day recorded
            lines.append("%s,%d,%s,7.5" % (day.isoformat(), rhr, steps))
        summary = summarise(read_rows(self.write_csv("\n".join(lines) + "\n")))
        self.assertEqual(summary.values["resting_hr"], 60)
        self.assertEqual(summary.values["sleep_hours"], 7.5)
        self.assertIsNone(summary.values["steps"])     # 10 days < 14 needed
        self.assertTrue(any("steps" in n for n in summary.notes))

    def test_missing_date_column(self):
        with self.assertRaisesRegex(ValueError, "date"):
            read_rows(self.write_csv("day,steps\n2026-01-01,5000\n"))

    def test_cli(self):
        self.assertEqual(main(["--age", "42", "--sex", "male", "--csv", SAMPLE]), 0)
        self.assertEqual(main(["--age", "42", "--resting-hr", "60"]), 0)
        self.assertEqual(main(["--age", "42"]), 2)


if __name__ == "__main__":
    unittest.main()
