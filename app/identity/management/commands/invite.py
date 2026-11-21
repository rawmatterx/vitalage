"""Invite one participant by email.

    python app/manage.py invite person@example.com
    python app/manage.py invite person@example.com --lang bn

The coordinator screen (milestone 6) will do the same from a web page.
"""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_email
from django.urls import reverse

from identity.emails import send_invite
from identity.models import AuditLog, Invite


class Command(BaseCommand):
    help = "Email a personal invite link to one pilot participant."

    def add_arguments(self, parser):
        parser.add_argument("email")
        parser.add_argument("--lang", choices=[c for c, _n in settings.LANGUAGES], default="en",
                            help="Language of the email and first screens (en or bn).")

    def handle(self, email, lang, **options):
        try:
            validate_email(email)
        except Exception:
            raise CommandError("That does not look like an email address.")
        invite, token = Invite.create(email, language=lang)
        link = settings.VITALAGE_SITE_URL.rstrip("/") + reverse("welcome", args=[token])
        send_invite(email, link, lang)
        AuditLog.record(None, "invite_created", "invite #%s" % invite.pk)
        self.stdout.write(self.style.SUCCESS("Invite #%s sent." % invite.pk))
        if settings.DEBUG:
            self.stdout.write("Link (shown only on a laptop): %s" % link)
