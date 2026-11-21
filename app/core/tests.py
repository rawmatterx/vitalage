"""Tests for the web app. Run from the repo folder with:

    DJANGO_DEBUG=1 python app/manage.py test core
"""

from django.test import TestCase
from django.urls import reverse

from core.views import example_result


class HomePageTests(TestCase):
    def test_home_page_loads(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "VitalAge")

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
