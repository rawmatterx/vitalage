"""Pages of the VitalAge app.

Add report -> Review values -> Results, then History and Fitness band. Only
signed-in participants who have given consent and filled in About you can
open these pages. A report is saved when the person confirms the values on
the Review screen; the lab file itself never reaches the server.
"""

import io

from django.contrib import messages
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from identity.decorators import participant_required
from identity.models import AuditLog
from phenoage import phenoage
from phenoage.band import parse_rows
from phenoage.internal import internal_age
from phenoage.vitalage import VERSION
from research.models import BloodTest

from . import records
from .forms import BandForm, ReportForm
from .science import compute, review_rows

# The worked example from the README (age 58), values as printed on an Indian lab report.
EXAMPLE_AGE = 58
EXAMPLE_REPORT = {
    "albumin": (4.1, "g/dL"),
    "creatinine": (1.0, "mg/dL"),
    "glucose": (112, "mg/dL"),
    "crp": (3.5, "mg/L"),
    "lymphocyte_pct": (24, "%"),
    "mcv": (93, "fL"),
    "rdw": (14.1, "%"),
    "alp": (96, "U/L"),
    "wbc": (8400, "cells/cumm"),
}


def example_result():
    """Internal age and PhenoAge for the fixed example, rounded for display."""
    inner = internal_age(EXAMPLE_AGE, EXAMPLE_REPORT)
    pheno = phenoage(EXAMPLE_AGE, EXAMPLE_REPORT)
    return {
        "age": EXAMPLE_AGE,
        "internal_age": round(inner.internal_age, 1),
        "gap": round(inner.gap, 1),
        "phenoage": round(pheno.phenoage, 1),
    }


def home(request):
    return render(request, "core/home.html", {"example": example_result(), "version": VERSION})


def report_form(request, data=None, **kwargs):
    return ReportForm(data, born=records.link_for(request.user).birth_date, **kwargs)


@participant_required
@require_http_methods(["GET", "POST"])
def add_report(request):
    """Screen 5. A POST here comes from "Edit values" on the Review screen and
    simply puts the values back in the form."""
    form = report_form(request, request.POST if request.method == "POST" else None)
    if request.method == "POST":
        form.is_valid()   # show any problems next to the boxes
    return render(request, "core/add_report.html", {"form": form})


@participant_required
@require_POST
def review(request):
    """Screen 6: show the values back, as printed, before saving."""
    form = report_form(request, request.POST)
    if not form.is_valid():
        return render(request, "core/add_report.html", {"form": form})
    data = form.cleaned_data
    return render(request, "core/review.html", {
        "form": form,
        "rows": review_rows(data["report"]),
        "age": data["age"],
        "test_date": data["test_date"],
        "fasting": data["fasting"],
    })


@participant_required
@require_POST
def save_report(request):
    """The person confirmed the values: check them again, save, show the result."""
    form = report_form(request, request.POST)
    if not form.is_valid():
        return render(request, "core/add_report.html", {"form": form})
    test = records.save_blood_test(request.user, form.cleaned_data)
    return redirect("result", pk=test.pk)


@participant_required
def result(request, pk):
    """Screen 7: the result of one saved test."""
    try:
        test = records.get_test(request.user, pk)
    except BloodTest.DoesNotExist:
        raise Http404
    link = records.link_for(request.user)
    return render(request, "core/result.html", {
        "test": test,
        "r": compute(test.age, test.report()),
        "test_date": records.test_date(link, test),
        "fasting": test.fasting,
    })


@participant_required
@require_POST
def delete_report(request, pk):
    try:
        test = records.get_test(request.user, pk)
    except BloodTest.DoesNotExist:
        raise Http404
    test.delete()
    AuditLog.record(request.user, "blood_test_deleted")
    messages.success(request, "The report was deleted.")
    return redirect("history")


@participant_required
def history(request):
    """Screen 8: every saved test, band months, and pace once it can be trusted."""
    return render(request, "core/history.html", records.history(request.user))


@participant_required
@require_http_methods(["GET", "POST"])
def band(request):
    """Screen 9: upload daily band data. Only monthly medians are kept."""
    link = records.link_for(request.user)
    if link.anchor_date is None:
        return render(request, "core/band.html", {"needs_blood": True})
    form = BandForm(request.POST, request.FILES) if request.method == "POST" else BandForm()
    context = {"form": form}
    if request.method == "POST" and form.is_valid():
        upload = form.cleaned_data["file"]
        try:
            text = upload.read().decode("utf-8-sig")
            rows = parse_rows(io.StringIO(text))
        except (UnicodeDecodeError, ValueError, KeyError) as exc:
            form.add_error("file", "Could not read this file: %s" % exc)
        else:
            summary, fitness = records.save_band(request.user, rows,
                                                 form.cleaned_data["device_model"])
            AuditLog.record(request.user, "band_saved")
            context.update({"summary": summary, "fitness": fitness, "saved_days": len(rows)})
    return render(request, "core/band.html", context)


def health(request):
    """A tiny check the hosting service calls to see the app is alive."""
    return JsonResponse({"status": "ok"})
