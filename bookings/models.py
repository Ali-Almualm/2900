from django.db import models
from django.contrib.auth.models import User
from django.conf import settings # Recommended for ForeignKey to User
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
    is_completed = models.BooleanField(default=False)  # New field to track match completion
    created_at = models.DateTimeField(auto_now_add=True)
    requester_skill = models.IntegerField(null=True, blank=True)

    def __str__(self):
        return f"{self.requester.username} -> {self.requested_player.username} ({self.start_time} - {self.end_time})"
class Booking(models.Model):
    BOOKING_TYPES = [
        ('pool', 'Pool'),
        ('switch', 'Nintendo Switch'),
        ('table_tennis', 'Table Tennis'),
    ]

    user_id = models.CharField(max_length=50)  # Matches the MySQL schema
    opponent = models.ForeignKey(User, on_delete=models.CASCADE, related_name='opponent_bookings', null=True, blank=True)
    name = models.CharField(max_length=100)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    booking_type = models.CharField(max_length=50, choices=BOOKING_TYPES)
    created_at = models.DateTimeField(auto_now_add=True)

    user_result = models.CharField(max_length=10, null=True, blank=True, choices=[
        ('win', 'Win'),
        ('loss', 'Loss'),
        ('pending', 'Pending'),
    ])
    opponent_result = models.CharField(max_length=10, null=True, blank=True, choices=[
        ('win', 'Win'),
        ('loss', 'Loss'),
        ('pending', 'Pending'),
    ])


    def is_match_completed(self):
        """Check if both players have confirmed the result."""
        return self.user_result is not None and self.opponent_result is not None

    def get_match_winner(self):
        """Determine the winner of the match."""
        if self.user_result == 'win' and self.opponent_result == 'loss':
            return self.user_id
        elif self.user_result == 'loss' and self.opponent_result == 'win':
            return self.opponent_id
        return None  # Match is not yet resolved

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

class Competition(models.Model):
    ACTIVITY_CHOICES = Booking.BOOKING_TYPES # Reuse choices from Booking

    activity_type = models.CharField(max_length=50, choices=ACTIVITY_CHOICES)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    max_joiners = models.PositiveIntegerField(default=2) # Sensible default?
    creator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='created_competitions')
    created_at = models.DateTimeField(auto_now_add=True)
    # We need to ensure a competition doesn't overlap with a regular booking or another competition
    # for the same activity type and time.
    # A unique constraint helps, but validation in the view/form is crucial.
    # unique_together might be too restrictive if you allow *different* activities at the same time.

    def __str__(self):
        return f"Competition: {self.get_activity_type_display()} ({self.start_time.strftime('%Y-%m-%d %H:%M')} - {self.end_time.strftime('%H:%M')})"

    def is_full(self):
        return self.participants.count() >= self.max_joiners

    def can_join(self, user):
        # Check if full and if user hasn't already joined
        return not self.is_full() and not self.participants.filter(user=user).exists()

    class Meta:
        ordering = ['start_time']
        verbose_name = "Competition"
        verbose_name_plural = "Competitions"
        # Add constraints if needed, e.g., unique for activity, start, end
        # unique_together = ('activity_type', 'start_time', 'end_time') # Be careful with this

class CompetitionParticipant(models.Model):
    competition = models.ForeignKey(Competition, on_delete=models.CASCADE, related_name='participants')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='joined_competitions')
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('competition', 'user') # User can join a competition only once
        ordering = ['joined_at']

    def __str__(self):
        return f"{self.user.username} joined {self.competition}"


