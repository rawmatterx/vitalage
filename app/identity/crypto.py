"""Encryption for personal fields in the identity store.

Two tools, both built from one secret, the VITALAGE_FIELD_KEY setting:

- encrypt()/decrypt(): scramble a value (an email, a birth date) so the
  database alone does not reveal it. Uses Fernet from the `cryptography`
  package (AES with a tamper check).
- lookup_hash(): a fixed fingerprint of an email, so sign-in can find an
  account without decrypting every row.

Keep VITALAGE_FIELD_KEY secret and backed up. If it is lost, the encrypted
emails and birth dates cannot be read again.
"""

import base64
import hashlib
import hmac

from cryptography.fernet import Fernet
from django.conf import settings


def _key(purpose):
    return hashlib.sha256((purpose + ":" + settings.VITALAGE_FIELD_KEY).encode()).digest()


def _fernet():
    return Fernet(base64.urlsafe_b64encode(_key("encrypt")))


def encrypt(text):
    return _fernet().encrypt(str(text).encode()).decode()


def decrypt(token):
    return _fernet().decrypt(token.encode()).decode()


def normalise_email(email):
    return email.strip().lower()


def lookup_hash(email):
    """Same email in, same fingerprint out; the email cannot be read back from it."""
    return hmac.new(_key("lookup"), normalise_email(email).encode(), hashlib.sha256).hexdigest()


def secret_hash(value):
    """Fingerprint for one-time secrets (invite tokens, sign-in codes)."""
    return hmac.new(_key("secret"), str(value).encode(), hashlib.sha256).hexdigest()
