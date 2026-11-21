"""Lets admins sign in to the admin pages with their email and password.

Accounts are stored by email fingerprint, not by email, so the normal Django
sign-in needs this small adapter. Participants never use a password: they
sign in with emailed codes (see views.py).
"""

from django.contrib.auth.backends import ModelBackend

from .models import Account


class EmailBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username or not password:
            return None
        account = Account.objects.for_email(username)
        if account and account.check_password(password) and self.user_can_authenticate(account):
            return account
        return None
