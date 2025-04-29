from django.contrib import admin
from .models import Booking, UserProfile, MatchAvailability

class BookingAdmin(admin.ModelAdmin):
    list_display = ('id', 'user_id', 'name', 'start_time', 'end_time', 'booking_type', 'created_at')
    list_filter = ('booking_type', 'start_time')
    search_fields = ('user_id', 'name')

class userProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'ranking_switch', 'ranking_pool', 'ranking_table_tennis')
    search_fields = ('user__username',)

class MatchAvailabilityAdmin(admin.ModelAdmin):
    list_display = ('user', 'booking_type', 'start_time', 'end_time', 'is_available')
    list_filter = ('booking_type', 'is_available', 'start_time')
    search_fields = ('user__username', 'booking_type')
    ordering = ('start_time',)
admin.site.register(Booking, BookingAdmin)
admin.site.register(MatchAvailability, MatchAvailabilityAdmin)
admin.site.register(UserProfile, userProfileAdmin)
