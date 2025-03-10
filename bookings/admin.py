from django.contrib import admin
from .models import Booking, UserProfile

class BookingAdmin(admin.ModelAdmin):
    list_display = ('id', 'user_id', 'name', 'start_time', 'end_time', 'booking_type', 'created_at')
    list_filter = ('booking_type', 'start_time')
    search_fields = ('user_id', 'name')

class userProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'ranking_switch', 'ranking_pool', 'ranking_table_tennis')
    search_fields = ('user__username',)
admin.site.register(Booking, BookingAdmin)
admin.site.register(UserProfile, userProfileAdmin)
