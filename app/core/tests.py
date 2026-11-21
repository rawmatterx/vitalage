"""Tests for the web app. Run from the repo folder with:

    DJANGO_DEBUG=1 python app/manage.py test core
"""

from django.test import TestCase
from django.urls import reverse

from core.views import EXAMPLE_REPORT, example_result


def form_data(report=EXAMPLE_REPORT, age=58, **extra):
    """The POST data the Add report form sends for a report."""
    data = {"age": age, "test_date": "2026-11-01", "fasting": "yes"}
    for marker, (value, unit) in report.items():
        data["v_" + marker] = value
        data["u_" + marker] = unit
    data.update(extra)
    return data


class HomePageTests(TestCase):
    def test_home_page_loads(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Add a blood report")

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


class AddReportTests(TestCase):
    def test_form_shows_all_nine_markers(self):
        response = self.client.get(reverse("add_report"))
        self.assertEqual(response.status_code, 200)
        for marker in EXAMPLE_REPORT:
            self.assertContains(response, 'name="v_%s"' % marker)
        self.assertContains(response, "never uploaded")

    def test_edit_values_puts_them_back_in_the_form(self):
        response = self.client.post(reverse("add_report"), form_data())
        self.assertContains(response, 'value="8400')


class ReviewTests(TestCase):
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

    def test_age_is_required(self):
        response = self.client.post(reverse("review"), form_data(age=""))
        self.assertContains(response, "This field is required")

    def test_non_fasting_warning(self):
        response = self.client.post(reverse("review"), form_data(fasting="no"))
        self.assertContains(response, "non-fasting")

    def test_get_is_not_allowed(self):
        self.assertEqual(self.client.get(reverse("review")).status_code, 405)


class ResultTests(TestCase):
    def test_full_report_matches_the_command_line(self):
        response = self.client.post(reverse("result"), form_data())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "61.8")        # internal age
        self.assertContains(response, "+3.8 yrs")    # gap
        self.assertContains(response, "1.18")        # pace estimate
        self.assertContains(response, "What moves your internal age")

    def test_missing_markers_give_a_range(self):
        report = dict(EXAMPLE_REPORT)
        del report["crp"]
        response = self.client.post(reverse("result"), form_data(report))
        self.assertContains(response, "Internal age, as a range")
        self.assertContains(response, "CRP (hs-CRP)")
        self.assertNotContains(response, "What moves your internal age")

    def test_bad_values_are_checked_again(self):
        # Someone could skip the review page; the result page must re-check.
        response = self.client.post(reverse("result"), form_data(u_albumin="g/L"))
        self.assertContains(response, "Add a blood report")

    def test_nothing_is_saved(self):
        from django.apps import apps
        before = {m: m.objects.count() for m in apps.get_models()}
        self.client.post(reverse("result"), form_data())
        after = {m: m.objects.count() for m in apps.get_models()}
        self.assertEqual(before, after)
