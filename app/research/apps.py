from django.apps import AppConfig


class ResearchConfig(AppConfig):
    """The research store: health data keyed by a random participant ID only."""
    default_auto_field = "django.db.models.BigAutoField"
    name = "research"
