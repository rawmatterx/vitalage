"""Tests for the coordinator dashboard and export. Run from the repo folder with:

    DJANGO_DEBUG=1 python app/manage.py test coordinator
"""

import json
from datetime import date
from io import StringIO

from django.core import mail
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from core.tests import BORN, EXAMPLE_REPORT, form_data, make_participant
from identity.models import Account, AuditLog, Invite, PersonLink
from phenoage.pilot import build_record


class CoordinatorTestCase(TestCase):
    def setUp(self):
        call_command("createcoordinator", "lead@example.com", stdout=StringIO())
        self.coordinator = Account.objects.for_email("lead@example.com")
        self.person = make_participant()
        self.client.force_login(self.person)
        self.client.post(reverse("save_report"), form_data())
        self.client.post(reverse("save_report"), form_data(test_date="2026-11-11"))
        self.client.post(reverse("dna"), {"test_date": "2026-11-05", "vendor": "TruDiagnostic",
                                          "clock": "DunedinPACE", "value": 0.92})
        self.client.force_login(self.coordinator)
        self.code = str(PersonLink.objects.get(account=self.person).participant_id)


class AccessTests(CoordinatorTestCase):
    def test_participants_cannot_open_the_coordinator_pages(self):
        self.client.force_login(self.person)
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 404)
        self.assertEqual(self.client.post(reverse("export")).status_code, 404)

    def test_signed_out_people_go_to_sign_in(self):
        self.client.logout()
        self.assertRedirects(self.client.get(reverse("dashboard")), reverse("signin"))

    def test_coordinator_lands_on_the_dashboard_after_sign_in(self):
        self.client.logout()
        self.client.post(reverse("signin"), {"email": "lead@example.com"})
        import re
        code = re.search(r"\b(\d{6})\b", mail.outbox[-1].body).group(1)
        response = self.client.post(reverse("signin_code"), {"code": code})
        self.assertRedirects(response, reverse("dashboard"))


class DashboardTests(CoordinatorTestCase):
    def test_shows_codes_and_steps_but_no_health_values_or_emails(self):
        response = self.client.get(reverse("dashboard"))
        self.assertContains(response, self.code[:8])
        self.assertContains(response, "Band 0/30")
        self.assertContains(response, "due Nov 2027")
        self.assertNotContains(response, "p@example.com")
        self.assertNotContains(response, "61.8")       # internal age
        self.assertNotContains(response, "0.92")       # DNA value

    def test_invite_from_the_dashboard(self):
        response = self.client.post(reverse("dashboard"), {"email": "new@example.com", "language": "bn"})
        self.assertRedirects(response, reverse("dashboard"))
        self.assertEqual(mail.outbox[-1].to, ["new@example.com"])
        invite = Invite.objects.get()
        self.assertEqual((invite.language, invite.created_by), ("bn", self.coordinator))
        self.assertContains(self.client.get(reverse("dashboard")), "1 link not used yet")


class ExportTests(CoordinatorTestCase):
    def download(self):
        response = self.client.post(reverse("export"))
        self.assertEqual(response.status_code, 200)
        return json.loads(response.content)

    def test_matches_the_command_line_pilot_record(self):
        data = self.download()
        self.assertEqual(len(data), 1)
        rec = data[0]
        expected = build_record(BORN, "male", "never",
                                [(date(2026, 11, 1), EXAMPLE_REPORT), (date(2026, 11, 11), EXAMPLE_REPORT)],
                                dna=[{"date": date(2026, 11, 5), "vendor": "TruDiagnostic",
                                      "clock": "DunedinPACE", "value": 0.92}])
        self.assertEqual(set(rec), set(expected))
        self.assertEqual(rec["schema"], "vitalage-pilot-v1")
        self.assertEqual(rec["participant_id"], self.code)
        for got, want in zip(rec["blood_tests"], expected["blood_tests"]):
            self.assertEqual(got["days_from_first"], want["days_from_first"])
            self.assertEqual(got["markers"], want["markers"])
            self.assertAlmostEqual(got["phenoage"], want["phenoage"], places=1)
            self.assertAlmostEqual(got["internal_age"], want["internal_age"], places=1)
        self.assertEqual(rec["dna_tests"], expected["dna_tests"])

    def test_no_identity_or_dates_in_the_file(self):
        body = self.client.post(reverse("export")).content.decode()
        for text in ("p@example.com", BORN.isoformat(), "2026-11-01", "2026-11-11", "2026-11-05"):
            self.assertNotIn(text, body)

    def test_every_download_is_logged(self):
        self.download()
        entry = AuditLog.objects.get(action="export_downloaded")
        self.assertEqual((entry.actor, entry.target), (self.coordinator, "1 records"))
        self.assertContains(self.client.get(reverse("export")), "1 records")

    def test_withdrawn_people_are_not_exported(self):
        self.client.force_login(self.person)
        self.client.post(reverse("withdraw"))
        self.client.force_login(self.coordinator)
        self.assertEqual(self.download(), [])
