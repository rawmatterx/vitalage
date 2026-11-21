"""Make an admin account for the admin pages (/admin/), signed in by email and password.

    python app/manage.py createadmin you@example.com
"""

import getpass

from django.core.management.base import BaseCommand, CommandError

from identity.models import Account


class Command(BaseCommand):
    help = "Create an admin account (email + password)."

    def add_arguments(self, parser):
        parser.add_argument("email")

    def handle(self, email, **options):
        if Account.objects.for_email(email):
            raise CommandError("An account with that email already exists.")
        password = getpass.getpass("Password: ")
        if len(password) < 12 or password != getpass.getpass("Again: "):
            raise CommandError("Passwords must match and be at least 12 characters.")
        Account.objects.create_superuser(email, password)
        self.stdout.write(self.style.SUCCESS("Admin account created."))
