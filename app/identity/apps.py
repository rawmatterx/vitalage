from django.apps import AppConfig


class IdentityConfig(AppConfig):
    """The identity store: who people are and what they agreed to."""
    default_auto_field = "django.db.models.BigAutoField"
    name = "identity"
