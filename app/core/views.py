"""Pages of the VitalAge app.

Add report -> Review values -> Results. Only signed-in participants who have
given consent and filled in About you can open these pages (milestone 3).
Nothing is saved yet: the values travel from page to page inside the form
itself, and the server forgets them once the page is sent. Saving comes in
milestone 4.
"""

from datetime import date

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods, require_POST

from phenoage import phenoage
from phenoage.internal import internal_age
from phenoage.vitalage import VERSION

from identity.decorators import participant_required
from identity.models import PersonLink

from .forms import ReportForm
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


def age_today(account):
    """Age in whole years from the birth date kept in the identity store."""
    born = PersonLink.objects.get(account=account).birth_date
    today = date.today()
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))


@participant_required
@require_http_methods(["GET", "POST"])
def add_report(request):
    """Screen 5. A POST here comes from "Edit values" on the Review screen and
    simply puts the values back in the form."""
    form = ReportForm(request.POST) if request.method == "POST" else ReportForm(initial={"age": age_today(request.user)})
    if request.method == "POST":
        form.is_valid()   # show any problems next to the boxes
    return render(request, "core/add_report.html", {"form": form})


@participant_required
@require_POST
def review(request):
    """Screen 6: show the values back, as printed, before any result."""
    form = ReportForm(request.POST)
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
def result(request):
    """Screen 7: the results. The values are checked again, never trusted."""
    form = ReportForm(request.POST)
    if not form.is_valid():
        return render(request, "core/add_report.html", {"form": form})
    data = form.cleaned_data
    return render(request, "core/result.html", {
        "form": form,
        "r": compute(data["age"], data["report"]),
        "test_date": data["test_date"],
        "fasting": data["fasting"],
    })


def health(request):
    """A tiny check the hosting service calls to see the app is alive."""
    return JsonResponse({"status": "ok"})
