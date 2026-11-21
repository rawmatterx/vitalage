# VitalAge web app (pilot study)

This folder is the web app for the VitalAge pilot study. It is built with
[Django](https://www.djangoproject.com/), a Python web framework, and it
reuses the science code in `../phenoage/` unchanged.

**Status: milestone 3 of 6.** People join through a personal email invite,
sign in with a 6-digit emailed code (no passwords), read the consent text and
tick two separate boxes, then fill in About you. Only then can they open the
blood report screens from milestone 2. Screens and emails work in English and
Bengali. Blood values are still not saved; saving comes in milestone 4.

**Before real participants:** the consent text and all Bengali text are
drafts. The ethics committee approves the English; a native speaker reviews
and back-translates the Bengali. See "Consent text" below.

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

To go through the screens as a participant, invite yourself. Open a second
terminal (same folder, run `source .venv/bin/activate` and
`export DJANGO_DEBUG=1` again) and type:

```bash
python app/manage.py invite you@example.com          # or add --lang bn for Bengali
```

On a laptop no email is really sent: the email is printed in the first
terminal (the one running `runserver`), and the link is also printed by the
command. Open the link, press Start, read the consent text, and fill in About
you. To sign in again later, use **Sign in**: the 6-digit code also appears in
the runserver terminal. Then pick `examples/sample_lab_report.pdf` to try the
blood report screens.

To use the admin pages (http://127.0.0.1:8000/admin/), make an admin account
with `python app/manage.py createadmin you@example.com`. Admins use a password;
participants never do.

Stop the app with Ctrl+C.

## Run the tests

```bash
DJANGO_DEBUG=1 python app/manage.py test identity core   # web app tests
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
| `core/forms.py` | The Add report form and its checks |
| `core/science.py` | Calls the phenoage package and shapes results for the pages |
| `core/static/core/report-reader.js` | Reads a PDF or CSV in the browser (copied from `web/vitalage.html`; change both together) |
| `core/static/core/vendor/pdfjs-3.11.174/` | Mozilla's pdf.js (Apache 2.0), served by the app so no outside site sees report use |
| `core/templates/core/` | The HTML of each page |
| `core/tests.py` | Tests for the report pages |
| `identity/` | The identity store: accounts, invites, sign-in codes, consent, audit log. Emails and birth dates are encrypted |
| `identity/views.py` | Welcome, Sign in, Consent and About you screens |
| `identity/management/commands/` | `invite` and `createadmin` commands |
| `identity/migrations/0002_draft_consent_text.py` | The first DRAFT consent text, English and Bengali |
| `research/` | The research store. People appear only as a random code, with birth year (no full dates), sex and smoking |
| `locale/bn/LC_MESSAGES/django.po` | Bengali screen and email text (draft translation) |
| `scripts/compile_translations.py` | Turns the `.po` file into the `.mo` file Django reads |

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
  no real participant data is in it yet. Move to a paid database (about 7 US dollars a month)
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
| `VITALAGE_FIELD_KEY` | not needed | a long random string (Render makes one). **Never change or lose it**: emails and birth dates encrypted with it could not be read again |
| `VITALAGE_SITE_URL` | not needed | the app's web address, used in invite links (Render fills it in) |
| `EMAIL_HOST`, `EMAIL_PORT` | not set (emails print in the terminal) | the email service's SMTP address and port |
| `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` | not set | the email service's SMTP login |
| `DEFAULT_FROM_EMAIL` | not set | the sender, like `VitalAge <study@yourdomain.in>` |

## Sending real emails

The email service is not decided yet. As a **guess**, `render.yaml` points at
[Brevo](https://www.brevo.com/)'s free plan (about 300 emails a day, which is
plenty for a pilot; check their pricing page). To use it: make a Brevo account,
verify the sender address, open **SMTP & API** to get the SMTP login and key,
and paste them into `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` and
`DEFAULT_FROM_EMAIL` in the Render dashboard. Any other service with SMTP
works the same way: change `EMAIL_HOST` too. Until these are filled in, the
server writes emails to its log instead of sending them.

## Consent text

The first consent text is added by `identity/migrations/0002_draft_consent_text.py`
as version `0.1-draft`. It is marked as a draft, so the consent screen shows a
yellow "Draft wording" warning, and it still has `[square bracket]` gaps (cost,
hosting company, contacts). When the ethics committee approves the wording, add
it in the admin pages as a new Consent version (one for English, one for
Bengali), with **Is draft** off and the approval number in **Ethics ref**. A
consent version cannot be changed once someone has agreed to it; make a new
version instead.

## Translations

Screen and email text is written in English in the code and templates. The
Bengali lines are in `locale/bn/LC_MESSAGES/django.po`. After changing it:

```bash
pip install -r app/requirements-dev.txt
python app/scripts/compile_translations.py
```

A test fails if a new English line on the sign-in or consent screens has no
Bengali line. The blood report screens are still English only.

## If you already put milestone 1 or 2 online

Milestone 3 changes how accounts are stored, which an existing database cannot
switch to. On Render, delete the `vitalage-db` database and sync the Blueprint
again so a fresh one is made. Nothing real is lost: no participant data was
saved before this milestone.
