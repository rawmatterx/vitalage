"""Pages of the VitalAge app.

Milestone 1 has one real page. It runs the existing phenoage science code on
a fixed example report, to prove the web app and the science package are
wired together. Nothing is saved and no personal data is used.
"""

from django.http import JsonResponse
from django.shortcuts import render

from phenoage import phenoage
from phenoage.internal import internal_age
from phenoage.vitalage import VERSION

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


def health(request):
    """A tiny check the hosting service calls to see the app is alive."""
    return JsonResponse({"status": "ok"})
