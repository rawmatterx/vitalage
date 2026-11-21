"""Withdrawal and account deletion (screen 11).

Withdraw: every research row for the person is deleted, then the PersonLink,
which was the only bridge between the two stores. Consent records stay, with
withdrawn_at filled in, as proof of what was agreed and when; they hold no
health data.

Delete account: withdraw, then wipe the email from the account and its
invites and codes. The account row itself stays (empty, signed out for good)
because the consent records point to it.
"""

import uuid

from django.db import transaction
from django.utils import timezone

from research.models import Participant

from .models import AuditLog, ConsentRecord, Invite, PersonLink, SignInCode


@transaction.atomic
def withdraw(account):
    link = PersonLink.objects.filter(account=account).first()
    if link is not None:
        # Cascades to blood tests, markers, results and band months.
        Participant.objects.filter(pk=link.participant_id).delete()
        link.delete()
    ConsentRecord.objects.filter(account=account, withdrawn_at__isnull=True).update(
        withdrawn_at=timezone.now())
    AuditLog.record(account, "withdrawn", "research data deleted")


@transaction.atomic
def delete_account(account):
    withdraw(account)
    Invite.objects.filter(email_hash=account.email_hash).delete()
    SignInCode.objects.filter(account=account).delete()
    account.email_hash = "deleted-" + uuid.uuid4().hex
    account.email_encrypted = ""
    account.is_active = False
    account.set_unusable_password()
    account.save()
    AuditLog.record(account, "account_deleted")
