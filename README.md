# VitalAge

Two views of how old your body acts:

- **Blood age:** Levine's **Phenotypic Age** (PhenoAge, 2018) from a routine
  blood report. You enter values exactly as printed on an Indian lab report
  (g/dL, mg/dL, mg/L, cells/cumm) and the calculator converts them to the
  units the formula needs.
- **Fitness Age:** resting heart rate, daily steps, sleep and VO₂max from a
  fitness band, each turned into years using published mortality studies.

The Python package is still called `phenoage`.

> **Not a diagnostic tool.** PhenoAge was fitted on US (NHANES) adults aged
> roughly 20–84 and has not been validated for Indian populations. Use it to
> track your own trend over time, not to make medical decisions.

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
4. Dashboard with trends over time
5. Missing-marker handling with a range instead of a single number
6. Refit a combined blood + activity model on NHANES 2003–2006

## References

- Levine ME et al. An epigenetic biomarker of aging for lifespan and
  healthspan. *Aging* 2018;10(4):573–591.
- Liu Z et al. A new aging measure captures morbidity and mortality risk
  across diverse subpopulations from NHANES IV. *PLOS Medicine* 2018.
- Kwon D, Belsky DW. A toolkit for quantification of biological age from
  blood chemistry and organ function test data: BioAge. *GeroScience* 2021.
- Zhang D et al. Resting heart rate and all-cause and cardiovascular
  mortality in the general population: a meta-analysis. *CMAJ* 2016;188(3):E53–63.
- Paluch AE et al. Daily steps and all-cause mortality: a meta-analysis of
  15 international cohorts. *Lancet Public Health* 2022;7(3):e219–28.
- Kodama S et al. Cardiorespiratory fitness as a quantitative predictor of
  all-cause mortality and cardiovascular events. *JAMA* 2009;301(19):2024–35.
- Kaminsky LA et al. Reference standards for cardiorespiratory fitness
  measured with cardiopulmonary exercise testing (FRIEND registry).
  *Mayo Clin Proc* 2015;90(11):1515–23.
- Cappuccio FP et al. Sleep duration and all-cause mortality: a systematic
  review and meta-analysis of prospective studies. *Sleep* 2010;33(5):585–92.
