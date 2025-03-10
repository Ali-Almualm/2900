# bookings/forms.py
from django import forms
from .models import Booking

class BookingForm(forms.ModelForm):
    class Meta:
        model = Booking
        # omit start_time and end_time if you don’t want the user to type them
        fields = ['user_id', 'name', 'booking_type']

