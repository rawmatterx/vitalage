import json
import os
import re
import tempfile
import unittest
from datetime import date

from phenoage import phenoage
from phenoage.band import read_rows
from phenoage.citations import FITNESS, PHENOAGE, short_phenoage_credit
from phenoage.dashboard import build_data, main, render
from phenoage.history import (age_on, blood_trend, change_since_previous,
                              fitness_trend, read_blood_history)

HERE = os.path.dirname(__file__)
BLOOD = os.path.join(HERE, "..", "examples", "blood_history.csv")
BAND = os.path.join(HERE, "..", "examples", "band_history.csv")
BORN = date(1984, 5, 10)


class HistoryTests(unittest.TestCase):
    def test_age_on(self):
        self.assertAlmostEqual(age_on(BORN, date(2024, 5, 10)), 40.0, places=2)

    def test_blood_trend_matches_single_calculation(self):
        tests = read_blood_history(BLOOD)
        points = blood_trend(tests, BORN)
        self.assertEqual(len(points), 4)
        day, report = tests[-1]
        direct = phenoage(age_on(BORN, day), report).phenoage
        self.assertAlmostEqual(points[-1].phenoage, direct, places=9)
        # Sample data improves over time.
        diffs = [p.difference for p in points]
        self.assertEqual(diffs, sorted(diffs, reverse=True))

    def test_untested_marker_becomes_a_range(self):
        points = blood_trend(read_blood_history(BLOOD), BORN)
        sept = points[1]                         # CRP blank in the sample
        self.assertEqual(sept.missing, ["crp"])
        self.assertLess(sept.low, sept.phenoage)
        self.assertLess(sept.phenoage, sept.high)
        self.assertNotIn("crp", sept.contributions)
        full = points[-1]
        self.assertEqual(full.low, full.high)
        self.assertEqual(full.missing, [])

    def test_change_since_previous(self):
        points = blood_trend(read_blood_history(BLOOD), BORN)
        change = change_since_previous(points)
        for marker, years in change.items():
            self.assertAlmostEqual(years, points[-1].contributions[marker]
                                   - points[-2].contributions[marker])
        self.assertIsNone(change_since_previous(points[:1]))

    def test_fitness_trend_is_weekly_and_ends_on_last_day(self):
        rows = read_rows(BAND)
        points = fitness_trend(rows, BORN, "male")
        self.assertEqual(points[-1].date, max(d for d, _ in rows))
        gaps = {(b.date - a.date).days for a, b in zip(points, points[1:])}
        self.assertEqual(gaps, {7})

    def test_bad_blood_header(self):
        f = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False)
        f.write("date,albumin\n2026-01-01,4.2\n")
        f.close()
        self.addCleanup(os.remove, f.name)
        with self.assertRaisesRegex(ValueError, "albumin \\(g/dL\\)"):
            read_blood_history(f.name)


class DashboardTests(unittest.TestCase):
    def build(self):
        blood = blood_trend(read_blood_history(BLOOD), BORN)
        fitness = fitness_trend(read_rows(BAND), BORN, "male")
        return build_data(BORN, "male", blood, fitness)

    def test_embedded_data_round_trips(self):
        data = self.build()
        html = render(data)
        payload = re.search(r'<script id="data" type="application/json">(.*?)</script>',
                            html, re.S).group(1)
        self.assertEqual(json.loads(payload), json.loads(json.dumps(data)))

    def test_script_tag_cannot_be_closed_by_data(self):
        data = self.build()
        data["labels"]["albumin"] = "</script><script>alert(1)</script>"
        html = render(data)
        self.assertEqual(html.count("</script>"), 2)   # only the page's own two

    def test_citations_are_in_the_page(self):
        html = render(self.build())
        for _, _, doi in PHENOAGE + FITNESS:
            self.assertIn(doi, html)
        self.assertIn("not affiliated", html)

    def test_cli_writes_file(self):
        out = tempfile.NamedTemporaryFile(suffix=".html", delete=False).name
        self.addCleanup(os.remove, out)
        self.assertEqual(main(["--born", "1984-05-10", "--sex", "male",
                               "--blood", BLOOD, "--band", BAND, "--out", out]), 0)
        with open(out, encoding="utf-8") as f:
            self.assertIn("VitalAge", f.read())
        self.assertEqual(main(["--born", "1984-05-10", "--blood", "missing.csv",
                               "--out", out]), 2)


class CitationTests(unittest.TestCase):
    def test_phenoage_sources(self):
        dois = [doi for _, _, doi in PHENOAGE]
        self.assertIn("10.18632/aging.101414", dois)        # Levine 2018
        self.assertIn("10.1371/journal.pmed.1002718", dois)  # Liu 2018
        self.assertIn("10.18632/aging.101414", short_phenoage_credit())


if __name__ == "__main__":
    unittest.main()
