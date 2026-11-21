"""Which web address goes to which page."""

from django.contrib import admin
from django.urls import include, path

from core import views
from identity import views as identity

urlpatterns = [
    path("", views.home, name="home"),
    # Screens 1-4: invite, sign in, consent, about you
    path("join/<str:token>/", identity.welcome, name="welcome"),
    path("signin/", identity.signin, name="signin"),
    path("signin/code/", identity.signin_code, name="signin_code"),
    path("signout/", identity.signout, name="signout"),
    path("consent/", identity.consent, name="consent"),
    path("about/", identity.about, name="about"),
    # Screens 5-7: add report, review, result
    path("report/", views.add_report, name="add_report"),
    path("report/review/", views.review, name="review"),
    path("report/result/", views.result, name="result"),
    # Language picker (English / Bengali)
    path("i18n/", include("django.conf.urls.i18n")),
    path("health/", views.health, name="health"),
    path("admin/", admin.site.urls),
]
