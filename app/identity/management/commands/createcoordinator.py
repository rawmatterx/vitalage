"""Make (or promote) the study coordinator account. They sign in like
participants, with a code emailed to them, and see the dashboard.

    python app/manage.py createcoordinator you@example.com
"""

from django.core.management.base import BaseCommand
from django.core.validators import validate_email

from identity.models import Account, AuditLog


class Command(BaseCommand):
    help = "Create the study coordinator account, or make an existing account one."

    def add_arguments(self, parser):
        parser.add_argument("email")

    def handle(self, email, **options):
        validate_email(email)
        account = Account.objects.for_email(email)
        if account is None:
            account = Account.objects.create_user(email, role="coordinator")
        else:
            account.role = "coordinator"
            account.save(update_fields=["role"])
        AuditLog.record(account, "coordinator_set")
        self.stdout.write(self.style.SUCCESS(
            "Coordinator account ready. Sign in at /signin/ with this email."))
