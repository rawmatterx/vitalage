# PhenoAge calculator (Indian lab units)

Estimates biological age from a routine blood report using Levine's
**Phenotypic Age** (PhenoAge, 2018). You enter values exactly as printed on an
Indian lab report (g/dL, mg/dL, mg/L, cells/cumm) and the calculator converts
them to the units the formula needs.

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

## Tests

```bash
python3 -m unittest discover -s tests -t .
```

The tests check the result against an independent transcription of the
BioAge R package's PhenoAge formula, and check every unit conversion.

## Roadmap

1. **Core PhenoAge with Indian units and tests** (done)
2. **Per-marker explanation in years** (done, `--explain`)
3. Band "fitness age" from resting HR, steps, sleep and VO₂max, using
   published mortality hazard ratios (labelled as a literature-based score)
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
