"""Saving and reading a participant's health data.

Everything here goes through the person's PersonLink: it holds the random
participant ID (the key to the research store), the birth date and the
anchor date (day 0). The research store only ever sees "days since the
anchor", never a calendar date.
"""

import statistics
from datetime import timedelta

from django.db import transaction

from identity.models import PersonLink
from phenoage.band import PLAUSIBLE, summarise
from phenoage.core import MARKERS
from phenoage.fitness import fitness_age
from phenoage.history import age_on
from phenoage.internal import MIN_TESTS_FOR_PACE, MIN_YEARS_FOR_PACE, pace_from_history
from phenoage.pilot import BAND_METRICS
from phenoage.units import to_canonical
from phenoage.vitalage import VERSION, vitalage
from research.models import BandMonth, BloodMarker, BloodTest, DnaTest, Participant, Result

from .science import compute

BAND_MIN_DAYS = {"resting_hr": 14, "steps": 14, "sleep_hours": 14, "vo2max": 1}


def link_for(account):
    return PersonLink.objects.get(account=account)


def tests_for(link):
    return (BloodTest.objects.filter(participant_id=link.participant_id)
            .select_related("result").prefetch_related("markers"))


def test_date(link, test):
    return link.anchor_date + timedelta(days=test.day_offset)


# ---------- blood tests ----------

@transaction.atomic
def save_blood_test(account, data):
    """Save a confirmed report. `data` is ReportForm.cleaned_data.
    Sending the same report twice (a double tap, the back button) saves it once."""
    link = PersonLink.objects.select_for_update().get(account=account)
    if link.anchor_date is None:
        link.set_anchor_date(data["test_date"])
    offset = (data["test_date"] - link.anchor_date).days
    report = data["report"]

    for old in tests_for(link).filter(day_offset=offset):
        if old.report() == report:
            return old

    test = BloodTest.objects.create(
        participant_id=link.participant_id, day_offset=offset, age=data["age"],
        source=data["source"], fasting=data["fasting"], complete=len(report) == len(MARKERS))
    BloodMarker.objects.bulk_create([
        BloodMarker(blood_test=test, marker=m, value_as_printed=v, unit_as_printed=u,
                    value_canonical=to_canonical(m, v, u))
        for m, (v, u) in report.items()])
    r = compute(test.age, report)
    if r["complete"]:
        internal, low, high, pheno = r["internal_age"], r["internal_age"], r["internal_age"], r["phenoage"]
    else:
        low, high = r["internal_low"], r["internal_high"]
        internal, pheno = (low + high) / 2, (r["phenoage_low"] + r["phenoage_high"]) / 2
    Result.objects.create(blood_test=test, model_version=VERSION, internal_age=internal,
                          internal_low=low, internal_high=high, phenoage=pheno,
                          pace_estimate=r.get("pace"))
    return test


def get_test(account, pk):
    """The test, only if it belongs to this person."""
    return tests_for(link_for(account)).get(pk=pk)


# ---------- band data ----------

def clean_band_rows(rows):
    """Drop values outside the plausible range (non-wear days, typos)."""
    out = []
    for day, values in rows:
        kept = {m: v for m, v in values.items()
                if v is not None and PLAUSIBLE[m][0] <= v <= PLAUSIBLE[m][1]}
        out.append((day, kept))
    return out


def band_fitness(age, sex, values):
    """Fitness Age from medians, using only metrics with a value."""
    inputs = {m: v for m, v in values.items() if v is not None}
    if not inputs:
        return None
    return fitness_age(age, sex, **inputs)


@transaction.atomic
def save_band(account, rows, device_model):
    """Store monthly medians from daily rows; the daily rows are then forgotten.
    Returns the latest 30-day summary and its Fitness Age, to show on screen."""
    link = link_for(account)
    anchor = link.anchor_date
    rows = clean_band_rows(rows)
    blocks = {}
    for day, values in rows:
        k = (day - anchor).days // 30
        b = blocks.setdefault(k, {m: [] for m in BAND_METRICS})
        for m in BAND_METRICS:
            if values.get(m) is not None:
                b[m].append(values[m])
    for k, vals in blocks.items():
        fields = {"day_offset": 30 * k, "device_model": device_model}
        for m in BAND_METRICS:
            fields[m] = statistics.median(vals[m]) if vals[m] else None
            fields[m + "_days"] = len(vals[m])
        BandMonth.objects.update_or_create(participant_id=link.participant_id, block=k,
                                           defaults=fields)
    summary = summarise(rows)
    participant = Participant.objects.get(pk=link.participant_id)
    age = age_on(link.birth_date, summary.end)
    return summary, band_fitness(age, participant.sex, summary.values)


def month_values(month):
    """Medians with enough days behind them to use."""
    return {m: getattr(month, m) if getattr(month, m + "_days") >= BAND_MIN_DAYS[m] else None
            for m in BAND_METRICS}


# ---------- history ----------

