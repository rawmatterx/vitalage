"""The Add report form: test date, fasting, and the 9 markers.

Each marker has a value box (v_<marker>) and a unit list (u_<marker>).
Age on the test day comes from the birth date the person gave on About you,
so it is not asked again. The form only checks the values; saving happens in
records.py once the person confirms them.
"""

from datetime import date

from django import forms

from phenoage.history import age_on

from phenoage.core import MARKERS
from phenoage.partial import MAX_MISSING
from phenoage.units import to_canonical

from .science import MARKER_INFO

FASTING_CHOICES = [("yes", "Yes, fasting"), ("no", "No"), ("unknown", "Not sure")]


SOURCE_CHOICES = [("typed", "Typed"), ("pdf", "PDF"), ("csv", "CSV")]


class ReportForm(forms.Form):
    test_date = forms.DateField(label="Test date",
                                widget=forms.DateInput(attrs={"type": "date"}),
                                error_messages={"required": "Enter the date of the blood test. "
                                                            "It is printed on the report."})
    fasting = forms.ChoiceField(label="Fasting when the blood was taken?",
                                choices=FASTING_CHOICES, initial="yes")
    # Set by the page's script when values came from a file; never the file itself.
    source = forms.ChoiceField(choices=SOURCE_CHOICES, required=False, initial="typed",
                               widget=forms.HiddenInput)

    def __init__(self, *args, born, **kwargs):
        """born: the person's birth date, from the identity store."""
        super().__init__(*args, **kwargs)
        self.born = born
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

    def clean_test_date(self):
        day = self.cleaned_data["test_date"]
        if day > date.today():
            raise forms.ValidationError("The test date cannot be in the future.")
        if age_on(self.born, day) < 18:
            raise forms.ValidationError("Check the year: this is before you turned 18.")
        return day

    def clean(self):
        data = super().clean()
        if data.get("test_date"):
            data["age"] = round(age_on(self.born, data["test_date"]), 1)
        data["source"] = data.get("source") or "typed"
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


BAND_MAX_BYTES = 2_000_000


class BandForm(forms.Form):
    file = forms.FileField(label="Band data (CSV)",
                           help_text="Columns: date, resting_hr, steps, sleep_hours, vo2max. "
                                     "Any column can be blank.",
                           widget=forms.ClearableFileInput(attrs={"accept": ".csv,text/csv"}))
    device_model = forms.CharField(label="Band brand and model", max_length=80,
                                   widget=forms.TextInput(attrs={"list": "band-models",
                                                                 "autocomplete": "off"}))

    def clean_file(self):
        f = self.cleaned_data["file"]
        if f.size > BAND_MAX_BYTES:
            raise forms.ValidationError("This file is too big. Export at most a year of daily values.")
        return f


# Plausible values per clock: pace clocks are near 1, age clocks are in years.
PACE_CLOCKS = {"dunedinpace": (0.4, 2.0)}
AGE_RANGE = (15.0, 120.0)


class DnaForm(forms.Form):
    test_date = forms.DateField(label="Test date (when the sample was taken)",
                                widget=forms.DateInput(attrs={"type": "date"}))
    vendor = forms.CharField(label="Test company", max_length=80,
                             widget=forms.TextInput(attrs={"list": "dna-vendors", "autocomplete": "off"}))
    clock = forms.CharField(label="Clock name, exactly as on the report", max_length=40,
                            widget=forms.TextInput(attrs={"list": "dna-clocks", "autocomplete": "off"}))
    value = forms.FloatField(label="Result",
                             widget=forms.NumberInput(attrs={"step": "any", "inputmode": "decimal"}))

    def clean_test_date(self):
        day = self.cleaned_data["test_date"]
        if day > date.today():
            raise forms.ValidationError("The test date cannot be in the future.")
        return day

    def clean(self):
        data = super().clean()
        clock, value = data.get("clock"), data.get("value")
        if clock and value is not None:
            key = clock.replace(" ", "").lower()
            low, high = PACE_CLOCKS.get(key, AGE_RANGE)
            if not low <= value <= high:
                if key in PACE_CLOCKS:
                    msg = "%s is usually between 0.6 and 1.4. Check the number." % clock
                else:
                    msg = "This looks wrong for an age clock (expected years). Check the number."
                self.add_error("value", msg)
        return data
