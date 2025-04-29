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
    # Renamed path, view function, and URL name
    path('update-match-availability/', views.update_match_availability, name='update_match_availability'),
    # Renamed path, view function, and URL name
    path('save-match-availability/<str:activity_type>/', views.save_match_availability, name='save_match_availability'),
    # Renamed path, parameter, view function, and URL name
    path('toggle-match-availability/<int:match_availability_id>/', views.toggle_match_availability, name='toggle_match_availability'),
    # Renamed path, parameter, view function, and URL name
    path('delete-match-availability/<int:match_availability_id>/', views.delete_match_availability, name='delete_match_availability'),
    # --- End Renamed URLs ---

    path('logout/', views.logout_view, name='logout'),
    # find_matches URL remains, as it finds matches based on the (now renamed) MatchAvailability
    path('matches/<str:activity_type>/', views.find_matches, name='find_matches'),
    path('create-match-request/', views.create_match_request, name='create_match_request'),
    path('respond-to-match-request/<int:booking_request_id>/', views.respond_to_match_request, name='respond_to_match_request'),
    path('match-history/', views.match_history_view, name='match_history'),
    path('confirm-result/<int:booking_id>/', views.confirm_result_view, name='confirm_result'),
]