from django import forms
from .models import Booking

class BookingForm(forms.ModelForm):
    class Meta:
        model = Booking
        fields = ['user_id', 'name', 'start_time', 'end_time', 'booking_type']
