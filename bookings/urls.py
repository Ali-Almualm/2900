from django.urls import path
from .views import index, book, cancel_booking, api_book

urlpatterns = [
    path('', index, name='index'),
    path('book/', book, name='book'),
    path('cancel/<int:booking_id>/', cancel_booking, name='cancel_booking'),
    path('api/book/', api_book, name='api_book'),
]
