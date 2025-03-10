from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from bookings.models import UserProfile

class Command(BaseCommand):
    help = 'Create UserProfile instances for all existing users'

    def handle(self, *args, **kwargs):
        users = User.objects.all()
        for user in users:
            if not hasattr(user, 'userprofile'):
                UserProfile.objects.create(user=user)
                self.stdout.write(self.style.SUCCESS(f'Created UserProfile for user: {user.username}'))
            else:
                self.stdout.write(self.style.SUCCESS(f'UserProfile already exists for user: {user.username}'))