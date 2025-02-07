from django.db import models

class Booking(models.Model):
    BOOKING_TYPES = [
        ('pool', 'Pool'),
        ('switch', 'Nintendo Switch'),
        ('table_tennis', 'Table Tennis'),
    ]

    user_id = models.CharField(max_length=50)  # Matches the MySQL schema
    name = models.CharField(max_length=100)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    booking_type = models.CharField(max_length=50, choices=BOOKING_TYPES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "bookings"  # Ensures Django uses the correct table name

    def __str__(self):
        return f"{self.name} - {self.booking_type} ({self.start_time} to {self.end_time})"
