"""Turn the translation files (.po, which people edit) into the files Django
reads (.mo). Run after changing any app/locale/*/LC_MESSAGES/django.po:

    pip install -r app/requirements-dev.txt
    python app/scripts/compile_translations.py

Django's own `compilemessages` does the same but needs the GNU gettext
programs installed; this needs only the small `polib` package.
"""

from pathlib import Path

import polib

LOCALE = Path(__file__).resolve().parent.parent / "locale"

for po_path in sorted(LOCALE.glob("*/LC_MESSAGES/*.po")):
    po = polib.pofile(str(po_path))
    po.save_as_mofile(str(po_path.with_suffix(".mo")))
    print("%s: %d translated, %d missing" % (po_path.relative_to(LOCALE.parent),
                                             len(po.translated_entries()),
                                             len(po.untranslated_entries())))
