"""Email the 12-month repeat reminder to everyone who is due.

    python app/manage.py send_reminders            # send
    python app/manage.py send_reminders --dry-run  # only count who is due

Run it once a day (see app/README.md). Someone gets the reminder once, from
30 days before their repeat is due, if they are still in the study, agreed to
be contacted, and have not done the repeat yet.
"""

from datetime import date, timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.urls import reverse

from core import records
from identity.emails import send_followup_reminder
from identity.models import AuditLog, ConsentRecord, PersonLink, Reminder

KIND = "followup_12m"


def due_for_reminder(today=None):
    """[(account, due date)] for everyone who should get the reminder today."""
    today = today or date.today()
    out = []
    links = (PersonLink.objects.select_related("account")
             .filter(account__is_active=True).exclude(anchor_date_encrypted=""))
    for link in links:
        account = link.account
        if Reminder.objects.filter(account=account, kind=KIND).exists():
            continue
        if not (ConsentRecord.has_active(account) and ConsentRecord.has_active(account, "recontact")):
            continue
        status = records.pilot_status(link)
        due = status["followup_due"]
        if due is None or status["followup"]["blood"] is not None:
            continue
        if today >= due - timedelta(days=records.REMIND_DAYS_BEFORE):
            out.append((account, due))
    return out


class Command(BaseCommand):
    help = "Email the 12-month repeat reminder to participants who are due."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Count only; send nothing.")

    def handle(self, dry_run=False, **options):
        due = due_for_reminder()
        if dry_run:
            self.stdout.write("%d participant(s) due for a reminder." % len(due))
            return
        link = settings.VITALAGE_SITE_URL.rstrip("/") + reverse("signin")
        for account, day in due:
            send_followup_reminder(account.email, day, link, account.language)
            Reminder.objects.create(account=account, kind=KIND)
            AuditLog.record(account, "reminder_sent", KIND)
        self.stdout.write(self.style.SUCCESS("Sent %d reminder(s)." % len(due)))
