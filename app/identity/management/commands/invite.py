"""Invite one participant by email.

    python app/manage.py invite person@example.com
    python app/manage.py invite person@example.com --lang bn

The coordinator dashboard (/coordinator/) does the same from a web page.
"""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_email
from identity.emails import invite_person


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
        invite, link = invite_person(email, lang)
        self.stdout.write(self.style.SUCCESS("Invite #%s sent." % invite.pk))
        if settings.DEBUG:
            self.stdout.write("Link (shown only on a laptop): %s" % link)
