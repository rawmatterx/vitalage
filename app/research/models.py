"""The research store: health data keyed by a random participant ID.

No names, emails, phone numbers or calendar dates live here. Every date is
saved as "days since the anchor date" (the day of the person's first blood
test). The anchor itself is kept, encrypted, only in the identity store, so
an export of these tables holds no calendar dates at all.

Deleting a Participant deletes every row below that belongs to it.
"""

from django.db import models


class Participant(models.Model):
    SEX = [("male", "Male"), ("female", "Female")]
    SMOKING = [("never", "Never"), ("former", "Former"), ("current", "Current")]
    STATUS = [("active", "Active"), ("withdrawn", "Withdrawn")]

    participant_id = models.UUIDField(primary_key=True)
    birth_year = models.PositiveSmallIntegerField()
    sex = models.CharField(max_length=10, choices=SEX)
    smoking = models.CharField(max_length=10, choices=SMOKING)
    status = models.CharField(max_length=10, choices=STATUS, default="active")

    def __str__(self):
        return str(self.participant_id)


class BloodTest(models.Model):
    """One blood report. The lab file itself is never stored."""
    SOURCES = [("pdf", "PDF read on the device"), ("csv", "CSV read on the device"),
               ("typed", "Typed in")]
    FASTING = [("yes", "Yes"), ("no", "No"), ("unknown", "Not known")]

    participant = models.ForeignKey(Participant, on_delete=models.CASCADE,
                                    related_name="blood_tests")
    day_offset = models.IntegerField(help_text="Days since the anchor date")
    age = models.FloatField(help_text="Age on the test day, to 0.1 year")
    source = models.CharField(max_length=10, choices=SOURCES, default="typed")
    fasting = models.CharField(max_length=10, choices=FASTING, default="unknown")
    complete = models.BooleanField(help_text="All 9 markers present")

    class Meta:
        ordering = ["day_offset", "id"]

    def report(self):
        """{marker: (value, unit)} as printed, ready for the science code."""
        return {m.marker: (m.value_as_printed, m.unit_as_printed) for m in self.markers.all()}


class BloodMarker(models.Model):
    """One marker of one test, as printed and converted. Keeping the printed
    value and unit means a unit conversion can always be re-checked."""
    blood_test = models.ForeignKey(BloodTest, on_delete=models.CASCADE, related_name="markers")
    marker = models.CharField(max_length=20)
    value_as_printed = models.FloatField()
    unit_as_printed = models.CharField(max_length=20)
    value_canonical = models.FloatField()

    class Meta:
        unique_together = [("blood_test", "marker")]


class Result(models.Model):
    """What the science code said about one test. It can always be recomputed
    from the markers; model_version says which weights made it."""
    blood_test = models.OneToOneField(BloodTest, on_delete=models.CASCADE, related_name="result")
    model_version = models.CharField(max_length=20)
    internal_age = models.FloatField(help_text="Middle of the range when markers are missing")
    internal_low = models.FloatField()
    internal_high = models.FloatField()
    phenoage = models.FloatField(help_text="Middle of the range when markers are missing")
    pace_estimate = models.FloatField(null=True, blank=True, help_text="Single-test pace, full reports only")


class BandMonth(models.Model):
    """Medians of the band data for one 30-day block counted from the anchor.
    Daily rows are never stored."""
    participant = models.ForeignKey(Participant, on_delete=models.CASCADE,
                                    related_name="band_months")
    block = models.IntegerField(help_text="0 = the 30 days starting on the anchor date")
    day_offset = models.IntegerField(help_text="First day of the block, in days since the anchor")
    device_model = models.CharField(max_length=80)
    resting_hr = models.FloatField(null=True, blank=True)
    resting_hr_days = models.PositiveSmallIntegerField(default=0)
    steps = models.FloatField(null=True, blank=True)
    steps_days = models.PositiveSmallIntegerField(default=0)
    sleep_hours = models.FloatField(null=True, blank=True)
    sleep_hours_days = models.PositiveSmallIntegerField(default=0)
    vo2max = models.FloatField(null=True, blank=True)
    vo2max_days = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["block"]
        unique_together = [("participant", "block")]


class DnaTest(models.Model):
    """One DNA-age result, as reported by the test company."""
    participant = models.ForeignKey(Participant, on_delete=models.CASCADE,
                                    related_name="dna_tests")
    day_offset = models.IntegerField(help_text="Days since the anchor date")
    vendor = models.CharField(max_length=80)
    clock = models.CharField(max_length=40, help_text="e.g. DunedinPACE, GrimAge")
    value = models.FloatField()

    class Meta:
        ordering = ["day_offset", "id"]
