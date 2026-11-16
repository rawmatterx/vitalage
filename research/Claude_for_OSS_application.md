# Claude for Open Source: application draft (VitalAge)

Drafted 16 November 2026 for https://claude.com/contact-sales/claude-for-oss.
The program gives 6 months of Claude Ultra to open-source maintainers. It is
a subscription, not a research grant, so it pays for the coding and analysis
work, not for the pilot or the blood tests.

## Before you submit (must-fix)

1. **Licence: done locally (Apache-2.0).** `LICENSE` is added and the
   README and `CITATION.cff` name it. Commit and push it so it shows on
   GitHub before you apply.
2. **Check the repo is public** and the README opens with what VitalAge is.
3. **Be straight about the criteria.** VitalAge meets none of the listed
   thresholds (it started on 4 Nov 2026, has one contributor, 27 commits, no
   dependents or download numbers yet). The page says "Don't quite fit?
   ... apply anyway and tell us about it", so apply on that line and on the
   open-science case below. Do not claim downloads, dependents or
   contributors you don't have.
4. **LASI wording.** Your LASI data agreement says the data are not shared
   with third parties. Say Claude is used to write and review the analysis
   code, and never say LASI records are sent to Claude. Keep it that way in
   practice too (run analysis locally; give Claude schemas, summaries and
   code, not individual rows).

## Likely form fields

**Name / email / GitHub handle:** [fill in]

**Project:** VitalAge, https://github.com/rawmatterx/vitalage

**Your role:** Creator and sole maintainer.

**Which criterion do you meet?** None of the listed thresholds yet. Applying
under "Don't quite fit? apply anyway": VitalAge is a new, openly developed
research tool for measuring the pace of aging in Indian adults, with
pre-registered studies and national survey data access.

## Project description (about 200 words)

VitalAge is an open-source tool that measures how fast a person is aging
from a routine blood report, and how exercise, sleep and fitness change that
pace over time. It reads values exactly as printed on Indian lab reports,
computes the published PhenoAge clock (Levine 2018) as a reference, and adds
an "internal age" score refitted on US NHANES data to track DNA-methylation
aging. On a locked, pre-registered test set it correlated 0.49 with GrimAge2
and 0.49 with DunedinPoAm, against 0.38 and 0.30 for PhenoAge. From repeat
tests it reports pace of aging (biological years per calendar year) with a
confidence interval.

Every study in the repo was pre-registered with its test set locked before
fitting, and null results are kept (two combined blood-plus-wearable models
did not beat blood age and are reported as such). The project includes a
Python package, a no-install web page, 94 tests and a citation file.

Blood-age clocks have never been validated in a nationally representative
Indian sample. We have been granted access to the Longitudinal Ageing Study
in India (LASI) to validate and recalibrate them for India, and we are
applying for government and private research grants (ICMR, India Alliance,
Longevity Impetus) to run a 200-person pilot with repeat blood, wearable and
DNA-age measures.

## How you will use Claude (about 120 words)

- Writing and reviewing the LASI analysis code: survey-weighted survival
  models, pre-registration documents, locked test sets and reproducible
  pipelines. Claude works on code, schemas and aggregate outputs only;
  individual LASI records stay on local, encrypted storage under the data
  agreement.
- Grant proposals and the pilot protocol for Indian ethics committees.
- Building the open tool itself: the web page, Indian lab-report import, and
  tests that check every formula against the published reference
  implementation.
- Keeping documentation readable for clinicians and participants, not only
  for programmers.

All code and India-calibrated coefficients will stay open under the
Apache License 2.0.

## Anything else (optional)

VitalAge is a one-person project today. The aim is a free, validated
pace-of-aging measure for Indian adults that clinics and researchers can
run on routine tests, with every step (plan, test set, code, null results)
public. Support now covers the LASI analysis and grant-writing period, before
any funded team exists.
