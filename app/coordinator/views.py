"""Screens 12 and 13: the coordinator dashboard and the export.

The coordinator sees study codes and which steps are done, never health
values or emails of participants (only the email they type to invite someone).
"""

import json

from django import forms
from django.conf import settings
from django.contrib import messages
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone

from core import records
from identity.decorators import coordinator_required
from identity.emails import invite_person
from identity.models import AuditLog, ConsentRecord, Invite, PersonLink

from .export import build_export


class InviteForm(forms.Form):
    email = forms.EmailField(label="Email address")
    language = forms.ChoiceField(label="Language", choices=settings.LANGUAGES, initial="en")


def participant_rows():
    """One row per enrolled person: study code and what is done or missing."""
    rows = []
    for link in PersonLink.objects.all():
        row = {"code": str(link.participant_id)[:8], "status": None}
        if link.anchor_date is not None:
            row["status"] = records.pilot_status(link)
        rows.append(row)

    def sort_key(r):
        s = r["status"]
        return (s is None, s["followup_due"] if s and s["followup_due"] else timezone.now().date())
    return sorted(rows, key=sort_key)


def counts():
    invited = Invite.objects.values("email_hash").distinct().count()
    withdrawn = (ConsentRecord.objects.filter(purpose="pilot_research")
                 .values("account").annotate(active=Count("id", filter=Q(withdrawn_at__isnull=True)))
                 .filter(active=0).count())
    return {"invited": invited, "enrolled": PersonLink.objects.count(), "withdrawn": withdrawn,
            "waiting": Invite.objects.filter(used_at__isnull=True, expires_at__gt=timezone.now()).count()}


@coordinator_required
def dashboard(request):
    form = InviteForm(request.POST) if request.method == "POST" else InviteForm()
    if request.method == "POST" and form.is_valid():
        invite_person(form.cleaned_data["email"], form.cleaned_data["language"], request.user)
        messages.success(request, "Invite sent.")
        return redirect("dashboard")
    rows = participant_rows()
    c = counts()
    c["first_visit_done"] = sum(1 for r in rows if r["status"] and r["status"]["baseline"]["done"])
    c["repeat_done"] = sum(1 for r in rows if r["status"] and r["status"]["followup"]["done"])
    return render(request, "coordinator/dashboard.html", {"form": form, "rows": rows, "c": c})


@coordinator_required
def export(request):
    if request.method == "POST":
        data = build_export()
        AuditLog.record(request.user, "export_downloaded", "%d records" % len(data))
        body = json.dumps(data, indent=2)
        response = HttpResponse(body, content_type="application/json")
        stamp = timezone.now().strftime("%Y%m%d")
        response["Content-Disposition"] = 'attachment; filename="vitalage-pilot-v1-%s.json"' % stamp
        return response
    log = AuditLog.objects.filter(action="export_downloaded").order_by("-at")[:10]
    return render(request, "coordinator/export.html", {"log": log})
