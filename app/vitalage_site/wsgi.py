"""Entry point the server (gunicorn) uses to run the app."""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "vitalage_site.settings")

application = get_wsgi_application()
