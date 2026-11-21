#!/usr/bin/env python
"""Django's command-line helper: runserver, test, migrate and so on."""
import os
import sys


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "vitalage_site.settings")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
