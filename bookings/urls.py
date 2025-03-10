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
    path('logout/', views.logout_view, name='logout'),
]