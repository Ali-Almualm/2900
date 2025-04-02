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

    # --- Make sure this one comes first ---
    path('availability/select/', views.select_availability_activity_view, name='select_availability_activity'),
    # --- Before this one ---
    path('availability/<str:activity_type>/', views.availability_view, name='availability'),

    path('update-availability/', views.update_availability, name='update_availability'),
    path('save-availability/<str:activity_type>/', views.save_availability, name='save_availability'),
    path('logout/', views.logout_view, name='logout'),
    path('toggle-availability/<int:availability_id>/', views.toggle_availability, name='toggle_availability'),
    path('delete-availability/<int:availability_id>/', views.delete_availability, name='delete_availability'),
    path('matches/<str:activity_type>/', views.find_matches, name='find_matches'),
]
