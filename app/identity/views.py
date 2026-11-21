"""Screens 1 to 4 (invite welcome, sign in, consent, about you) and 11 (my data).

How someone gets in:
1. The coordinator runs `python app/manage.py invite person@example.com`.
2. The person opens the emailed link (/join/<token>/) and presses Start.
   That signs them in: only they received the link.
3. Later visits: /signin/ -> email -> 6-digit code -> signed in.
"""

import json

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone, translation
from django.views.decorators.http import require_POST

from research.models import Participant

from core import records

from . import privacy
from .crypto import encrypt
from .decorators import next_step
from .emails import send_code
from .forms import AboutForm, CodeForm, ConsentForm, EmailForm
from .models import Account, AuditLog, ConsentRecord, ConsentVersion, Invite, PersonLink, SignInCode

BACKEND = "identity.backends.EmailBackend"
SESSION_KEY = "signin_account"


def welcome(request, token):
    """Screen 1, opened from the invite email."""
    invite = Invite.find_valid(token)
    if invite is None:
        return render(request, "identity/invite_invalid.html", status=404)
    if request.method == "POST":
        with transaction.atomic():
            account = Account.objects.for_email(invite.email)
            if account is None:
                account = Account.objects.create_user(invite.email,
                                                      language=translation.get_language())
            invite.used_at = timezone.now()
            invite.save(update_fields=["used_at"])
            AuditLog.record(account, "invite_used", "invite #%s" % invite.pk)
        login(request, account, backend=BACKEND)
        return redirect(next_step(account))
    # First visit: show the page in the language the coordinator chose for this
    # person, and remember it. The language picker can change it any time.
    first_visit = settings.LANGUAGE_COOKIE_NAME not in request.COOKIES
    if first_visit:
        translation.activate(invite.language)
    response = render(request, "identity/welcome.html", {"token": token})
    if first_visit:
        response.set_cookie(settings.LANGUAGE_COOKIE_NAME, invite.language,
                            max_age=365 * 24 * 3600, samesite="Lax")
    return response


def signin(request):
    """Screen 2, first half: ask for the email address."""
    if request.user.is_authenticated:
        return redirect(next_step(request.user))
    form = EmailForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        account = Account.objects.for_email(form.cleaned_data["email"])
        request.session[SESSION_KEY] = None
        # The same next screen whether or not the email is known, so nobody can
        # use this page to find out who is in the study.
        if account and account.is_active:
            request.session[SESSION_KEY] = account.pk
            code = SignInCode.issue(account)
            if code:
                send_code(account.email, code, account.language)
        return redirect("signin_code")
    return render(request, "identity/signin.html", {"form": form})


def signin_code(request):
    """Screen 2, second half: type the 6-digit code from the email."""
    if SESSION_KEY not in request.session:
        return redirect("signin")
    form = CodeForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        account = Account.objects.filter(pk=request.session.get(SESSION_KEY) or 0,
                                         is_active=True).first()
        if account and SignInCode.verify(account, form.cleaned_data["code"]):
            del request.session[SESSION_KEY]
            login(request, account, backend=BACKEND)
            AuditLog.record(account, "signin")
            return redirect(next_step(account))
        form.add_error("code", translation.gettext(
            "That code did not work. Check the latest email, or ask for a new code."))
    return render(request, "identity/signin_code.html", {"form": form})


@require_POST
def signout(request):
    logout(request)
    return redirect("home")


def consent(request):
    """Screen 3: the consent text, then two separate yes/no choices."""
    if not request.user.is_authenticated:
        return redirect("signin")
    if ConsentRecord.has_active(request.user):
        return redirect(next_step(request.user))
    version = ConsentVersion.current(translation.get_language())
    if version is None:
        return render(request, "identity/consent_missing.html", status=503)
    form = ConsentForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            for purpose in ("pilot_research", "recontact"):
                if form.cleaned_data[purpose]:
                    ConsentRecord.objects.create(account=request.user, consent_version=version,
                                                 purpose=purpose)
                    AuditLog.record(request.user, "consent_granted",
                                    "%s v%s %s" % (purpose, version.version, version.language))
        return redirect(next_step(request.user))
    return render(request, "identity/consent.html", {"form": form, "version": version})


def about(request):
    """Screen 4: birth date (identity store), sex and smoking (research store)."""
    if not request.user.is_authenticated:
        return redirect("signin")
    if not ConsentRecord.has_active(request.user):
        return redirect("consent")
    if PersonLink.objects.filter(account=request.user).exists():
        return redirect("add_report")
    form = AboutForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        with transaction.atomic():
            link = PersonLink.objects.create(
                account=request.user, birth_date_encrypted=encrypt(data["birth_date"].isoformat()))
            Participant.objects.create(participant_id=link.participant_id,
                                       birth_year=data["birth_date"].year,
                                       sex=data["sex"], smoking=data["smoking"])
            AuditLog.record(request.user, "about_saved")
        return redirect("add_report")
    return render(request, "identity/about.html", {"form": form})


def my_data(request):
    """Screen 11: download, change consent, withdraw, delete."""
    if not request.user.is_authenticated:
        return redirect("signin")
    link = PersonLink.objects.filter(account=request.user).first()
    tests = records.tests_for(link).count() if link else 0
    participant = link and Participant.objects.get(pk=link.participant_id)
    months = participant.band_months.count() if link else 0
    dna = participant.dna_tests.count() if link else 0
    return render(request, "identity/my_data.html", {
        "link": link, "tests": tests, "months": months, "dna": dna,
        "in_study": ConsentRecord.has_active(request.user),
        "recontact": ConsentRecord.has_active(request.user, "recontact"),
    })


def download_my_data(request):
    if not request.user.is_authenticated:
        return redirect("signin")
    AuditLog.record(request.user, "data_downloaded")
    body = json.dumps(records.export(request.user), indent=2, ensure_ascii=False)
    response = HttpResponse(body, content_type="application/json; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="vitalage-my-data.json"'
    return response


@require_POST
def change_recontact(request):
    """Turn the optional "contact me about follow-up" consent on or off."""
    if not request.user.is_authenticated:
        return redirect("signin")
    want = request.POST.get("recontact") == "on"
    has = ConsentRecord.has_active(request.user, "recontact")
    if want and not has:
        version = ConsentVersion.current(request.user.language) or ConsentVersion.current("en")
        ConsentRecord.objects.create(account=request.user, consent_version=version,
                                     purpose="recontact")
        AuditLog.record(request.user, "consent_granted", "recontact")
    elif has and not want:
        ConsentRecord.objects.filter(account=request.user, purpose="recontact",
                                     withdrawn_at__isnull=True).update(withdrawn_at=timezone.now())
        AuditLog.record(request.user, "consent_withdrawn", "recontact")
    messages.success(request, translation.gettext("Your choice is saved."))
    return redirect("my_data")


def withdraw(request):
    """Asks once, then deletes the research data and signs the person out."""
    if not request.user.is_authenticated:
        return redirect("signin")
    if request.method == "POST":
        privacy.withdraw(request.user)
        logout(request)
        return render(request, "identity/left.html", {"deleted_account": False})
    return render(request, "identity/confirm_leave.html", {"delete_account": False})


def delete_account(request):
    if not request.user.is_authenticated:
        return redirect("signin")
    if request.method == "POST":
        privacy.delete_account(request.user)
        logout(request)
        return render(request, "identity/left.html", {"deleted_account": True})
    return render(request, "identity/confirm_leave.html", {"delete_account": True})