def history(account):
    """Everything the History screen shows, with real dates added back."""
    link = link_for(account)
    participant = Participant.objects.get(pk=link.participant_id)
    tests = list(tests_for(link))
    months = list(BandMonth.objects.filter(participant_id=link.participant_id))

    fitness = []
    for month in months:
        mid = link.anchor_date + timedelta(days=month.day_offset + 15)
        age = age_on(link.birth_date, mid)
        result = band_fitness(age, participant.sex, month_values(month))
        fitness.append({"month": month, "start": link.anchor_date + timedelta(days=month.day_offset),
                        "age": age, "result": result})

    rows = []
    for test in tests:
        res = test.result
        row = {"test": test, "date": test_date(link, test), "age": test.age, "result": res,
               "gap": res.internal_age - test.age, "vitalage": None}
        if test.complete:
            near = [f for f in fitness if f["result"] is not None
                    and f["month"].day_offset <= test.day_offset < f["month"].day_offset + 30]
            fit = near[0]["result"].fitness_age - near[0]["age"] + test.age if near else None
            row["vitalage"] = vitalage(test.age, res.internal_age, fit) if fit is not None else None
        rows.append(row)

    full = [t for t in tests if t.complete]
    pace = None
    if full:
        pace = pace_from_history([((t.day_offset - full[0].day_offset) / 365.2425,
                                   t.result.internal_age) for t in full])
    span = ((full[-1].day_offset - full[0].day_offset) / 365.2425) if full else 0
    return {
        "rows": rows,
        "fitness": fitness,
        "pace": pace,
        "complete_count": len(full),
        "tests_needed": max(0, MIN_TESTS_FOR_PACE - len(full)),
        "years_needed": max(0.0, MIN_YEARS_FOR_PACE - span),
    }


# ---------- pilot checklist ----------

# From research/PILOT_PROTOCOL.md: at least 30 days of band data around the
# blood draw, a DNA-age test within 30 days of it, and the same again at 12 months.
VISIT_WINDOW_DAYS = 30
BAND_DAYS_NEEDED = 30
FOLLOWUP_DAYS = 365
FOLLOWUP_EARLIEST = 300     # a complete test this long after the first one counts as the repeat
REMIND_DAYS_BEFORE = 30


def band_days_around(months, offset):
    """Days of band data in the 30-day blocks that touch the 30 days either side
    of `offset`. Approximate: only monthly counts are kept, so a block that
    partly overlaps the window counts in full."""
    lo, hi = offset - VISIT_WINDOW_DAYS, offset + VISIT_WINDOW_DAYS
    return sum(max(m.resting_hr_days, m.steps_days, m.sleep_hours_days)
               for m in months if m.day_offset <= hi and m.day_offset + 30 > lo)


def visit(link, test, months, dnas):
    if test is None:
        return {"blood": None, "band_days": 0, "band_ok": False, "dna": None, "done": False}
    days = band_days_around(months, test.day_offset)
    dna = next((d for d in dnas if abs(d.day_offset - test.day_offset) <= VISIT_WINDOW_DAYS), None)
    return {"blood": test, "date": test_date(link, test), "band_days": days,
            "band_ok": days >= BAND_DAYS_NEEDED, "dna": dna,
            "done": days >= BAND_DAYS_NEEDED and dna is not None}


def pilot_status(link):
    """The two study visits: the first full blood test and the 12-month repeat."""
    full = [t for t in tests_for(link) if t.complete]
    months = list(BandMonth.objects.filter(participant_id=link.participant_id))
    dnas = list(DnaTest.objects.filter(participant_id=link.participant_id))
    first = full[0] if full else None
    repeat = None
    if first:
        repeat = next((t for t in full if t.day_offset - first.day_offset >= FOLLOWUP_EARLIEST), None)
    due = test_date(link, first) + timedelta(days=FOLLOWUP_DAYS) if first else None
    baseline, followup = visit(link, first, months, dnas), visit(link, repeat, months, dnas)
    return {"baseline": baseline, "followup": followup, "followup_due": due,
            "visits": [("First visit", baseline), ("12-month repeat", followup)]}


# ---------- DNA tests ----------

def save_dna(account, data):
    link = link_for(account)
    return DnaTest.objects.create(
        participant_id=link.participant_id,
        day_offset=(data["test_date"] - link.anchor_date).days,
        vendor=data["vendor"], clock=data["clock"], value=data["value"])


def dna_list(link):
    return [{"test": d, "date": link.anchor_date + timedelta(days=d.day_offset)}
            for d in DnaTest.objects.filter(participant_id=link.participant_id)]


# ---------- my data ----------

def export(account):
    """The person's own data, with real dates, for "Download my data"."""
    link = PersonLink.objects.filter(account=account).first()
    out = {"email": account.email, "language": account.language,
           "consents": [{"purpose": c.purpose, "version": c.consent_version.version,
                         "language": c.consent_version.language,
                         "granted_at": c.granted_at.isoformat(),
                         "withdrawn_at": c.withdrawn_at.isoformat() if c.withdrawn_at else None}
                        for c in account.consents.select_related("consent_version")]}
    if link is None:
        return out
    participant = Participant.objects.get(pk=link.participant_id)
    out.update({"study_code": str(link.participant_id), "birth_date": link.birth_date.isoformat(),
                "sex": participant.sex, "smoking": participant.smoking,
                "blood_tests": [], "band_months": [], "dna_tests": []})
    if link.anchor_date is None:
        return out
    for test in tests_for(link):
        out["blood_tests"].append({
            "date": test_date(link, test).isoformat(), "age": test.age, "fasting": test.fasting,
            "entered_from": test.source,
            "markers": {m.marker: {"value": m.value_as_printed, "unit": m.unit_as_printed}
                        for m in test.markers.all()},
            "internal_age": round(test.result.internal_age, 2),
            "phenoage": round(test.result.phenoage, 2),
            "model_version": test.result.model_version})
    for d in dna_list(link):
        out["dna_tests"].append({"date": d["date"].isoformat(), "vendor": d["test"].vendor,
                                 "clock": d["test"].clock, "value": d["test"].value})
    for month in BandMonth.objects.filter(participant_id=link.participant_id):
        entry = {"from": (link.anchor_date + timedelta(days=month.day_offset)).isoformat(),
                 "device": month.device_model}
        for m in BAND_METRICS:
            entry[m + "_median"] = getattr(month, m)
            entry[m + "_days"] = getattr(month, m + "_days")
        out["band_months"].append(entry)
    return out
