"""Tests for the web app. Run from the repo folder with:

    DJANGO_DEBUG=1 python app/manage.py test core
"""

from datetime import date
from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile

from django.test import TestCase
from django.urls import reverse

from core.views import EXAMPLE_REPORT, example_result
from identity.crypto import encrypt
from identity.models import Account, ConsentRecord, ConsentVersion, PersonLink
from research.models import BandMonth, BloodMarker, BloodTest, Participant, Result


def form_data(report=EXAMPLE_REPORT, test_date="2026-11-01", **extra):
    """The POST data the Add report form sends for a report."""
    data = {"test_date": test_date, "fasting": "yes"}
    for marker, (value, unit) in report.items():
        data["v_" + marker] = value
        data["u_" + marker] = unit
    data.update(extra)
    return data


# Born so that they are exactly 58.0 on the example test date, 2026-11-01.
BORN = date(1968, 11, 1)


def make_participant(email="p@example.com", born=BORN, sex="male"):
    """An account that has given consent and filled in About you."""
    account = Account.objects.create_user(email)
    ConsentRecord.objects.create(account=account, purpose="pilot_research",
                                 consent_version=ConsentVersion.current("en"))
    link = PersonLink.objects.create(account=account, birth_date_encrypted=encrypt(born.isoformat()))
    Participant.objects.create(participant_id=link.participant_id, birth_year=born.year,
                               sex=sex, smoking="never")
    return account


class ParticipantTestCase(TestCase):
    """The report pages are for signed-in participants only."""
    def setUp(self):
        self.account = make_participant()
        self.client.force_login(self.account)


