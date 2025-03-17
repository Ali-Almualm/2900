from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

class Availability(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    booking_type = models.CharField(max_length=50, choices=[
        ('pool', 'Pool'),
        ('switch', 'Nintendo Switch'),
        ('table_tennis', 'Table Tennis'),
    ])
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    is_available = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.user.username} - {self.booking_type} - {self.start_time} to {self.end_time}"

    class Meta:
        unique_together = ('user', 'booking_type', 'start_time', 'end_time')
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