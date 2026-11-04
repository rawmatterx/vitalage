# VitalAge

VitalAge measures **how gracefully you are aging**: how much aging your body
shows now, how fast that is changing, and what is driving it, so you can see
whether exercise, sleep and health habits are slowing it down.

- **Internal age** (main number): a blood score from a routine report, built
  to track DNA-methylation aging. In US adults aged 50-84 it correlated 0.49
  with DNA internal age (GrimAge2) and 0.49 with DNA pace of aging
  (DunedinPoAm), clearly better than PhenoAge (see below). It is an estimate
  that correlates with DNA age, not a DNA test.
- **Pace of aging:** how fast internal age moves per calendar year across
  repeat blood tests (1.00 = calendar speed), with a 95% confidence interval.
  It needs 3 or more complete tests spanning at least a year; before that you
  get a single-test pace estimate.
- **Levers:** how many years each marker adds or removes, and **Fitness
  Age** from your band (resting heart rate, steps, sleep, VO₂max), the
  fast-moving side you can change week to week.
- **PhenoAge** (Levine 2018) is still computed and shown, as the published
  reference.

Values are entered exactly as printed on an Indian lab report (g/dL, mg/dL,
mg/L, cells/cumm) and converted automatically.

The Python package is still called `phenoage`.

> **Not a diagnostic tool.** PhenoAge was fitted on US (NHANES) adults aged
> roughly 20–84 and has not been validated for Indian populations. Use it to
> track your own trend over time, not to make medical decisions.

## Scientific basis

Blood age is **Phenotypic Age (PhenoAge)**, a published, peer-reviewed
measure. VitalAge uses its coefficients unchanged and adds no fitted
parameters of its own.

