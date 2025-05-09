from django.test import TestCase, SimpleTestCase
from django.urls import reverse
from django.contrib.auth.models import User
from bookings.models import Booking, MatchAvailability, Competition, BookingRequestmatch, CompetitionParticipant  # Import all models
from bookings.forms import BookingForm, CompetitionForm  #Import all forms
from django.utils import timezone
from datetime import datetime, timedelta
from django.test import Client # Import Client for simulating requests


class BookingModelTest(TestCase):


    def test_booking_creation(self):
        # Make datetimes aware
        start_time = timezone.make_aware(datetime(2024, 1, 1, 10, 0))
        end_time = timezone.make_aware(datetime(2024, 1, 1, 11, 0))


        booking = Booking.objects.create(
            user_id="testuser",
            name="Test Booking",
            booking_type="pool",
            start_time=start_time,
            end_time=end_time
        )
        self.assertEqual(booking.user_id, "testuser")
        self.assertEqual(booking.booking_type, "pool")


    def test_match_availability_creation(self):
        user = User.objects.create_user(username='testuser', password='testpassword')
        # Make datetimes aware
        start_time = timezone.make_aware(datetime(2024, 1, 2, 12, 0))
        end_time = timezone.make_aware(datetime(2024, 1, 2, 13, 0))


        availability = MatchAvailability.objects.create(
            user=user,
            booking_type="pool",
            start_time=start_time,
            end_time=end_time,
            is_available=True
        )
        self.assertTrue(availability.is_available)
        self.assertEqual(availability.booking_type, "pool")


class BookingViewTest(TestCase):


    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpassword')
        self.client = Client()
        self.client.login(username='testuser', password='testpassword')


    def test_index_view(self):
        response = self.client.get(reverse('index'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'bookings/index.html')


    def test_create_competition_view(self):
        response = self.client.get(reverse('create_competition'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'bookings/create_competition.html')


    def test_book_view(self):
        response = self.client.get(reverse('book'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'bookings/book.html')


class CompetitionModelTest(TestCase):  # Separate class for Competition tests


    def setUp(self):
        self.user = User.objects.create_user(username='creator', password='testpassword')


    def test_competition_creation(self):
        # Create aware datetime objects
        start_time = timezone.make_aware(datetime(2025, 5, 9, 9, 0))
        end_time = timezone.make_aware(datetime(2025, 5, 9, 10, 0))


        # Create a Competition instance
        competition = Competition.objects.create(
            creator=self.user,
            activity_type='pool',
            start_time=start_time,
            end_time=end_time,
            max_joiners=4
        )


        self.assertEqual(competition.creator, self.user)
        self.assertEqual(competition.activity_type, 'pool')
        self.assertEqual(competition.start_time, start_time)
        self.assertEqual(competition.end_time, end_time)
        self.assertEqual(competition.max_joiners, 4)


class CompetitionFormTest(TestCase): # Changed from SimpleTestCase to TestCase


    def setUp(self):
        self.user = User.objects.create_user(username='creator', password='testpassword')


    def test_competition_form_valid(self):
        start_time = timezone.make_aware(datetime(2025, 5, 10, 10, 0))
        end_time = timezone.make_aware(datetime(2025, 5, 10, 12, 0))
        form_data = {
            'activity_type': 'pool',
            'start_time': start_time,
            'end_time': end_time,
            'max_joiners': 4
        }
        form = CompetitionForm(data=form_data)
        self.assertTrue(form.is_valid())


    def test_competition_form_invalid(self):
            # Prepare invalid form data
            start_time = timezone.make_aware(datetime(2025, 5, 10, 10, 0))
            end_time = timezone.make_aware(datetime(2025, 5, 10, 8, 0))
            form_data = {
                'activity_type': 'pool',
                'start_time': start_time,
                'end_time': end_time,
                'max_joiners': 4
            }
            form = CompetitionForm(data=form_data)
            self.assertFalse(form.is_valid())
            print("Form Errors:", form.errors) # Debugging
            print("Form Non-Field Errors:", form.non_field_errors()) # Debugging non-field errors
            # self.assertEqual(len(form.errors), 1) # This assertion might also need adjustment depending on other potential field errors
            self.assertIn('End time must be after start time.', form.non_field_errors()) # Check for the specific non-field error message
            self.assertNotIn('end_time', form.errors) # Ensure no field-specific error was raised
            self.assertNotIn('activity_type', form.errors)
            self.assertNotIn('max_joiners', form.errors)


class MatchAvailabilityModelTest(TestCase):


    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpassword')


    def test_availability_time_range(self):
        start_time = timezone.make_aware(datetime(2025, 5, 11, 8, 0))
        end_time = timezone.make_aware(datetime(2025, 5, 11, 9, 0))
        availability = MatchAvailability.objects.create(
            user=self.user,
            booking_type='pool',
            start_time=start_time,
            end_time=end_time,
            is_available=True
        )
        self.assertEqual(availability.start_time, start_time)
        self.assertEqual(availability.end_time, end_time)
        self.assertTrue(availability.is_available)


    def test_availability_booking_type_choice(self):
        # Ensure that booking_type is one of the allowed choices
        valid_type = 'pool'
        availability = MatchAvailability.objects.create(
            user=self.user,
            booking_type=valid_type,
            start_time=timezone.make_aware(datetime(2025, 5, 11, 10, 0)),
            end_time=timezone.make_aware(datetime(2025, 5, 11, 11, 0)),
            is_available=True
        )
        self.assertEqual(availability.booking_type, valid_type)


class BookingRequestmatchModelTest(TestCase):


    def setUp(self):
        self.requester = User.objects.create_user(username='requester', password='testpassword')
        self.requested_player = User.objects.create_user(username='requested', password='testpassword')


    def test_match_request_creation(self):
        start_time = timezone.make_aware(datetime(2025, 5, 12, 12, 0))
        end_time = timezone.make_aware(datetime(2025, 5, 12, 13, 0))
        request = BookingRequestmatch.objects.create(
            requester=self.requester,
            requested_player=self.requested_player,
            activity_type='pool',
            start_time=start_time,
            end_time=end_time
        )
        self.assertEqual(request.requester, self.requester)
        self.assertEqual(request.requested_player, self.requested_player)
        self.assertEqual(request.activity_type, 'pool')
        self.assertEqual(request.start_time, start_time)
        self.assertEqual(request.end_time, end_time)
        self.assertFalse(request.is_confirmed)
        self.assertFalse(request.is_rejected)