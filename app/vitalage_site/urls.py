"""Which web address goes to which page."""

from django.contrib import admin
from django.urls import path

from core import views

urlpatterns = [
    path("", views.home, name="home"),
    path("report/", views.add_report, name="add_report"),
    path("report/review/", views.review, name="review"),
    path("report/result/", views.result, name="result"),
    path("health/", views.health, name="health"),
    path("admin/", admin.site.urls),
]
