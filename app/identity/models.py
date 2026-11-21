"""The identity store: who a person is and what they agreed to.

Nothing about blood, band or DNA lives here. The only bridge to the research
store is PersonLink, which maps an account to a random participant ID.
Emails and birth dates are kept encrypted (see crypto.py).
"""

import secrets
import uuid
from datetime import timedelta

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone

from .crypto import decrypt, encrypt, lookup_hash, normalise_email, secret_hash

INVITE_DAYS = 7          # an invite link works for this long (guess; easy to change)
CODE_MINUTES = 10        # a sign-in code works for this long
CODE_ATTEMPTS = 5        # wrong guesses allowed per code
CODES_PER_HOUR = 5       # codes one account can ask for in an hour


class AccountManager(BaseUserManager):
    def for_email(self, email):
        return self.filter(email_hash=lookup_hash(email)).first()

    def create_user(self, email, password=None, role="participant", **extra):
        account = self.model(email_hash=lookup_hash(email),
                             email_encrypted=encrypt(normalise_email(email)), role=role, **extra)
        if password:
            account.set_password(password)
        else:
            account.set_unusable_password()   # participants sign in with emailed codes
        account.save(using=self._db)
        return account

    def create_superuser(self, email, password, **extra):
        return self.create_user(email, password, role="admin", is_staff=True,
                                is_superuser=True, **extra)


class Account(AbstractBaseUser, PermissionsMixin):
    ROLES = [("participant", "Participant"), ("coordinator", "Study coordinator"),
             ("admin", "Admin")]

    email_hash = models.CharField(max_length=64, unique=True)
    email_encrypted = models.TextField()
    role = models.CharField(max_length=20, choices=ROLES, default="participant")
    language = models.CharField(max_length=5, default="en")
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)   # may open the admin pages
    created_at = models.DateTimeField(default=timezone.now)

    objects = AccountManager()
    USERNAME_FIELD = "email_hash"

    @property
    def email(self):
        return decrypt(self.email_encrypted) if self.email_encrypted else ""

    def __str__(self):
        return "%s #%s" % (self.get_role_display(), self.pk)


class Invite(models.Model):
    """A personal link the coordinator emails to one participant."""
    email_hash = models.CharField(max_length=64, db_index=True)
    email_encrypted = models.TextField()
    token_hash = models.CharField(max_length=64, unique=True)
    language = models.CharField(max_length=5, default="en")
    created_by = models.ForeignKey(Account, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="invites_sent")
    created_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)

    @classmethod
    def create(cls, email, language="en", created_by=None):
        """Returns (invite, token). The token is only ever in the emailed link."""
        token = secrets.token_urlsafe(32)
        invite = cls.objects.create(
            email_hash=lookup_hash(email), email_encrypted=encrypt(normalise_email(email)),
            token_hash=secret_hash(token), language=language, created_by=created_by,
            expires_at=timezone.now() + timedelta(days=INVITE_DAYS))
        return invite, token

    @classmethod
    def find_valid(cls, token):
        invite = cls.objects.filter(token_hash=secret_hash(token)).first()
        if invite and invite.used_at is None and invite.expires_at > timezone.now():
            return invite
        return None

    @property
    def email(self):
        return decrypt(self.email_encrypted)


class SignInCode(models.Model):
    """A 6-digit code emailed to someone who wants to sign in."""
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name="codes")
    code_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    used_at = models.DateTimeField(null=True, blank=True)

    @classmethod
    def issue(cls, account):
        """Returns the code to email, or None if too many were asked for recently."""
        hour_ago = timezone.now() - timedelta(hours=1)
        if cls.objects.filter(account=account, created_at__gte=hour_ago).count() >= CODES_PER_HOUR:
            return None
        code = "%06d" % secrets.randbelow(1_000_000)
        cls.objects.create(account=account, code_hash=secret_hash("%s:%s" % (account.pk, code)),
                           expires_at=timezone.now() + timedelta(minutes=CODE_MINUTES))
        return code

    @classmethod
    def verify(cls, account, code):
        """True if `code` is the latest live code for this account; uses it up."""
        latest = cls.objects.filter(account=account, used_at__isnull=True,
                                    expires_at__gt=timezone.now()).order_by("-created_at").first()
        if latest is None or latest.attempts >= CODE_ATTEMPTS:
            return False
        if secrets.compare_digest(latest.code_hash, secret_hash("%s:%s" % (account.pk, code.strip()))):
            latest.used_at = timezone.now()
            latest.save(update_fields=["used_at"])
            return True
        latest.attempts += 1
        latest.save(update_fields=["attempts"])
        return False


