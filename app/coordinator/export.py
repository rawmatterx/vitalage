"""The de-identified export for the analyst, in the vitalage-pilot-v1 format.

Each participant becomes one record shaped exactly like the output of
`python -m phenoage.pilot` (see phenoage/pilot.py), so the analysis code reads
it unchanged. The file is a JSON list of those records.

What is in it: the random participant ID, birth year, sex, smoking, band model,
blood markers (converted to standard units), monthly band medians, DNA results
and the VitalAge outputs. Every date is "days since the first blood test".
No email, name, birth date or calendar date is in it: they are not even
read here, because only the research store is used.

Two differences from the command-line tool, both because the app keeps only
monthly band medians: VitalAge for a test uses the band month that contains
the test, and band blocks are counted from the person's anchor date (the first
blood test they saved; the same day unless that test was later deleted).
"""

from django.db.models import Prefetch

from phenoage.core import MARKERS
from phenoage.fitness import fitness_age
from phenoage.pilot import BAND_METRICS, SCHEMA
from phenoage.vitalage import VERSION, vitalage
from research.models import BandMonth, BloodMarker, BloodTest, DnaTest, Participant

UNITS = ("canonical: albumin g/L, creatinine umol/L, glucose mmol/L, crp mg/dL, "
         "lymphocyte_pct %, mcv fL, rdw %, alp U/L, wbc 10^3/uL")
BAND_MIN_DAYS = {"resting_hr": 14, "steps": 14, "sleep_hours": 14, "vo2max": 1}


def _fitness(month, age, sex):
    inputs = {m: getattr(month, m) for m in BAND_METRICS
              if getattr(month, m) is not None and getattr(month, m + "_days") >= BAND_MIN_DAYS[m]}
    return fitness_age(age, sex, **inputs).fitness_age if inputs else None


def record(participant):
    tests = list(participant.blood_tests.all())
    if not tests:
        return None
    t0 = tests[0].day_offset
    months = list(participant.band_months.all())
    blood = []
    for test in tests:
        markers = {m.marker: m.value_canonical for m in test.markers.all()}
        res = test.result
        v = None
        if test.complete:
            month = next((m for m in months
                          if m.day_offset <= test.day_offset < m.day_offset + 30), None)
            fit = _fitness(month, test.age, participant.sex) if month else None
            v = round(vitalage(test.age, res.internal_age, fit).vitalage, 3)
        blood.append({
            "days_from_first": test.day_offset - t0,
            "age": round(test.age, 1),
            "markers": {m: round(markers[m], 4) for m in MARKERS if m in markers},
            "phenoage": round(res.phenoage, 3),
            "internal_age": round(res.internal_age, 3),
            "vitalage": v,
        })
    band = []
    for month in months:
        entry = {"block": month.block, "days_from_first_blood_start": month.day_offset - t0}
        for m in BAND_METRICS:
            entry[m + "_median"] = getattr(month, m)
            entry[m + "_days"] = getattr(month, m + "_days")
        band.append(entry)
    devices = sorted({m.device_model for m in months})
    return {
        "schema": SCHEMA,
        "participant_id": str(participant.participant_id),
        "vitalage_version": VERSION,
        "birth_year": participant.birth_year,
        "sex": participant.sex,
        "smoking": participant.smoking,
        "band_device": "; ".join(devices) or None,
        "units": UNITS,
        "blood_tests": blood,
        "band_monthly": band,
        "dna_tests": [{"days_from_first": d.day_offset - t0, "vendor": d.vendor,
                       "clock": d.clock, "value": d.value} for d in participant.dna_tests.all()],
    }


def build_export():
    """All participants with at least one blood test. Withdrawn people are not
    here: withdrawing deletes their research rows."""
    people = Participant.objects.prefetch_related(
        Prefetch("blood_tests", BloodTest.objects.select_related("result").prefetch_related(
            Prefetch("markers", BloodMarker.objects.all()))),
        Prefetch("band_months", BandMonth.objects.all()),
        Prefetch("dna_tests", DnaTest.objects.all()))
    return [r for r in (record(p) for p in people.order_by("participant_id")) if r]
