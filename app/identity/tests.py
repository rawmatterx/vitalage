"""Tests for invites, sign-in codes, consent and About you. Run from the repo folder with:

    DJANGO_DEBUG=1 python app/manage.py test identity
"""

import re
from datetime import timedelta
from io import StringIO

from django.core import mail
from django.core.management import call_command
from django.db import connection
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from research.models import Participant

from .models import (CODE_ATTEMPTS, Account, AuditLog, ConsentRecord, ConsentVersion, Invite,
                     PersonLink, SignInCode)


def code_from_last_email():
    return re.search(r"\b(\d{6})\b", mail.outbox[-1].body).group(1)


class InviteTests(TestCase):
    def test_invite_command_emails_a_working_link(self):
        call_command("invite", "Person@Example.com", stdout=StringIO())
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["Person@Example.com"])
        path = re.search(r"https?://[^/\s]+(/join/\S+/)", mail.outbox[0].body).group(1)
        self.assertEqual(self.client.get(path).status_code, 200)

    def test_start_signs_the_person_in_and_goes_to_consent(self):
        _invite, token = Invite.create("p@example.com")
        response = self.client.post(reverse("welcome", args=[token]))
        self.assertRedirects(response, reverse("consent"))
        account = Account.objects.for_email("P@example.com ")
        self.assertIsNotNone(account)
        self.assertEqual(int(self.client.session["_auth_user_id"]), account.pk)

    def test_a_link_works_only_once(self):
        _invite, token = Invite.create("p@example.com")
        self.client.post(reverse("welcome", args=[token]))
        self.client.logout()
        self.assertEqual(self.client.get(reverse("welcome", args=[token])).status_code, 404)

    def test_an_old_link_does_not_work(self):
        invite, token = Invite.create("p@example.com")
        invite.expires_at = timezone.now() - timedelta(minutes=1)
        invite.save()
        response = self.client.get(reverse("welcome", args=[token]))
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "does not work", status_code=404)

    def test_a_made_up_link_does_not_work(self):
        self.assertEqual(self.client.get(reverse("welcome", args=["nonsense"])).status_code, 404)

    def test_bengali_invite_sets_the_language(self):
        _invite, token = Invite.create("p@example.com", language="bn")
        response = self.client.get(reverse("welcome", args=[token]))
        self.assertEqual(response.cookies["django_language"].value, "bn")
        self.assertContains(response, 'lang="bn"')

    def test_email_is_not_stored_in_plain_text(self):
        Invite.create("secret.person@example.com")
        Account.objects.create_user("secret.person@example.com")
        with connection.cursor() as cursor:
            for table in ("identity_invite", "identity_account"):
                cursor.execute("SELECT * FROM %s" % table)
                self.assertNotIn("secret.person", str(cursor.fetchall()))


class SignInTests(TestCase):
    def setUp(self):
        self.account = Account.objects.create_user("p@example.com")

    def ask_for_code(self, email="p@example.com"):
        return self.client.post(reverse("signin"), {"email": email})

    def test_right_code_signs_in(self):
        self.ask_for_code()
        response = self.client.post(reverse("signin_code"), {"code": code_from_last_email()})
        self.assertRedirects(response, reverse("consent"))
        self.assertTrue(AuditLog.objects.filter(action="signin", actor=self.account).exists())

    def test_wrong_code_does_not(self):
        self.ask_for_code()
        good = code_from_last_email()
        bad = "%06d" % ((int(good) + 1) % 1_000_000)
        response = self.client.post(reverse("signin_code"), {"code": bad})
        self.assertContains(response, "That code did not work")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_code_stops_working_after_too_many_tries(self):
        self.ask_for_code()
        good = code_from_last_email()
        bad = "%06d" % ((int(good) + 1) % 1_000_000)
        for _ in range(CODE_ATTEMPTS):
            self.client.post(reverse("signin_code"), {"code": bad})
        response = self.client.post(reverse("signin_code"), {"code": good})
        self.assertContains(response, "That code did not work")

    def test_a_code_works_once(self):
        self.ask_for_code()
        code = code_from_last_email()
        self.assertTrue(SignInCode.verify(self.account, code))
        self.assertFalse(SignInCode.verify(self.account, code))

    def test_unknown_email_looks_the_same(self):
        known = self.ask_for_code("p@example.com")
        unknown = self.ask_for_code("stranger@example.com")
        self.assertEqual(known.status_code, unknown.status_code)
        self.assertEqual(known["Location"], unknown["Location"])
        self.assertEqual(len(mail.outbox), 1)   # only the real participant gets an email

    def test_too_many_code_requests(self):
        for _ in range(8):
            self.ask_for_code()
        self.assertEqual(len(mail.outbox), 5)