class HomePageTests(TestCase):
    def test_home_page_loads(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sign in")
        self.assertContains(response, "invite email")

    def test_home_page_shows_the_science_result(self):
        # The README example: age 58 gives internal age 61.8 (+3.8 years).
        result = example_result()
        self.assertEqual(result["internal_age"], 61.8)
        self.assertEqual(result["gap"], 3.8)
        response = self.client.get(reverse("home"))
        self.assertContains(response, "61.8")
        self.assertContains(response, "+3.8 yrs")

    def test_health_check(self):
        response = self.client.get(reverse("health"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})


class AddReportTests(ParticipantTestCase):
    def test_form_shows_all_nine_markers(self):
        response = self.client.get(reverse("add_report"))
        self.assertEqual(response.status_code, 200)
        for marker in EXAMPLE_REPORT:
            self.assertContains(response, 'name="v_%s"' % marker)
        self.assertContains(response, "never uploaded")

    def test_age_comes_from_the_birth_date(self):
        response = self.client.get(reverse("add_report"))
        self.assertNotContains(response, 'name="age"')
        response = self.client.post(reverse("review"), form_data())
        self.assertContains(response, "at age 58.0")

    def test_edit_values_puts_them_back_in_the_form(self):
        response = self.client.post(reverse("add_report"), form_data())
        self.assertContains(response, 'value="8400')


class ReviewTests(ParticipantTestCase):
    def test_shows_values_as_entered_with_flags(self):
        response = self.client.post(reverse("review"), form_data())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Check your values")
        self.assertContains(response, "112 mg/dL")     # glucose above the usual 70-100
        self.assertContains(response, '<span class="flag">high</span>', html=False)

    def test_wrong_unit_goes_back_to_the_form(self):
        # Albumin 4.1 g/L is impossible (it means 4.1 g/dL was meant).
        data = form_data(u_albumin="g/L")
        response = self.client.post(reverse("review"), data)
        self.assertContains(response, "Add a blood report")
        self.assertContains(response, "too high or too low for g/L")

    def test_too_many_missing_markers(self):
        report = {m: EXAMPLE_REPORT[m] for m in list(EXAMPLE_REPORT)[:5]}
        response = self.client.post(reverse("review"), form_data(report))
        self.assertContains(response, "at least 6 of the 9 markers")

    def test_test_date_is_required(self):
        response = self.client.post(reverse("review"), form_data(test_date=""))
        self.assertContains(response, "Enter the date of the blood test")

    def test_future_test_date_is_refused(self):
        response = self.client.post(reverse("review"), form_data(test_date="2999-01-01"))
        self.assertContains(response, "cannot be in the future")

    def test_non_fasting_warning(self):
        response = self.client.post(reverse("review"), form_data(fasting="no"))
        self.assertContains(response, "non-fasting")

    def test_get_is_not_allowed(self):
        self.assertEqual(self.client.get(reverse("review")).status_code, 405)


class SaveAndResultTests(ParticipantTestCase):
    def save(self, **kwargs):
        response = self.client.post(reverse("save_report"), form_data(**kwargs))
        return response, BloodTest.objects.order_by("-id").first()

    def test_full_report_matches_the_command_line(self):
        response, test = self.save()
        self.assertRedirects(response, reverse("result", args=[test.pk]))
        response = self.client.get(reverse("result", args=[test.pk]))
        self.assertContains(response, "61.8")        # internal age
        self.assertContains(response, "+3.8 yrs")    # gap
        self.assertContains(response, "1.18")        # pace estimate
        self.assertContains(response, "What moves your internal age")
        self.assertContains(response, "1 Nov 2026")

    def test_saves_markers_as_printed_and_converted(self):
        _response, test = self.save()
        self.assertTrue(test.complete)
        self.assertEqual(test.age, 58.0)
        glucose = test.markers.get(marker="glucose")
        self.assertEqual((glucose.value_as_printed, glucose.unit_as_printed), (112, "mg/dL"))
        self.assertAlmostEqual(glucose.value_canonical, 112 / 18.016, places=2)
        self.assertAlmostEqual(test.result.internal_age, 61.8, places=1)

    def test_first_test_is_day_zero_and_later_tests_count_days(self):
        _r, first = self.save()
        _r, second = self.save(test_date="2026-11-11")
        self.assertEqual((first.day_offset, second.day_offset), (0, 10))
        link = PersonLink.objects.get(account=self.account)
        self.assertEqual(link.anchor_date, date(2026, 11, 1))
        self.assertNotIn("2026", link.anchor_date_encrypted)

    def test_sending_twice_saves_once(self):
        self.save()
        self.save()
        self.assertEqual(BloodTest.objects.count(), 1)

    def test_missing_markers_give_a_range(self):
        report = dict(EXAMPLE_REPORT)
        del report["crp"]
        _r, test = self.save(report=report)
        self.assertFalse(test.complete)
        response = self.client.get(reverse("result", args=[test.pk]))
        self.assertContains(response, "Internal age, as a range")
        self.assertContains(response, "CRP (hs-CRP)")
        self.assertNotContains(response, "What moves your internal age")

    def test_bad_values_are_checked_again(self):
        # Someone could skip the review page; saving must re-check.
        response = self.client.post(reverse("save_report"), form_data(u_albumin="g/L"))
        self.assertContains(response, "Add a blood report")
        self.assertFalse(BloodTest.objects.exists())

    def test_research_store_has_no_calendar_dates(self):
        from django.db import models
        for model in (Participant, BloodTest, BloodMarker, Result, BandMonth):
            for f in model._meta.get_fields():
                self.assertNotIsInstance(f, (models.DateField, models.DateTimeField),
                                         "%s.%s" % (model.__name__, f.name))

    def test_nobody_else_can_see_a_result(self):
        _r, test = self.save()
        self.client.force_login(make_participant("other@example.com"))
        self.assertEqual(self.client.get(reverse("result", args=[test.pk])).status_code, 404)
        self.client.post(reverse("delete_report", args=[test.pk]))
        self.assertTrue(BloodTest.objects.filter(pk=test.pk).exists())

    def test_delete_a_report(self):
        _r, test = self.save()
        self.client.post(reverse("delete_report", args=[test.pk]))
        self.assertFalse(BloodTest.objects.exists())
        self.assertFalse(BloodMarker.objects.exists())


class HistoryTests(ParticipantTestCase):
    def add(self, day):
        self.client.post(reverse("save_report"), form_data(test_date=day))

    def test_empty_history(self):
        response = self.client.get(reverse("history"))
        self.assertContains(response, "No blood reports saved yet")

    def test_pace_unlocks_after_three_tests_over_a_year(self):
        self.add("2025-01-10")
        self.add("2025-07-10")
        response = self.client.get(reverse("history"))
        self.assertContains(response, "1 more full test to unlock it")
        self.add("2026-02-10")
        response = self.client.get(reverse("history"))
        self.assertContains(response, "from 3 full tests over 1.1 years")
        self.assertContains(response, "10 Jan 2025")


SAMPLE_BAND = (Path(__file__).resolve().parents[2] / "examples" / "band_sample.csv")


class BandTests(ParticipantTestCase):
    def upload(self, content=None, device="Fitbit Charge 6"):
        content = content if content is not None else SAMPLE_BAND.read_bytes()
        return self.client.post(reverse("band"), {
            "file": SimpleUploadedFile("band.csv", content, content_type="text/csv"),
            "device_model": device})

    def test_needs_a_blood_test_first(self):
        self.assertContains(self.client.get(reverse("band")), "Add a blood report first")

    def test_upload_keeps_only_monthly_medians(self):
        self.client.post(reverse("save_report"), form_data(test_date="2026-10-15"))
        response = self.upload()
        self.assertContains(response, "Fitness Age")
        months = list(BandMonth.objects.all())
        self.assertTrue(months)
        # 35 days in the file; 2 are non-wear days (120 steps) and are dropped.
        self.assertEqual(sum(m.steps_days for m in months), 33)
        self.assertEqual(months[0].device_model, "Fitbit Charge 6")
        # Uploading the same file again replaces, not duplicates.
        self.upload()
        self.assertEqual(BandMonth.objects.count(), len(months))

    def test_vitalage_appears_when_band_covers_the_test(self):
        self.client.post(reverse("save_report"), form_data(test_date="2026-10-15"))
        self.upload()
        response = self.client.get(reverse("history"))
        self.assertNotContains(response, "needs band data")

    def test_bad_file(self):
        self.client.post(reverse("save_report"), form_data())
        response = self.upload(b"day,steps\nyesterday,100\n")
        self.assertContains(response, "Could not read this file")
        self.assertFalse(BandMonth.objects.exists())


class ReportPagesNeedSignInTests(TestCase):
    def test_signed_out_people_go_to_sign_in(self):
        for name in ("add_report", "review", "save_report", "history", "band"):
            response = self.client.post(reverse(name), form_data())
            self.assertRedirects(response, reverse("signin"))

    def test_without_consent_people_go_to_consent(self):
        self.client.force_login(Account.objects.create_user("new@example.com"))
        self.assertRedirects(self.client.get(reverse("add_report")), reverse("consent"))
