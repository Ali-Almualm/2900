from django.contrib import admin
from .models import Competition, CompetitionParticipant
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


# Add the new models to the admin interface (optional but helpful)
# In bookings/admin.py:

class CompetitionParticipantInline(admin.TabularInline):
    model = CompetitionParticipant
    extra = 1 # Show one empty slot for adding participants

class CompetitionAdmin(admin.ModelAdmin):
    list_display = ('activity_type', 'start_time', 'end_time', 'max_joiners', 'creator', 'created_at', 'current_participants')
    list_filter = ('activity_type', 'start_time', 'creator')
    inlines = [CompetitionParticipantInline]

    def current_participants(self, obj):
        return obj.participants.count()
    current_participants.short_description = 'Participants'

admin.site.register(Competition, CompetitionAdmin)
admin.site.register(CompetitionParticipant) # You might not need this if using inline
