"""The Add report form: age, test date, fasting, and the 9 markers.

Each marker has a value box (v_<marker>) and a unit list (u_<marker>).
Nothing here is saved; the form only checks the values.
"""

from django import forms

from phenoage.core import MARKERS
from phenoage.partial import MAX_MISSING
from phenoage.units import to_canonical

from .science import MARKER_INFO

FASTING_CHOICES = [("yes", "Yes, fasting"), ("no", "No"), ("unknown", "Not sure")]


class ReportForm(forms.Form):
    age = forms.IntegerField(label="Your age on the test day", min_value=18, max_value=100)
    test_date = forms.DateField(label="Test date", required=False,
                                widget=forms.DateInput(attrs={"type": "date"}))
    fasting = forms.ChoiceField(label="Fasting when the blood was taken?",
                                choices=FASTING_CHOICES, initial="yes")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for m in MARKERS:
            name, units = MARKER_INFO[m]
            self.fields["v_" + m] = forms.FloatField(
                label=name, required=False, min_value=0,
                widget=forms.NumberInput(attrs={"step": "any", "inputmode": "decimal"}))
            # Not required: a marker left empty needs no unit.
            self.fields["u_" + m] = forms.ChoiceField(
                label=name + " unit", choices=[(u, u) for u in units], required=False,
                initial=units[0])

    def marker_fields(self):
        """(value field, unit field) pairs, for the template."""
        return [(self["v_" + m], self["u_" + m]) for m in MARKERS]

    def clean(self):
        data = super().clean()
        report = {}
        for m in MARKERS:
            value = data.get("v_" + m)
            unit = data.get("u_" + m) or MARKER_INFO[m][1][0]
            if value is None:
                continue
            try:
                to_canonical(m, value, unit)
            except ValueError:
                if value <= 0:
                    msg = ("Must be more than 0. If the report says below a limit "
                           "(like <0.5), enter the limit.")
                else:
                    msg = ("This looks too high or too low for %s. Check the number "
                           "and the unit on your report." % unit)
                self.add_error("v_" + m, msg)
                continue
            report[m] = (value, unit)
        missing = len(MARKERS) - len(report)
        if missing > MAX_MISSING and not self.errors:
            raise forms.ValidationError(
                "Please enter at least %d of the 9 markers. With more than %d missing, "
                "the result would be too uncertain." % (len(MARKERS) - MAX_MISSING, MAX_MISSING))
        data["report"] = report
        return data