class ConsentVersion(models.Model):
    """One exact wording of the consent form. Never edited: a change is a new row."""
    version = models.CharField(max_length=20)
    language = models.CharField(max_length=5)
    title = models.CharField(max_length=200)
    summary = models.TextField(help_text="Short points shown first, one per line.")
    text = models.TextField(help_text="The full consent text.")
    text_hash = models.CharField(max_length=64, editable=False)
    is_draft = models.BooleanField(default=True,
                                   help_text="Draft wording, not yet approved by an ethics committee.")
    ethics_ref = models.CharField(max_length=100, blank=True)
    effective_from = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = [("version", "language")]

    def save(self, *args, **kwargs):
        import hashlib
        self.text_hash = hashlib.sha256((self.summary + "\n" + self.text).encode()).hexdigest()
        super().save(*args, **kwargs)

    @classmethod
    def current(cls, language):
        now = timezone.now()
        qs = cls.objects.filter(effective_from__lte=now).order_by("-effective_from", "-pk")
        return qs.filter(language=language).first() or qs.filter(language="en").first()

    def summary_points(self):
        return [line.strip() for line in self.summary.splitlines() if line.strip()]

    def paragraphs(self):
        return [p.strip() for p in self.text.split("\n\n") if p.strip()]

    def __str__(self):
        return "Consent %s (%s)%s" % (self.version, self.language, " draft" if self.is_draft else "")


class ConsentRecord(models.Model):
    """One yes to one purpose, for one exact consent wording."""
    PURPOSES = [("pilot_research", "Pilot research (required)"),
                ("recontact", "Contact me about follow-up (optional)")]
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="consents")
    consent_version = models.ForeignKey(ConsentVersion, on_delete=models.PROTECT)
    purpose = models.CharField(max_length=30, choices=PURPOSES)
    granted_at = models.DateTimeField(default=timezone.now)
    withdrawn_at = models.DateTimeField(null=True, blank=True)

    @classmethod
    def has_active(cls, account, purpose="pilot_research"):
        return cls.objects.filter(account=account, purpose=purpose, withdrawn_at__isnull=True).exists()


class PersonLink(models.Model):
    """The only bridge between the two stores. Deleting it cuts the link for good."""
    account = models.OneToOneField(Account, on_delete=models.CASCADE, related_name="link")
    participant_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    birth_date_encrypted = models.TextField()
    anchor_date_encrypted = models.TextField(blank=True)   # set at the first saved blood test

    @property
    def birth_date(self):
        from datetime import date
        return date.fromisoformat(decrypt(self.birth_date_encrypted))

    @property
    def anchor_date(self):
        """Day 0 for every date in the research store; None before the first test."""
        from datetime import date
        if not self.anchor_date_encrypted:
            return None
        return date.fromisoformat(decrypt(self.anchor_date_encrypted))

    def set_anchor_date(self, day):
        self.anchor_date_encrypted = encrypt(day.isoformat())
        self.save(update_fields=["anchor_date_encrypted"])


class AuditLog(models.Model):
    """Append-only record of important actions. Holds no health data."""
    actor = models.ForeignKey(Account, null=True, blank=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=50)
    target = models.CharField(max_length=100, blank=True)
    at = models.DateTimeField(default=timezone.now)

    @classmethod
    def record(cls, actor, action, target=""):
        cls.objects.create(actor=actor, action=action, target=str(target))
