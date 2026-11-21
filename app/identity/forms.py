from datetime import date

from django import forms
from django.utils.translation import gettext_lazy as _


class EmailForm(forms.Form):
    email = forms.EmailField(label=_("Your email address"),
                             widget=forms.EmailInput(attrs={"autocomplete": "email"}))


class CodeForm(forms.Form):
    code = forms.RegexField(label=_("6-digit code"), regex=r"^\s*\d{6}\s*$",
                            error_messages={"invalid": _("Enter the 6 digits from the email.")},
                            widget=forms.TextInput(attrs={"inputmode": "numeric",
                                                          "autocomplete": "one-time-code",
                                                          "maxlength": "6"}))


class ConsentForm(forms.Form):
    pilot_research = forms.BooleanField(
        label=_("I have read the information above and agree to take part in the VitalAge pilot study."),
        error_messages={"required": _("You need to agree to this to take part.")})
    recontact = forms.BooleanField(
        label=_("You may contact me by email about the 12-month follow-up and future studies."),
        required=False)


class AboutForm(forms.Form):
    birth_date = forms.DateField(label=_("Date of birth"),
                                 widget=forms.DateInput(attrs={"type": "date"}))
    sex = forms.ChoiceField(label=_("Sex"), choices=[("male", _("Male")), ("female", _("Female"))],
                            widget=forms.RadioSelect,
                            help_text=_("Needed for the fitness reference values."))
    smoking = forms.ChoiceField(label=_("Smoking"),
                                choices=[("never", _("Never smoked")), ("former", _("Used to smoke")),
                                         ("current", _("Smoke now"))],
                                widget=forms.RadioSelect)

    def clean_birth_date(self):
        born = self.cleaned_data["birth_date"]
        today = date.today()
        age = today.year - born.year - ((today.month, today.day) < (born.month, born.day))
        if age < 18:
            raise forms.ValidationError(_("You must be 18 or older to take part."))
        if age > 100:
            raise forms.ValidationError(_("Please check the year."))
        return born

