from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('pool/', views.activity_view, {'activity_type': 'pool'}, name='pool'),
    path('switch/', views.activity_view, {'activity_type': 'switch'}, name='switch'),
    path('table-tennis/', views.activity_view, {'activity_type': 'table_tennis'}, name='table_tennis'),
    path('book/', views.book, name='book'),
    path('api/book/', views.api_book, name='api_book'),
    path('cancel/<int:booking_id>/', views.cancel_booking, name='cancel_booking'),
    path('register/', views.register_user_view, name='register'),
    path('login/', views.login_user_view, name='login'),

    # Renamed URL name and view function
    path('match-availability/select/', views.select_match_availability_activity_view, name='select_match_availability_activity'),
    # Renamed path, view function, and URL name
    path('match-availability/<str:activity_type>/', views.match_availability_view, name='match_availability'),
    # --- End Renamed URLs ---
    path('api/toggle-slot-availability/', views.toggle_slot_availability, name='toggle_slot_availability'), # New URL

    path('logout/', views.logout_view, name='logout'),
    # find_matches URL remains, as it finds matches based on the (now renamed) MatchAvailability
    path('matches/<str:activity_type>/', views.find_matches, name='find_matches'),
    path('create-match-request/', views.create_match_request, name='create_match_request'),
    path('respond-to-match-request/<int:booking_request_id>/', views.respond_to_match_request, name='respond_to_match_request'),

    path('competitions/create/', views.create_competition, name='create_competition'),
    path('join-competition/<int:competition_id>/', views.join_competition, name='join_competition'),
    path('leave-competition/<int:competition_id>/', views.leave_competition, name='leave_competition'),

    path('competition/<int:competition_id>/', views.competition_detail, name='competition_detail'),
    path('competition/<int:competition_id>/complete/', views.complete_competition, name='complete_competition'),
    path('competition/<int:competition_id>/add_match/', views.add_competition_match, name='add_competition_match'),
    path('match/<int:match_id>/assign/', views.assign_match_participants, name='assign_match_participants'), # <-- ADD THIS

    path('match/<int:match_id>/results/', views.enter_match_results, name='enter_match_results'), # <-- CHECK THIS LINE


    path('match-history/', views.match_history_view, name='match_history'),
    path('confirm-result/<int:booking_id>/', views.confirm_result_view, name='confirm_result'),
    path('leaderboard/', views.leaderboard_view, name='leaderboard'),
    path('profile/', views.profile_view, name='profile'),
]