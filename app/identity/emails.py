"""The two emails the app sends. Which service sends them is set in settings
(EMAIL_HOST and friends); with nothing set, emails are printed in the terminal."""

from django.conf import settings
from django.core.mail import send_mail
from django.utils import translation
from django.utils.translation import gettext as _

from .models import CODE_MINUTES, INVITE_DAYS


def send_invite(email, link, language="en"):
    with translation.override(language):
        subject = _("Your invitation to the VitalAge pilot study")
        body = _(
            "You have been invited to the VitalAge pilot study.\n\n"
            "Open this personal link on your phone to read about the study and decide "
            "whether to take part:\n\n%(link)s\n\n"
            "The link works once and expires in %(days)d days. Please do not forward it.\n\n"
            "VitalAge is not a diagnostic tool."
        ) % {"link": link, "days": INVITE_DAYS}
    send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [email])


def send_code(email, code, language="en"):
    with translation.override(language):
        subject = _("Your VitalAge sign-in code: %(code)s") % {"code": code}
        body = _(
            "Your sign-in code is %(code)s\n\n"
            "It works for %(minutes)d minutes. If you did not ask for it, you can ignore this email."
        ) % {"code": code, "minutes": CODE_MINUTES}
    send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [email])
