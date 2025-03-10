from django.contrib import admin
from .models import Booking

class BookingAdmin(admin.ModelAdmin):
    list_display = ('id', 'user_id', 'name', 'start_time', 'end_time', 'booking_type', 'created_at')
    list_filter = ('booking_type', 'start_time')
    search_fields = ('user_id', 'name')

admin.site.register(Booking, BookingAdmin)
