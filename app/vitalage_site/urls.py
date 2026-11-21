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
    # Screens 5-7: add report, review, save, result
    path("report/", views.add_report, name="add_report"),
    path("report/review/", views.review, name="review"),
    path("report/save/", views.save_report, name="save_report"),
    path("report/<int:pk>/", views.result, name="result"),
    path("report/<int:pk>/delete/", views.delete_report, name="delete_report"),
    path("report/<int:pk>/summary.pdf", views.result_pdf, name="result_pdf"),
    # Screens 8-11: history, fitness band, DNA test, my data and privacy
    path("history/", views.history, name="history"),
    path("band/", views.band, name="band"),
    path("dna/", views.dna, name="dna"),
    path("dna/<int:pk>/delete/", views.delete_dna, name="delete_dna"),
    path("my-data/", identity.my_data, name="my_data"),
    path("my-data/download/", identity.download_my_data, name="download_my_data"),
    path("my-data/recontact/", identity.change_recontact, name="change_recontact"),
    path("my-data/withdraw/", identity.withdraw, name="withdraw"),
    path("my-data/delete/", identity.delete_account, name="delete_account"),
    # Language picker (English / Bengali)
    path("i18n/", include("django.conf.urls.i18n")),
    path("health/", views.health, name="health"),
    path("admin/", admin.site.urls),
]
