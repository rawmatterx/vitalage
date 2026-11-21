"""The research store: health data keyed by a random participant ID.

No names, emails, phone numbers or calendar dates live here. Milestone 3
adds the participant row; blood tests, band months and DNA results come in
milestone 4 and 5.
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
