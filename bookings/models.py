from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

class MatchAvailability(models.Model): # Renamed
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    booking_type = models.CharField(max_length=50, choices=[
        ('pool', 'Pool'),
        ('switch', 'Nintendo Switch'),
        ('table_tennis', 'Table Tennis'),
    ])
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    # Consider renaming is_available if it causes confusion.
    # Maybe 'is_seeking_match'? But 'is_available' within MatchAvailability context might be okay.
    is_available = models.BooleanField(default=True)

    def __str__(self):
        # Updated __str__
        return f"{self.user.username} - Match Availability: {self.booking_type} - {self.start_time} to {self.end_time}"

    class Meta:
        # Updated unique_together if you want to keep the model name change consistent
        unique_together = ('user', 'booking_type', 'start_time', 'end_time')
        verbose_name = "Match Availability" # Optional: For Admin
        verbose_name_plural = "Match Availabilities" # Optional: For Admin
class BookingRequestmatch(models.Model):
    requester = models.ForeignKey(User, on_delete=models.CASCADE, related_name='booking_requests_made')
    requested_player = models.ForeignKey(User, on_delete=models.CASCADE, related_name='booking_requests_received')
    activity_type = models.CharField(max_length=50, choices=[
        ('pool', 'Pool'),
        ('switch', 'Nintendo Switch'),
        ('table_tennis', 'Table Tennis'),
    ])
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    is_confirmed = models.BooleanField(default=False)
    is_rejected = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    requester_skill = models.IntegerField(null=True, blank=True)  # Add this field

    def __str__(self):
        return f"{self.requester.username} -> {self.requested_player.username} ({self.start_time} - {self.end_time})"
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
        unique_together = ('start_time', 'booking_type')  # ✅ Allows different activities at the same time

    def __str__(self):
        return f"{self.name} - {self.booking_type} ({self.start_time} to {self.end_time})"

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    ranking_switch = models.IntegerField(default=0)
    ranking_pool = models.IntegerField(default=0)
    ranking_table_tennis = models.IntegerField(default=0)

    def __str__(self):
        return self.user.username
    
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)
@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.userprofile.save()