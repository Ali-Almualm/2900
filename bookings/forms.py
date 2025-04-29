# bookings/forms.py
from django import forms
from .models import Booking, MatchAvailability, Competition
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm

class BookingForm(forms.ModelForm):
    class Meta:
        model = Booking
        # omit start_time and end_time if you don’t want the user to type them
        fields = ['user_id', 'name', 'booking_type']


class registrationform(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']
class loginform(AuthenticationForm):
    class Meta:
        model = User
        fields = ['username', 'password']

class MatchAvailabilityForm(forms.ModelForm):
    class Meta:
        # Use renamed model
        model = MatchAvailability
        fields = ['booking_type', 'start_time', 'end_time', 'is_available']
        widgets = {
            'start_time': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'end_time': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }

class CompetitionForm(forms.ModelForm):
    class Meta:
        model = Competition
        fields = ['activity_type', 'start_time', 'end_time', 'max_joiners']
        widgets = {
            'start_time': forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
            'end_time': forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
            'activity_type': forms.Select(choices=Booking.BOOKING_TYPES), # Use choices from Booking model
        }

    def clean(self):
        cleaned_data = super().clean()
        start_time = cleaned_data.get("start_time")
        end_time = cleaned_data.get("end_time")
        activity_type = cleaned_data.get("activity_type")

        if start_time and end_time:
            if end_time <= start_time:
                raise forms.ValidationError("End time must be after start time.")

            # Check for conflicts with existing bookings
            conflicting_bookings = Booking.objects.filter(
                booking_type=activity_type,
                start_time__lt=end_time,
                end_time__gt=start_time
            )
            if conflicting_bookings.exists():
                raise forms.ValidationError(
                    f"This time slot conflicts with an existing booking for {activity_type}."
                )

            # Check for conflicts with existing competitions
            conflicting_competitions = Competition.objects.filter(
                activity_type=activity_type,
                start_time__lt=end_time,
                end_time__gt=start_time
            )
            if conflicting_competitions.exists():
                 raise forms.ValidationError(
                    f"This time slot conflicts with an existing competition for {activity_type}."
                )

        return cleaned_data