1. **Developed in:** Levine ME, Lu AT, Quach A, et al. An epigenetic
   biomarker of aging for lifespan and healthspan. *Aging (Albany NY)*
   2018;10(4):573–591.
   [doi:10.18632/aging.101414](https://doi.org/10.18632/aging.101414)
   Phenotypic Age was built from 9 blood markers plus age by modelling
   mortality in US NHANES III.
2. **Validated in:** Liu Z, Kuo PL, Horvath S, Crimmins E, Ferrucci L,
   Levine M. A new aging measure captures morbidity and mortality risk across
   diverse subpopulations from NHANES IV: a cohort study. *PLoS Med*
   2018;15(12):e1002718.
   [doi:10.1371/journal.pmed.1002718](https://doi.org/10.1371/journal.pmed.1002718)
   Independent sample of 11,432 adults aged 20–84.
3. **Coefficient precision cross-checked against:** Kwon D, Belsky DW. A
   toolkit for quantification of biological age from blood chemistry and
   organ function test data: BioAge. *GeroScience* 2021;43(6):2795–2808.
   [doi:10.1007/s11357-021-00480-5](https://doi.org/10.1007/s11357-021-00480-5)
   The test suite compares every result against BioAge's own formula.

Fitness Age is **not** a published clock; it combines effects from separate
meta-analyses (see [References](#references)). VitalAge is an independent
implementation and is not affiliated with or endorsed by any of these
authors. If you use VitalAge, please cite the papers above.

## Internal age and pace of aging

```bash
python3 -m phenoage --age 58 --albumin 4.1 g/dL --creatinine 1.0 mg/dL \
  --glucose 112 mg/dL --crp 3.5 mg/L --lymphocyte_pct 24 % --mcv 93 fL \
  --rdw 14.1 % --alp 96 U/L --wbc 8400 cells/cumm --explain
```

```
Internal age      : 61.8  (+3.8 years vs calendar age)
Pace estimate     : 1.18 biological years per year (typical at your age 1.11)

What moves your internal age (vs a typical healthy adult your age):
  Typical healthy adult your age: -1.0 yrs
  rdw              +1.0 yrs
  wbc              +0.9 yrs
  crp              +0.8 yrs
  lymphocyte_pct   +0.7 yrs
  ...
```

**How it was built.** NHANES 1999-2002 measured routine blood tests and, for
adults aged 50+, DNA methylation clocks (CDC public file `dnmepi`). A ridge
regression of the 9 PhenoAge markers and age was fitted to predict how much
older or younger each person's DNA looks than their birthday (GrimAge2
acceleration) and their DNA pace of aging (DunedinPoAm). The plan and a
locked 30% test set were committed before fitting. On that test set:

| DNA measure (beyond calendar age) | PhenoAge | Internal-age score | Gain (95% CI) |
|---|---|---|---|
| Internal age (GrimAge2) | 0.38 | 0.49 | +0.11 (+0.06 to +0.16) |
| Pace of aging (DunedinPoAm) | 0.30 | 0.49 | +0.19 (+0.12 to +0.25) |

The final weights were refitted on all 2,388 people
(`phenoage/internal_age_params.json`, exported by `research/dna_age.py`).

**What drives it.** Lower lymphocyte %, higher RDW, MCV, white cells and
CRP, then glucose and ALP. Part of this is the blood signature of smoking,
which GrimAge builds in; for everyone else, inflammation and blood sugar are
the parts that respond to weight, exercise and sleep.

**Pace from repeat tests.** On the dashboard, pace is the slope of internal
age over complete tests (3+, spanning a year or more), with its 95% CI.
Single tests are noisy (a cold raises CRP and WBC), so read the interval:
a pace whose interval includes 1.00 is not yet distinguishable from
calendar speed.

**Limits.** Fitted on US adults aged 50-84 around 2000. Outside that age
range it is a rough guide, and it is not validated in Indian populations.
The study used one test per person, so it validates the "right now" score;
how well test-to-test change tracks change in DNA aging is not yet known.

## Easiest way: the web page

Open [`web/vitalage.html`](web/vitalage.html) in any browser, or use the
hosted copy. Type the values from your blood report, pick the unit printed on
it, and add band values if you have them. Blood age, a range if a test is
missing, the per-marker breakdown, Fitness Age and the citations update as
you type. Everything is calculated in the browser and nothing is sent
anywhere. The test suite runs the page's calculation code in Node and checks
it against the Python package on hundreds of random cases.

**Import from a file** instead of typing:

- **Blood report as a PDF**: the page reads the report's text in your
  browser (with pdf.js), finds the nine markers by their usual names on
  Indian reports (S. Albumin, Creatinine Serum, FBS, hs-CRP, Lymphocytes,
  MCV, RDW-CV, ALP, TLC and others) and fills the form, along with age and
  sex when the report shows them. It skips look-alike lines such as
  post-prandial or random glucose, RDW-SD, absolute lymphocyte count and the
  A/G ratio. Scanned photos have no text and cannot be read. Try it with
  [`examples/sample_lab_report.pdf`](examples/sample_lab_report.pdf).
- **Blood report as a CSV**: the blood history layout below (the newest row
  is used), or simple rows of `test, value, unit`.
- **Band data as a CSV**: one row per day with date, resting heart rate,
  steps, sleep (hours or minutes) and VO₂max columns. The page uses the same
  30-day medians and non-wear rules as `python3 -m phenoage.band`.

Every imported value is highlighted, and the page lists what it found, what
it could not find and any unit it had to guess, so check each value
against your report.

The rest of this README covers the Python tools, for repeated tests, band
CSV exports and the trend dashboard.

## Tests you need

All nine markers come from a standard package plus one add-on:

| Marker | Test on the report | Units accepted |
|---|---|---|
| Albumin | Liver function test (LFT) | g/dL, g/L |
| Alkaline phosphatase (ALP) | LFT | U/L, IU/L |
| Creatinine | Kidney function test (KFT) | mg/dL, µmol/L |
| Glucose (fasting) | Fasting blood sugar | mg/dL, mmol/L |
| C-reactive protein | **hs-CRP** (add-on) | mg/L, mg/dL |
| WBC count | Complete blood count (CBC) | cells/cumm, cells/µL, 10^3/µL, 10^9/L |
| Lymphocyte % | CBC differential | % |
| MCV | CBC | fL |
| RDW | CBC (use **RDW-CV in %**, not RDW-SD in fL) | % |

Tips:
- If CRP is reported as below a limit (e.g. `<0.5 mg/L`), enter the limit.
- A CRP of 10 mg/L or more usually means an acute infection; retest when well.
- Values outside a plausible range are rejected, because that almost always
  means the wrong unit was chosen.

## Usage

Requires Python 3.9+, no extra packages.

```bash
python3 -m phenoage --age 42 --albumin 4.3 g/dL --creatinine 0.9 mg/dL \
  --glucose 95 mg/dL --crp 1.2 mg/L --lymphocyte_pct 32 % --mcv 88 fL \
  --rdw 13.1 % --alp 78 U/L --wbc 6800 cells/cumm
```

```
Chronological age : 42.0
PhenoAge          : 36.4
Difference        : -5.6 years
10-yr mortality   : 1.4% (model estimate)
```

### If a marker was not tested

Leave it out (up to 3 markers). Instead of guessing, the calculator assumes
only that the missing value lies inside a common adult lab reference
interval and reports the lowest and highest PhenoAge that allows. Here CRP
was not tested:

```
Chronological age : 42.0
PhenoAge          : 34.5 to 38.6 (middle estimate 36.2)
Difference        : -7.5 to -3.4 years

Missing marker(s), assumed within a normal lab range:
  crp             0.2-10 mg/L
```

Because PhenoAge is a straight line in the weighted marker sum, the
extremes sit exactly at the interval ends, so the range is exact rather than
simulated. The middle estimate uses the typical healthy value. Assumed
intervals: albumin 3.5–5.0 g/dL, creatinine 0.6–1.3 mg/dL, fasting glucose
70–100 mg/dL, CRP 0.2–10 mg/L, lymphocytes 20–40 %, MCV 80–100 fL, RDW
11.5–14.5 %, ALP 40–130 U/L, WBC 4,000–11,000 cells/cumm. Your lab's
interval may differ, and a value outside it (for example CRP during an
infection) would put PhenoAge outside the range. CRP alone spans about
4 years, so adding hs-CRP to the panel is worth it.

### Which markers drive the result

Add `--explain` to see how many years each marker adds or removes compared
with a typical healthy adult of the same age:

```
Why (vs a typical healthy adult of the same age):
  Same age, reference values : 35.3
  mcv                   88 fL         ref 90       -0.6 yrs
  glucose               95 mg/dL      ref 90.08    +0.6 yrs
  albumin              4.3 g/dL       ref 4.4      +0.4 yrs
  rdw                 13.1 %          ref 13       +0.4 yrs
  ...
  Total                                                   +1.0 yrs
```

This split is exact, not an approximation. The log-log step in PhenoAge
undoes its Gompertz exponential, so PhenoAge is a straight line in the
weighted marker sum: each marker adds `coefficient × (value − reference) / 0.0902`
years, and the parts add up to the total. The reference values
(`phenoage/explain.py`) are typical healthy adult values, a chosen yardstick
rather than population medians; changing them moves years between
"baseline" and "markers" but never changes your PhenoAge.

Rough sensitivities: RDW +1 % point ≈ +3.7 years, doubling CRP ≈ +0.7 years,
fasting glucose +18 mg/dL ≈ +2.2 years, albumin +0.1 g/dL ≈ −0.4 years.

From Python:

```python
from phenoage import phenoage

result = phenoage(42, {"albumin": (4.3, "g/dL"), "crp": (1.2, "mg/L"), ...})
print(result.phenoage, result.acceleration, result.warnings)

from phenoage.explain import explain

for c in explain(result).contributions:
    print(c.marker, round(c.years, 1))
```

## Fitness Age from a band

```bash
python3 -m phenoage.band --age 42 --sex male --csv examples/band_sample.csv
```

```
Band data 2026-10-06 to 2026-11-04
note: steps: ignored 2 day(s) outside 500-60000.
Chronological age : 42.0
Fitness Age       : 40.3
Difference        : -1.7 years

  vo2max             41   ref 39.2 mL/kg/min    -0.8 yrs
  steps          8266.5   ref 7000/day          -0.6 yrs
  resting_hr       61.5   ref 65 bpm            -0.3 yrs
  sleep_hours       6.9   ref 7-8 h             +0.1 yrs
```

The CSV has one row per day with columns `date,resting_hr,steps,sleep_hours,vo2max`
(any may be blank; see `examples/band_sample.csv`). Copy the daily values from
your band's app export. The tool uses the median of the last 30 days, drops
days under 500 steps as "band not worn", and skips a metric with fewer than
14 valid days. You can also pass typical values directly:
`--resting-hr 62 --steps 8400 --sleep 7.1 --vo2max 41`.

**How it works.** Each metric becomes a mortality hazard ratio (HR) from a
meta-analysis, and each HR becomes years with PhenoAge's own Gompertz rate:
`years = ln(HR) / 0.0902`, i.e. "the extra death risk of being that many
years older".

| Metric | Published effect | Reference point |
|---|---|---|
| Resting HR | RR 1.09 per +10 bpm (Zhang 2016) | 65 bpm, clamped to 45–100 |
| Daily steps | HR 1.00 / 0.60 / 0.55 / 0.47 at 3,553 / 5,801 / 7,842 / 10,901 steps (Paluch 2022) | 7,000/day; no extra credit above 8,000 at age 60+ |
| VO₂max | RR 0.87 per +1 MET = 3.5 mL/kg/min (Kodama 2009) | FRIEND treadmill median for age and sex, capped at ±4 METs |
| Sleep | RR 1.12 short, 1.30 long (Cappuccio 2010) | 7–8 h; full effect at ≤6 h or ≥9 h |

**Honest limits.**
- This is a **literature-based score, not a validated clock.** Nobody has
  fitted these four metrics together against deaths.
- The effects come from separate studies and overlap (fitter people also have
  lower resting HR and walk more), so the sum overstates the total. The total
  is capped at ±5 years as a guard, not a correction.
- Band VO₂max is an estimate (often ±10–15%), and band resting HR and sleep
  differ between devices.
- Long sleep and very low step counts are partly signs of existing illness.
- HRV is left out on purpose: wearable HRV is not consistent across devices
  or studies.

## Dashboard with trends over time

```bash
python3 -m phenoage.dashboard --born 1984-05-10 --sex male \
  --blood examples/blood_history.csv --band examples/band_history.csv \
  --out dashboard.html
```

Open `dashboard.html` in any browser; it works offline. It shows:

- your calendar age, latest blood age and latest Fitness Age;
- a chart of "years older or younger than calendar age" over time, with every
  blood test as a point and Fitness Age every week (each from the 30 days
  before it);
- what drives your latest blood age and Fitness Age, marker by marker;
- table views of every number, and the full list of citations with DOIs.

Blood history is a CSV with one row per test and columns named
`marker (unit)`, in the units on your report; see `examples/blood_history.csv`:

```
date,albumin (g/dL),creatinine (mg/dL),glucose (mg/dL),crp (mg/L),lymphocyte_pct (%),mcv (fL),rdw (%),alp (U/L),wbc (cells/cumm)
2026-10-25,4.4,0.90,93,1.0,32,88,13.1,76,6500
```

Leave a cell blank if that marker was not tested; the test then shows as a
range (a vertical bar on the chart). Either `--blood` or `--band` can be left
out. The example files are made-up sample data.

## Can activity improve on PhenoAge? (research, not shipped)

`research/` tests whether adding band-style activity data to the blood
markers predicts death better than PhenoAge alone. It uses public NHANES
2003–2006 data: blood tests, one week of hip accelerometer data, the exam
pulse, and NCHS death records through 2019, for 5,842 adults.

To keep any win honest, a 30% test set (1,753 people, 384 deaths) was
locked and committed before fitting. Every choice was made with
cross-validation on the rest, and every model tried is logged in
[`research/RESULTS.md`](research/RESULTS.md), failures included.

**Result: no combined number is shipped.** The model the pre-registered rule
picked (PhenoAge + minutes of moderate-to-vigorous activity) did not beat
PhenoAge on the locked test set:

| Locked test set | 10-year C-index |
|---|---|
| PhenoAge | 0.847 |
| PhenoAge + activity minutes (chosen in cross-validation) | 0.849 (+0.002, 95% CI −0.002 to +0.006) |

Adding daily steps, resting pulse or peak cadence also gave gains whose
confidence intervals include zero. A refit of the 9 blood markers together
with steps and pulse did well on the test set. It had not been chosen in
cross-validation, so picking it now would be cherry-picking. It is a
candidate for a future study with fresh data. An earlier steps-based
VitalAge (commit 8e3c108) was withdrawn for the same reason.

**Second study, 24-hour wrist data (NHANES 2011–2014).** A second
pre-registered study used wrist accelerometry, which is closer to a
consumer band. It covered 7,454 adults aged 20–79, with 5-year mortality as
the outcome; CRP wasn't measured in those years. Cross-validation chose
blood + daily wrist activity volume (+0.014 in 5-year C), but on the locked
test set the gain was +0.001 (95% CI −0.012 to +0.013), so again nothing
ships. Sleep duration, sleep timing, rest-activity rhythm and resting pulse
didn't help either. Penalised refits of the blood markers did well on both
locked test sets without being chosen in cross-validation. That's a
hypothesis for a future study with fresh data, not a result.

So VitalAge reports internal age, pace and Fitness Age side by side rather
than a single death-risk-based number.

To reproduce (about 1 GB of downloads):

```bash
python3 -m venv .venv-research && .venv-research/bin/pip install "numpy<2.1" "scipy<1.14" "pandas<2.3"
python3 research/fetch_nhanes.py
(cd research/data && unzip -o PAXRAW_C.ZIP && unzip -o PAXRAW_D.ZIP)
.venv-research/bin/python research/build_dataset.py
.venv-research/bin/python research/fit_model.py        # sections 1-3 of RESULTS.md
.venv-research/bin/python research/ladder.py cv        # choices on the 70% only
.venv-research/bin/python research/ladder.py test      # one look at the locked 30%
.venv-research/bin/python research/ladder.py report    # section 4 of RESULTS.md
.venv-research/bin/python research/wrist.py build      # 2011-14 wrist study
.venv-research/bin/python research/wrist.py cv
.venv-research/bin/python research/wrist.py test
.venv-research/bin/python research/wrist.py report     # section 6 of RESULTS.md
```

## Tests

```bash
python3 -m unittest discover -s tests -t .
```

The tests check PhenoAge against an independent transcription of the
BioAge R package's formula, every unit conversion, the per-marker split,
and the Fitness Age curves against the published numbers.

## Roadmap

1. **Core PhenoAge with Indian units and tests** (done)
2. **Per-marker explanation in years** (done, `--explain`)
3. **Band Fitness Age** from resting HR, steps, sleep and VO₂max (done,
   `python3 -m phenoage.band`)
4. **Dashboard with trends over time** (done, `python3 -m phenoage.dashboard`)
5. **Missing-marker handling** with a range instead of a single number (done)
6. **Combined blood + activity model on NHANES 2003–2006** (done, null
   result: nothing beat PhenoAge on a locked test set; see `research/RESULTS.md`)

## References

Fitness Age sources (all DOIs checked against Crossref):

- Zhang D, Shen X, Qi X. Resting heart rate and all-cause and cardiovascular
  mortality in the general population: a meta-analysis. *CMAJ*
  2016;188(3):E53–63. [doi:10.1503/cmaj.150535](https://doi.org/10.1503/cmaj.150535)
- Paluch AE et al. Daily steps and all-cause mortality: a meta-analysis of
  15 international cohorts. *Lancet Public Health* 2022;7(3):e219–28.
  [doi:10.1016/S2468-2667(21)00302-9](https://doi.org/10.1016/S2468-2667(21)00302-9)
- Kodama S et al. Cardiorespiratory fitness as a quantitative predictor of
  all-cause mortality and cardiovascular events in healthy men and women.
  *JAMA* 2009;301(19):2024–35. [doi:10.1001/jama.2009.681](https://doi.org/10.1001/jama.2009.681)
- Kaminsky LA, Arena R, Myers J. Reference standards for cardiorespiratory
  fitness measured with cardiopulmonary exercise testing: data from the
  FRIEND registry. *Mayo Clin Proc* 2015;90(11):1515–23.
  [doi:10.1016/j.mayocp.2015.07.026](https://doi.org/10.1016/j.mayocp.2015.07.026)
- Cappuccio FP et al. Sleep duration and all-cause mortality: a systematic
  review and meta-analysis of prospective studies. *Sleep* 2010;33(5):585–92.
  [doi:10.1093/sleep/33.5.585](https://doi.org/10.1093/sleep/33.5.585)

The same list lives in `phenoage/citations.py`, which the command-line
tools and the dashboard print from.
