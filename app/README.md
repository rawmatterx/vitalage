# VitalAge web app (pilot study)

This folder is the web app for the VitalAge pilot study. It is built with
[Django](https://www.djangoproject.com/), a Python web framework, and it
reuses the science code in `../phenoage/` unchanged.

**Status: milestone 1 of 6.** One page that runs the science code on a fixed
example report. No sign-in, consent or saving yet. See the MVP plan for what
comes next.

## Run it on your laptop

From the repository folder (the one that contains `app/` and `phenoage/`):

```bash
python3 -m venv .venv                 # make a private Python just for this project
source .venv/bin/activate             # Windows: .venv\Scripts\activate
pip install -r app/requirements.txt   # install Django and friends

export DJANGO_DEBUG=1                 # Windows: set DJANGO_DEBUG=1
python app/manage.py migrate          # create the local database (a file, app/db.sqlite3)
python app/manage.py runserver        # start the app
```

Open http://127.0.0.1:8000 in your browser. You should see internal age
**61.8 (+3.8 yrs)** for the example 58-year-old, the same number the README's
command-line example prints.

Stop the app with Ctrl+C.

## Run the tests

```bash
DJANGO_DEBUG=1 python app/manage.py test core   # web app tests
python -m unittest                                # science package tests (unchanged)
```

## What is in this folder

| Path | What it is |
| --- | --- |
| `manage.py` | Django's helper: `runserver`, `test`, `migrate` |
| `requirements.txt` | The packages the app needs |
| `vitalage_site/settings.py` | All settings. Secrets come from environment variables, never from the code |
| `vitalage_site/urls.py` | Which web address shows which page |
| `core/views.py` | The code behind each page |
| `core/templates/core/home.html` | The HTML of the home page |
| `core/tests.py` | Tests for the pages |

## Put it online (Render, free plan)

The file `render.yaml` in the repository folder tells [Render](https://render.com)
how to build and start the app, and creates a PostgreSQL database for it.

1. Sign in to Render with your GitHub account.
2. Click **New**, then **Blueprint**, and pick the `vitalage` repository.
3. Render reads `render.yaml`, creates the app and the database, and gives you
   a web address like `https://vitalage.onrender.com`.

Things to know about the free plan:

- The app goes to sleep after about 15 minutes without visitors, so the first
  page after a break takes up to a minute to load.
- The free database is deleted after about 30 days. That is fine now, since
  nothing is saved yet. Move to a paid database (about 7 US dollars a month)
  before any real participant data goes in.
- The server is outside India. Ask the ethics committee whether that is
  acceptable before the pilot starts (see the MVP plan's privacy checklist).

These limits are from Render's pricing page as we understand it; check it
before relying on them.

## Settings (environment variables)

| Name | Laptop | Server |
| --- | --- | --- |
| `DJANGO_DEBUG` | `1` | not set (debug off) |
| `DJANGO_SECRET_KEY` | not needed | a long random string (Render makes one) |
| `DJANGO_ALLOWED_HOSTS` | not needed | your web address, if not on Render |
| `DATABASE_URL` | not needed (uses SQLite) | the PostgreSQL address (Render fills it in) |
