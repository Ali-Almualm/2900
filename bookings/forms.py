# bookings/forms.py
from django import forms
from .models import Booking, Availability
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

class AvailabilityForm(forms.ModelForm):
    class Meta:
        model = Availability
        fields = ['booking_type', 'start_time', 'end_time', 'is_available']
        widgets = {
            'start_time': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'end_time': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }
