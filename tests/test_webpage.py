"""The web page's JavaScript engine must give the same numbers as Python."""

import json
import os
import random
import re
import shutil
import subprocess
import tempfile
import unittest

from phenoage import phenoage_from_canonical
from phenoage.explain import REFERENCE_PROFILE, marker_years
from phenoage.fitness import fitness_age
from phenoage.partial import NORMAL_RANGES, phenoage_range_from_canonical
from phenoage.units import PLAUSIBLE_RANGES

PAGE = os.path.join(os.path.dirname(__file__), "..", "web", "vitalage.html")
NODE = shutil.which("node")

RUNNER = """
const VA = require(process.argv[2]);
const cases = JSON.parse(require("fs").readFileSync(0, "utf8"));
const out = cases.map(c => {
  if (c.kind === "full") {
    const r = VA.phenoage(c.age, c.values);
    const parts = {};
    for (const m in c.values) parts[m] = VA.markerYears(m, c.values[m], VA.REFERENCE[m]);
    return { phenoage: r.phenoage, mortality: r.mortality, parts };
  }
  if (c.kind === "range") {
    const r = VA.range(c.age, c.values);
    return { low: r.low, estimate: r.estimate, high: r.high, missing: r.missing };
  }
  if (c.kind === "fitness") {
    const r = VA.fitness(c.age, c.sex, c.band);
    return { fitnessAge: r.fitnessAge, parts: r.parts };
  }
  if (c.kind === "unit") return { value: VA.toCanonical(c.marker, c.value, c.unit) };
});
process.stdout.write(JSON.stringify(out));
"""


def random_values(rng):
    values = {}
    for m, (lo, hi) in PLAUSIBLE_RANGES.items():
        a, b = NORMAL_RANGES[m]
        # Mostly near-normal values, sometimes anywhere plausible
        if rng.random() < 0.8:
            a, b = a * 0.8, b * 1.2
        a, b = max(a, lo), min(b, hi)
        values[m] = rng.uniform(a, b)
    return values


@unittest.skipUnless(NODE, "node is not installed")
class WebEngineMatchesPython(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(PAGE, encoding="utf-8") as f:
            html = f.read()
        script = re.search(r'<script id="vitalage-engine">(.*?)</script>', html, re.S).group(1)
        cls.tmp = tempfile.mkdtemp()
        cls.engine = os.path.join(cls.tmp, "engine.js")
        with open(cls.engine, "w", encoding="utf-8") as f:
            f.write(script)
        cls.runner = os.path.join(cls.tmp, "runner.js")
        with open(cls.runner, "w", encoding="utf-8") as f:
            f.write(RUNNER)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def run_js(self, cases):
        out = subprocess.run([NODE, self.runner, self.engine], input=json.dumps(cases),
                             capture_output=True, text=True, check=True)
        return json.loads(out.stdout)

    def test_full_phenoage_and_parts(self):
        rng = random.Random(1)
        cases = [{"kind": "full", "age": rng.uniform(20, 84), "values": random_values(rng)}
                 for _ in range(200)]
        for case, js in zip(cases, self.run_js(cases)):
            py = phenoage_from_canonical(case["age"], case["values"])
            self.assertAlmostEqual(js["phenoage"], py.phenoage, places=9)
            self.assertAlmostEqual(js["mortality"], py.mortality_10yr, places=12)
            for m, v in case["values"].items():
                self.assertAlmostEqual(js["parts"][m],
                                       marker_years(m, v, REFERENCE_PROFILE[m]), places=9)

    def test_missing_marker_ranges(self):
        rng = random.Random(2)
        markers = list(PLAUSIBLE_RANGES)
        cases = []
        for _ in range(100):
            values = random_values(rng)
            for m in rng.sample(markers, rng.randint(1, 3)):
                del values[m]
            cases.append({"kind": "range", "age": rng.uniform(20, 84), "values": values})
        for case, js in zip(cases, self.run_js(cases)):
            py = phenoage_range_from_canonical(case["age"], case["values"])
            self.assertAlmostEqual(js["low"], py.low, places=9)
            self.assertAlmostEqual(js["estimate"], py.estimate, places=9)
            self.assertAlmostEqual(js["high"], py.high, places=9)
            self.assertEqual(js["missing"], py.missing)

    def test_fitness_age(self):
        rng = random.Random(3)
        cases = []
        for _ in range(200):
            band = {"resting_hr": rng.uniform(40, 110), "steps": rng.uniform(1000, 16000),
                    "sleep_hours": rng.uniform(4, 10.5), "vo2max": rng.uniform(15, 60)}
            for k in rng.sample(list(band), rng.randint(0, 3)):
                del band[k]
            cases.append({"kind": "fitness", "age": rng.uniform(20, 79),
                          "sex": rng.choice(["male", "female"]), "band": band})
        for case, js in zip(cases, self.run_js(cases)):
            py = fitness_age(case["age"], case["sex"], **case["band"])
            self.assertAlmostEqual(js["fitnessAge"], py.fitness_age, places=9)
            for c in py.components:
                self.assertAlmostEqual(js["parts"][c.metric], c.years, places=9)

    def test_unit_conversion(self):
        from phenoage.units import to_canonical
        cases = [
            ("albumin", 4.3, "g/dL"), ("creatinine", 0.9, "mg/dL"), ("creatinine", 80, "µmol/L"),
            ("glucose", 95, "mg/dL"), ("glucose", 5.2, "mmol/L"), ("crp", 1.2, "mg/L"),
            ("wbc", 6800, "cells/cumm"), ("wbc", 6.8, "10^3/µL"), ("wbc", 6.8, "10^9/L"),
            ("alp", 78, "IU/L"),
        ]
        js = self.run_js([{"kind": "unit", "marker": m, "value": v, "unit": u} for m, v, u in cases])
        for (m, v, u), out in zip(cases, js):
            self.assertAlmostEqual(out["value"], to_canonical(m, v, u), places=12, msg=(m, u))


if __name__ == "__main__":
    unittest.main()
