# VitalAge pilot: protocol and pre-specified analysis

Status: draft for review before any data is collected. Version 1, 2026-11-04.

## Why

VitalAge v1 (beta) adds half of the Fitness Age gap to internal age, capped
at ±3 years. Internal age is validated against DNA-methylation aging in US
adults aged 50–84 (research/RESULTS.md, section 10). The band weight is a
judgment call. This pilot collects blood, band and DNA-age data from the
same people so that the band weight can be fitted and tested, and so that
internal age can be checked in Indian participants.

## Questions, fixed in advance

1. **Primary.** In pilot participants, does adding band measures to internal
   age improve the correlation with DNA-age acceleration?
2. **Secondary.**
   - How well does internal age track DNA age in Indian adults? Compare with
     the US result (r = 0.49).
   - Do 12-month changes in internal age and VitalAge move with 12-month
     changes in DNA pace?

## Participants and measures

- **Who.** Adults aged 30–75 who already use a fitness band and agree to the
  measures below. Exclusions: pregnancy, acute illness or infection in the
  past 2 weeks, active cancer treatment.
- **Blood.** One fasting panel covering the 9 markers: CBC with
  differential, LFT (albumin, ALP), creatinine, fasting glucose and hs-CRP.
- **Band.** At least 30 days of daily data around the blood draw: resting
  heart rate, steps, sleep and VO₂max where available. Record the band brand
  and model.
- **DNA age.** A commercial saliva or blood DNA-methylation test that reports
  DunedinPACE and, if possible, GrimAge, taken within 30 days of the blood
  draw. Record the vendor and clock names exactly.
- **Questionnaire.** Smoking (never / former / current), with
  self-reported weight and height as optional extras.
- **Follow-up.** Repeat the blood, band and DNA measures at 12 months, to
  answer the pace question.

## Sample size

Question 1 asks whether band measures explain DNA-age variation beyond
internal age. Detecting a partial correlation of 0.2 with 80% power at
α = 0.05 needs about 200 participants; 0.3 needs about 85. Target: **200
completers**, with at least 120 having the 12-month repeat.

## Consent, ethics and privacy (India)

- **Ethics.** Get approval from an Institutional Ethics Committee before
  recruiting, following the ICMR National Ethical Guidelines for Biomedical
  and Health Research. Commercial DNA tests are paid by or for the
  participant, and that must be explained up front.
- **Consent.** Written informed consent covering:
  - what is collected and why;
  - that VitalAge is not a diagnosis;
  - who can see the data;
  - how long it is kept;
  - the right to withdraw using the participant ID, after which the record is
    deleted.
- **Data protection.** Collection must comply with India's Digital Personal
  Data Protection Act 2023: explicit consent, purpose limitation, the right
  to withdraw, and security safeguards. Health and DNA data are especially
  sensitive. **Get legal advice before launch.** This document is not legal
  advice.
- **De-identification.** Participants share only the file produced by
  `python -m phenoage.pilot`. It contains:
  - birth year, sex and smoking status;
  - the band model;
  - blood marker values;
  - monthly band medians;
  - DNA-test results;
  - every date converted to days since the first blood test.

  No name, phone number, email or calendar date leaves the device. Store
  records encrypted, with access limited to the analysis team.
- **Results to participants.** Each participant gets their own VitalAge,
  internal age and DNA results, with plain-language caveats.

## Analysis plan (fixed before any data is seen)

1. **Lock first.** When enrolment closes, set aside 30% of participants as a
   test set, stratified by sex and age band. Commit the list of IDs and its
   hash before any analysis.
2. **Target.** DNA-age acceleration: the residual of the reported GrimAge on
   age, or DunedinPACE where GrimAge is unavailable. Analyse each vendor and
   clock separately if more than one is used.
3. **Models, fitted on the 70% with 5-fold CV for any penalty:**
   - **M0:** internal-age gap alone, using the v1 weights unchanged.
   - **M1:** M0 plus the four Fitness Age components (resting HR, steps,
     sleep, VO₂max), with a ridge penalty.
   - **M2:** M0 plus the Fitness Age gap as a single input. This tests the
     v1 composite form.
4. **Primary test, on the locked 30%:** correlation of M1 minus M0, with a
   paired bootstrap 95% CI (2,000 resamples). **Success = the CI is above
   zero.**
5. **Outcome.**
   - If the test succeeds, VitalAge v2 uses the fitted band weights, refitted
     on all participants, and the v1 → v2 change is documented.
   - If it fails, v2 sets the band weight to zero and keeps band data as a
     separate lever display, as before.
6. **Secondary.**
   - Correlation of internal age with DNA-age acceleration in Indian
     participants, with a CI.
   - 12-month change analyses, descriptive only.
   - Band brand as a moderator, descriptive only.
7. **Reporting.** Every model and result goes into research/RESULTS.md,
   failures included.

## Not decided yet (needs the project owner)

- Where records are stored and who runs the analysis.
- Which DNA-test vendor or vendors to recommend.
- Recruitment channel, and whether participants are reimbursed.
