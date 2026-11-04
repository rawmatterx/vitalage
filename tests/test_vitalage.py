import json
import os
import re
import tempfile
import unittest
from datetime import date

from phenoage.__main__ import main
from phenoage.band import read_rows
from phenoage.history import (blood_trend, fitness_trend, read_blood_history,
                              vitalage_history, vitalage_now)
from phenoage.pilot import build_record, read_dna
from phenoage.pilot import main as pilot_main
from phenoage.vitalage import BAND_CAP, BAND_WEIGHT, VERSION, band_adjustment, vitalage
from tests.test_core import REPORT

HERE = os.path.dirname(__file__)
BLOOD = os.path.join(HERE, "..", "examples", "blood_history.csv")
BAND = os.path.join(HERE, "..", "examples", "band_history.csv")
DNA = os.path.join(HERE, "..", "examples", "dna_tests.csv")
BORN = date(1984, 5, 10)


class CompositeTests(unittest.TestCase):
    def test_formula(self):
        v = vitalage(50, 52.0, fitness_age=46.0)
        self.assertAlmostEqual(v.band_adjustment, BAND_WEIGHT * -4.0)
        self.assertAlmostEqual(v.vitalage, 52.0 + BAND_WEIGHT * -4.0)
        self.assertEqual(v.version, VERSION)

    def test_cap(self):
        self.assertEqual(band_adjustment(50, 70), BAND_CAP)
        self.assertEqual(band_adjustment(50, 30), -BAND_CAP)
        v = vitalage(50, 50, fitness_age=70)
        self.assertTrue(any("capped" in w for w in v.warnings))

    def test_blood_only(self):
        v = vitalage(50, 51.5)
        self.assertEqual(v.vitalage, 51.5)
        self.assertIsNone(v.band_adjustment)

    def test_old_blood_is_carried_forward(self):
        v = vitalage(52, 51.0, fitness_age=52, blood_date=date(2024, 1, 1), as_of=date(2026, 1, 1))
        self.assertAlmostEqual(v.internal_age, 51.0 + 731 / 365.2425, places=9)
        self.assertTrue(any("months old" in w for w in v.warnings))
        with self.assertRaises(ValueError):
            vitalage(50, 50, blood_date=date(2026, 2, 1), as_of=date(2026, 1, 1))

    def test_dashboard_helpers(self):
        b = blood_trend(read_blood_history(BLOOD), BORN)
        f = fitness_trend(read_rows(BAND), BORN, "male")
        now = vitalage_now(b, f, BORN)
        self.assertEqual(now.as_of, f[-1].date)
        hist = vitalage_history(b, f)
        self.assertEqual(len(hist), sum(1 for p in b if not p.missing))
        self.assertIsNone(hist[0][1].band_adjustment)       # no band data in early 2025

    def test_cli(self):
        argv = ["--age", "58", "--sex", "male", "--resting-hr", "62", "--steps", "9000"]
        for marker, (value, unit) in REPORT.items():
            argv += ["--" + marker, str(value), unit]
        self.assertEqual(main(argv), 0)


class PilotExportTests(unittest.TestCase):
    def record(self):
        return build_record(BORN, "male", "never", read_blood_history(BLOOD),
                            read_rows(BAND), read_dna(DNA), "Example band")

    def test_no_calendar_dates_or_birth_date(self):
        text = json.dumps(self.record())
        self.assertEqual(re.findall(r"\d{4}-\d{2}-\d{2}", text), [])
        self.assertNotIn("05-10", text)
        self.assertIn('"birth_year": 1984', text)

    def test_contents(self):
        r = self.record()
        self.assertEqual(r["schema"], "vitalage-pilot-v1")
        self.assertEqual(r["blood_tests"][0]["days_from_first"], 0)
        self.assertEqual(len(r["blood_tests"]), 4)
        self.assertNotIn("crp", r["blood_tests"][1]["markers"])    # untested in the sample
        self.assertEqual({d["clock"] for d in r["dna_tests"]}, {"DunedinPACE", "GrimAge"})
        self.assertTrue(r["band_monthly"])
        self.assertNotEqual(self.record()["participant_id"], r["participant_id"])

    def test_cli(self):
        out = tempfile.NamedTemporaryFile(suffix=".json", delete=False).name
        self.addCleanup(os.remove, out)
        self.assertEqual(pilot_main(["--born", "1984-05-10", "--sex", "male", "--smoking", "never",
                                     "--blood", BLOOD, "--out", out]), 0)
        with open(out) as f:
            self.assertEqual(json.load(f)["band_monthly"], [])


if __name__ == "__main__":
    unittest.main()