class ConsentAndAboutTests(TestCase):
    def setUp(self):
        self.account = Account.objects.create_user("p@example.com")
        self.client.force_login(self.account)

    def test_draft_text_is_shown_with_a_warning(self):
        response = self.client.get(reverse("consent"))
        self.assertContains(response, "Draft wording")
        self.assertContains(response, "VitalAge pilot study: information and consent")

    def test_bengali_text_is_shown_in_bengali(self):
        self.client.cookies["django_language"] = "bn"
        response = self.client.get(reverse("consent"))
        self.assertContains(response, ConsentVersion.current("bn").title)

    def test_must_agree_to_take_part(self):
        response = self.client.post(reverse("consent"), {})
        self.assertContains(response, "You need to agree")
        self.assertFalse(ConsentRecord.objects.exists())

    def test_two_separate_choices_are_recorded(self):
        response = self.client.post(reverse("consent"), {"pilot_research": "on"})
        self.assertRedirects(response, reverse("about"))
        purposes = list(ConsentRecord.objects.values_list("purpose", flat=True))
        self.assertEqual(purposes, ["pilot_research"])
        record = ConsentRecord.objects.get()
        self.assertEqual(record.consent_version.version, "0.1-draft")

    def test_about_you_splits_the_data(self):
        self.client.post(reverse("consent"), {"pilot_research": "on", "recontact": "on"})
        response = self.client.post(reverse("about"), {
            "birth_date": "1968-03-15", "sex": "female", "smoking": "never"})
        self.assertRedirects(response, reverse("add_report"))
        link = PersonLink.objects.get(account=self.account)
        self.assertEqual(link.birth_date.isoformat(), "1968-03-15")
        self.assertNotIn("1968", link.birth_date_encrypted)
        person = Participant.objects.get(participant_id=link.participant_id)
        self.assertEqual((person.birth_year, person.sex, person.smoking), (1968, "female", "never"))

    def test_research_store_holds_no_email_or_dates(self):
        self.client.post(reverse("consent"), {"pilot_research": "on"})
        self.client.post(reverse("about"), {"birth_date": "1968-03-15", "sex": "male",
                                            "smoking": "former"})
        fields = {f.name for f in Participant._meta.get_fields()}
        self.assertFalse(fields & {"email", "email_hash", "birth_date", "account", "name"})
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM research_participant")
            row = str(cursor.fetchall())
        self.assertNotIn("example.com", row)
        self.assertNotIn("1968-03-15", row)

    def test_under_18_is_refused(self):
        self.client.post(reverse("consent"), {"pilot_research": "on"})
        year = timezone.now().year - 10
        response = self.client.post(reverse("about"), {"birth_date": "%d-01-01" % year,
                                                       "sex": "male", "smoking": "never"})
        self.assertContains(response, "18 or older")
        self.assertFalse(Participant.objects.exists())

    def test_missing_consent_text_shows_a_holding_page(self):
        ConsentVersion.objects.all().delete()
        response = self.client.get(reverse("consent"))
        self.assertEqual(response.status_code, 503)


class TranslationTests(TestCase):
    def test_bengali_screens_are_in_bengali(self):
        self.client.cookies["django_language"] = "bn"
        response = self.client.get(reverse("signin"))
        self.assertContains(response, "সাইন ইন")
        self.assertNotContains(response, "There is no password")

    def test_bengali_invite_email(self):
        call_command("invite", "p@example.com", "--lang", "bn", stdout=StringIO())
        self.assertIn("আমন্ত্রণ", mail.outbox[0].subject)

    def test_every_screen_text_has_a_bengali_version(self):
        """Catches new English text that was added without a Bengali line."""
        from pathlib import Path
        try:
            import polib
        except ImportError:
            self.skipTest("pip install -r app/requirements-dev.txt")
        app = Path(__file__).resolve().parent.parent
        po = polib.pofile(str(app / "locale/bn/LC_MESSAGES/django.po"))
        done = {e.msgid for e in po.translated_entries()}
        found = set()
        for path in app.glob("identity/templates/**/*.html"):
            found |= set(re.findall(r'{% translate "([^"]+)"', path.read_text()))
        for path in [app / "core/templates/core/base.html", app / "core/templates/core/home.html"]:
            found |= set(re.findall(r'{% translate "([^"]+)"', path.read_text()))
        for path in [app / "identity/forms.py"]:
            found |= set(re.findall(r'_\("([^"]+)"\)', path.read_text()))
        self.assertEqual(found - done, set())
