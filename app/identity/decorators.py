"""Page guards: each page says what a person must have done before seeing it."""

from functools import wraps

from django.shortcuts import redirect

from .models import ConsentRecord, PersonLink


def participant_required(view):
    """Signed in, consent given, and About you filled in, in that order."""
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("signin")
        if not ConsentRecord.has_active(request.user):
            return redirect("consent")
        if not PersonLink.objects.filter(account=request.user).exists():
            return redirect("about")
        return view(request, *args, **kwargs)
    return wrapper


def is_coordinator(account):
    return account.is_authenticated and (account.role in ("coordinator", "admin") or account.is_superuser)


def coordinator_required(view):
    """The study coordinator (or an admin). Everyone else gets a 404, so the
    page does not even admit it exists."""
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("signin")
        if not is_coordinator(request.user):
            from django.http import Http404
            raise Http404
        return view(request, *args, **kwargs)
    return wrapper


def next_step(account):
    """Where someone who just signed in should go."""
    if account.role in ("coordinator", "admin"):
        return "dashboard"
    if not ConsentRecord.has_active(account):
        return "consent"
    if not PersonLink.objects.filter(account=account).exists():
        return "about"
    return "history"
