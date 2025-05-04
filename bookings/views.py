from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import logout, login, authenticate
import json
from django.forms import modelformset_factory # Import formset factory
from django import forms
from django.http import JsonResponse
from datetime import datetime, timedelta, date, time
from django.contrib import messages
from django.urls import reverse # For redirects

from .models import Booking, UserProfile, MatchAvailability , BookingRequestmatch, Competition, CompetitionParticipant
from .models import CompetitionMatch, MatchParticipant, User
from django.views.decorators.http import require_POST # <--- ADD THIS LINE

#  SE HER!!!!!!! MATCH
from django.contrib.auth.models import User
from .forms import BookingForm, registrationform, loginform, MatchAvailabilityForm, CompetitionForm 
from .forms import CompetitionMatch, CompetitionMatchForm, MatchParticipantForm, MatchResultForm 
from django.contrib.auth.decorators import login_required
from django.db import models, transaction
from django.db.models import Q
from .elo_utils import update_elo_1v1, update_elo_2v2, update_elo_ffa, get_elo_field_name # Import your Elo functions


@login_required
@csrf_exempt
def api_book(request):
    if request.method == "POST":
        data = json.loads(request.body)
        
        time_range = data.get("start_time")  # e.g., "09:00 - 10:30"
        booking_type = data.get("booking_type")
        selected_date_str = data.get("booking_date")

        try:
            selected_date = datetime.strptime(selected_date_str, "%Y-%m-%d").date()
            times = time_range.split(" - ")
            if len(times) != 2:
                return JsonResponse({"message": "Invalid time range format."}, status=400)

            start_time = datetime.strptime(times[0], "%H:%M").time()
            end_time = datetime.strptime(times[1], "%H:%M").time()

            start_datetime = datetime.combine(selected_date, start_time)
            end_datetime = datetime.combine(selected_date, end_time)

            # Validate the duration (max 2 hours)
            if (end_datetime - start_datetime) > timedelta(hours=2):
                return JsonResponse({"message": "Booking cannot exceed two hours."}, status=400)

            # Check for overlapping bookings for the same activity
            if Booking.objects.filter(
                booking_type=booking_type,
                start_time__lt=end_datetime,
                end_time__gt=start_datetime
            ).exists():
                return JsonResponse(
                    {"message": "Some or all of these slots are already booked for this activity!"},
                    status=400
                )

            # Create booking
            Booking.objects.create(
                user_id=request.user.id,
                name=request.user.username,
                start_time=start_datetime,
                end_time=end_datetime,
                booking_type=booking_type
            )
            return JsonResponse({"message": "Booking created!"})
        except Exception as e:
            return JsonResponse({"message": f"Error: {str(e)}"}, status=400)

    return JsonResponse({"message": "Invalid request method."}, status=400)

@login_required
@csrf_exempt
def cancel_booking(request, booking_id):
    if request.method == "POST":
        booking = get_object_or_404(Booking, id=booking_id)
        if booking.name == request.user.username:
            booking.delete()
            return JsonResponse({"message": "Booking cancelled successfully."})
        else:
            return JsonResponse({"message": "You are not authorized to cancel this booking." + request.user.username}, status=403)
    return JsonResponse({"message": "Invalid request method."}, status=400)


def index(request):
    # --- Date Calculation ---
    today_date = date.today()
    date_str = request.GET.get('date', today_date.strftime('%Y-%m-%d'))
    try:
        selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        selected_date = today_date # Default to today if date format is invalid

    previous_date = selected_date - timedelta(days=1)
    next_date = selected_date + timedelta(days=1)
    # --- End Date Calculation ---

    time_slots = []
    # Use selected_date which is now guaranteed to be a date object
    start_time_dt = datetime.combine(selected_date, datetime.min.time()).replace(hour=8, minute=0)
    end_time_dt = datetime.combine(selected_date, datetime.min.time()).replace(hour=23, minute=59)

    current = start_time_dt
    while current < end_time_dt:
        slot_end = current + timedelta(minutes=15)
        time_slots.append((current, slot_end))
        current = slot_end

    bookings = Booking.objects.filter(start_time__date=selected_date)
    competitions = Competition.objects.filter(start_time__date=selected_date)

    ACTIVITY_TYPES = ["pool", "switch", "table_tennis"]
    timetable_by_activity = {activity: [] for activity in ACTIVITY_TYPES}

    for slot_start_time, slot_end_time in time_slots:
        time_slot_str = f"{slot_start_time.strftime('%H:%M')} - {slot_end_time.strftime('%H:%M')}"

        for activity in ACTIVITY_TYPES:
            slot_info = {
                "time_slot": time_slot_str,
                "start_datetime": slot_start_time,
                "status": "Available",
                "details": None,
                "type": "available",
                "competition_id": None,
                "can_join_competition": False,
                "is_full": False,
                "booked_by_user": False,
                "booking_id": None,
                "user_id": None,
                "name": "-", # Initialize name
                 # Add flags needed for template logic
                "user_joined": False,
                "is_creator": False,
            }

            competition_entry = competitions.filter(
                activity_type=activity,
                start_time__lt=slot_end_time,
                end_time__gt=slot_start_time
            ).first()

            if competition_entry:
                user_is_participant = False
                user_is_creator = False
                if request.user.is_authenticated:
                    user_is_participant = competition_entry.participants.filter(user=request.user).exists()
                    user_is_creator = (request.user == competition_entry.creator)

                slot_info.update({
                    "status": "Competition",
                    "details": f"Max: {competition_entry.max_joiners}, Joined: {competition_entry.participants.count()}",
                    "type": "competition",
                    "competition_id": competition_entry.id,
                    "is_full": competition_entry.is_full(),
                    "can_join_competition": request.user.is_authenticated and not user_is_creator and not user_is_participant and not competition_entry.is_full(),
                    "name": f"Comp by {competition_entry.creator.username}",
                    "user_joined": user_is_participant, # Pass this flag
                    "is_creator": user_is_creator,   # Pass this flag
                })
            else:
                booked_entry = bookings.filter(
                    booking_type=activity,
                    start_time__lt=slot_end_time,
                    end_time__gt=slot_start_time
                ).first()

                if booked_entry:
                    slot_info.update({
                        "status": "Booked",
                        "type": "booked",
                        "name": booked_entry.name,
                        "booking_id": booked_entry.id,
                        "user_id": booked_entry.user_id,
                        "booked_by_user": request.user.is_authenticated and booked_entry.name == request.user.username
                    })

            timetable_by_activity[activity].append(slot_info)

    return render(request, 'bookings/index.html', {
        "timetable_by_activity": timetable_by_activity,
        "selected_date": selected_date, # Pass date object
        "previous_date": previous_date.strftime('%Y-%m-%d'), # Pass formatted string
        "next_date": next_date.strftime('%Y-%m-%d'),       # Pass formatted string
        "today_date": today_date.strftime('%Y-%m-%d'),     # Pass formatted string for Today button
        "user": request.user
    })


@login_required
def select_match_availability_activity_view(request):
    """
    Displays a page for the user to select which activity
    they want to set availability for.
    """
    activity_types = [
        {'code': 'pool', 'name': 'Pool'},
        {'code': 'switch', 'name': 'Nintendo Switch'},
        {'code': 'table_tennis', 'name': 'Table Tennis'},
    ]
    return render(request, 'bookings/select_match_availability_activity.html', {'activity_types': activity_types})




@login_required
def match_availability_view(request, activity_type):
    # Get selected date or default to today
    today_dt = date.today() # Use consistent naming
    date_str = request.GET.get('date', today_dt.strftime('%Y-%m-%d'))
    try:
        selected_date_dt = date.fromisoformat(date_str)
    except ValueError:
        selected_date_dt = today_dt # Default to today if format is invalid

    # --- Get Existing Availability Times ---
    # Fetch records for the specific user, activity, and selected date
    existing_availabilities = MatchAvailability.objects.filter(
        user=request.user,
        booking_type=activity_type,
        start_time__date=selected_date_dt
    ).order_by('start_time') # Ordering is good practice but not essential for the set

    # Create a set of "HH:MM" strings for existing slots
    existing_times_set = set()
    for avail in existing_availabilities:
        # Add the start time formatted as HH:MM
        existing_times_set.add(avail.start_time.strftime("%H:%M"))
        # Note: This assumes availability is always in 15-min blocks matching the grid.
        # If availability could span multiple slots, more complex logic would be needed
        # to add all covered 15-min intervals to the set.
        # For now, we assume a 1-to-1 match between saved records and grid slots.
    # --- End Get Existing Times ---


    # The form is no longer needed here as it was removed from the template
    # form = MatchAvailabilityForm(initial={'booking_type': activity_type})

    return render(request, 'bookings/match_availability.html', {
        'activity_type': activity_type,
        # 'match_availabilities': existing_availabilities, # No longer needed for the table
        'existing_availability_times': existing_times_set, # Pass the set of HH:MM strings
        'today': today_dt, # Pass today's date object
        'selected_date': selected_date_dt # Pass the selected date object
    })


@login_required
@csrf_exempt # Consider removing csrf_exempt if using proper CSRF handling in JS fetch headers
@transaction.atomic # Wrap the whole operation in a transaction
def update_match_availability(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            selected_times = data.get('times', []) # List of "HH:MM" strings
            activity_type = data.get('activity_type')
            selected_date_str = data.get('selected_date')

            if not activity_type or not selected_date_str:
                return JsonResponse({"message": "Missing activity type or date parameter."}, status=400)

            # --- Validate and Parse Inputs ---
            try:
                selected_date = date.fromisoformat(selected_date_str)
            except ValueError:
                return JsonResponse({"message": "Invalid date format. Use YYYY-MM-DD."}, status=400)

            if activity_type not in [choice[0] for choice in MatchAvailability._meta.get_field('booking_type').choices]:
                 return JsonResponse({"message": "Invalid activity type."}, status=400)

            # --- Sync Logic ---
            # 1. Delete existing availability for this user, activity, and date
            num_deleted, _ = MatchAvailability.objects.filter(
                user=request.user,
                booking_type=activity_type,
                start_time__date=selected_date
            ).delete()
            print(f"DEBUG: Deleted {num_deleted} existing availability slots for {request.user.username} on {selected_date_str} for {activity_type}.") # Debugging

            # 2. Create new availability records for the submitted times
            created_count = 0
            for time_str in selected_times:
                try:
                    # Parse "HH:MM" string
                    hours, minutes = map(int, time_str.split(':'))
                    slot_start_time = time(hour=hours, minute=minutes)

                    # Combine date and time, ensure timezone awareness if needed (based on settings.USE_TZ)
                    # For simplicity, assuming naive datetimes or consistent handling elsewhere
                    start_datetime = datetime.combine(selected_date, slot_start_time)
                    end_datetime = start_datetime + timedelta(minutes=15) # Calculate end time

                    # Create the new record
                    MatchAvailability.objects.create(
                        user=request.user,
                        booking_type=activity_type,
                        start_time=start_datetime,
                        end_time=end_datetime,
                        is_available=True # Default to available when setting
                    )
                    created_count += 1
                except (ValueError, TypeError) as parse_error:
                    # Log error if a time string is invalid, but maybe continue?
                    print(f"Warning: Could not parse time string '{time_str}': {parse_error}")
                    # Optionally, you could stop and return an error here
                    # return JsonResponse({"message": f"Invalid time format submitted: {time_str}"}, status=400)
                    continue # Skip this invalid time string

            print(f"DEBUG: Created {created_count} new availability slots.") # Debugging

            # --- Return Success Response ---
            return JsonResponse({
                "message": f"Availability updated successfully for {selected_date_str}. ({created_count} slots set)"
            })

        # Handle potential errors during JSON parsing or database operations
        except json.JSONDecodeError:
            return JsonResponse({"message": "Invalid JSON format in request body."}, status=400)
        except Exception as e:
            # Log the full error for debugging on the server
            print(f"!!! Unexpected Error in update_match_availability: {type(e).__name__} - {e}")
            import traceback
            traceback.print_exc()
            return JsonResponse({"message": "An unexpected server error occurred while updating availability."}, status=500)

    # Handle non-POST requests
    return JsonResponse({"message": "Invalid request method. Use POST."}, status=405) # Method Not Allowed

# Add these functions to your views.py file

@login_required
@csrf_exempt
def toggle_match_availability(request, match_availability_id):
    """Toggle the availability status (available/unavailable)"""
    if request.method == 'POST':
        try:
            availability = get_object_or_404(MatchAvailability, id=match_availability_id, user=request.user)
            data = json.loads(request.body)
            availability.is_available = data.get('is_available', not availability.is_available)
            availability.save()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})
    return JsonResponse({'success': False, 'message': 'Invalid request method'})

@login_required
@csrf_exempt
def delete_match_availability(request, match_availability_id):
    """Delete an availability entry"""
    if request.method == 'POST':
        try:
            availability = get_object_or_404(MatchAvailability, id=match_availability_id, user=request.user)
            availability.delete()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})
    return JsonResponse({'success': False, 'message': 'Invalid request method'})

@login_required
def find_matches(request, activity_type):
    """
    Find users who have matching availability for the given activity,
    ensuring the overlapping slots are not already booked or part of a competition.
    Also handles pending requests.
    """
    user_profile = request.user.userprofile

    # Get the user's skill level for this activity
    if activity_type == 'pool':
        user_skill = user_profile.ranking_pool
    elif activity_type == 'switch':
        user_skill = user_profile.ranking_switch
    elif activity_type == 'table_tennis':
        user_skill = user_profile.ranking_table_tennis
    else:
        user_skill = 0 # Default or raise error?

    # Get the user's availability for this activity
    user_match_availability = MatchAvailability.objects.filter(
        user=request.user,
        booking_type=activity_type,
        is_available=True
    ).order_by('start_time') # Order for potentially cleaner overlap logic

    if not user_match_availability.exists():
        # Fetch pending requests even if user has no availability set
        pending_requests = BookingRequestmatch.objects.filter(
            requested_player=request.user,
            is_confirmed=False,
            is_rejected=False
        ).select_related('requester') # Optimize query

        return render(request, 'bookings/matches.html', {
            'activity_type': activity_type,
            'matches': [],
            'pending_requests': pending_requests,
            'error': 'You need to set your match availability before finding matches.'
        })

    # Find all other users with availability for this activity
    potential_matches = []
    # Exclude self and fetch related profiles and availability efficiently
    other_users_with_availability = User.objects.exclude(id=request.user.id).prefetch_related(
        'userprofile',
        models.Prefetch(
            'matchavailability_set',
            queryset=MatchAvailability.objects.filter(booking_type=activity_type, is_available=True),
            to_attr='filtered_availability'
        )
    )

    # Get *all* bookings and competitions for the relevant activity type upfront
    # This is more efficient than querying inside the loop for each overlap
    # Filter by date range if possible to reduce load (e.g., only check today/upcoming week)
    all_bookings = Booking.objects.filter(booking_type=activity_type) # Add date filtering if needed
    all_competitions = Competition.objects.filter(activity_type=activity_type) # Add date filtering if needed


    for other_user in other_users_with_availability:
        # Access the prefetched availability
        other_match_availability = getattr(other_user, 'filtered_availability', [])

        if not other_match_availability:
            continue # Skip user if they have no availability for this activity

        overlapping_times = []

        for user_slot in user_match_availability:
            for other_slot in other_match_availability:
                # Check if user/other availability slots overlap
                latest_start = max(user_slot.start_time, other_slot.start_time)
                earliest_end = min(user_slot.end_time, other_slot.end_time)

                if latest_start < earliest_end: # They overlap
                    overlap_start = latest_start
                    overlap_end = earliest_end

                    # --- Check if this specific overlap period is already booked ---
                    is_slot_booked = False

                    # Check against Bookings
                    if all_bookings.filter(start_time__lt=overlap_end, end_time__gt=overlap_start).exists():
                        is_slot_booked = True
                        # print(f"DEBUG: Slot {overlap_start}-{overlap_end} for {activity_type} conflicts with a Booking.") # Optional Debug

                    # Check against Competitions (only if not already found booked)
                    if not is_slot_booked and all_competitions.filter(start_time__lt=overlap_end, end_time__gt=overlap_start).exists():
                        is_slot_booked = True
                        # print(f"DEBUG: Slot {overlap_start}-{overlap_end} for {activity_type} conflicts with a Competition.") # Optional Debug

                    # --- Only add the overlap if it's NOT booked ---
                    if not is_slot_booked:
                        overlapping_times.append({
                            'start': overlap_start,
                            'end': overlap_end,
                            'duration_minutes': (overlap_end - overlap_start).total_seconds() / 60
                        })
                    # --- End check ---

        # Only add the user to potential_matches if there are valid, available overlapping times
        if overlapping_times:
            # Get other user's skill level from prefetched profile
            try:
                other_profile = other_user.userprofile
                if activity_type == 'pool':
                    other_skill = other_profile.ranking_pool
                elif activity_type == 'switch':
                    other_skill = other_profile.ranking_switch
                elif activity_type == 'table_tennis':
                    other_skill = other_profile.ranking_table_tennis
                else:
                    other_skill = 0 # Or handle appropriately

                # Calculate skill difference
                skill_difference = abs(user_skill - other_skill)

                potential_matches.append({
                    'user': other_user,
                    'overlapping_times': overlapping_times, # This list now only contains available slots
                    'skill_level': other_skill,
                    'skill_difference': skill_difference
                })
            except UserProfile.DoesNotExist:
                # This shouldn't happen if the signal works, but good to handle
                continue

    # Sort matches by skill difference (closer matches first)
    potential_matches.sort(key=lambda x: x['skill_difference'])

    # Fetch pending match requests for the logged-in user (optimize query)
    pending_requests = BookingRequestmatch.objects.filter(
        requested_player=request.user,
        is_confirmed=False,
        is_rejected=False
    ).select_related('requester') # Fetch requester info efficiently

    return render(request, 'bookings/matches.html', {
        'activity_type': activity_type,
        'matches': potential_matches, # Pass the filtered list
        'pending_requests': pending_requests,
        'error': None # Clear any previous error if availability exists now
    })


@login_required
def book(request):
    activity_type = request.GET.get('activity', 'pool')
    
    if request.method == "POST":
        form = BookingForm(request.POST)
        if form.is_valid():
            booking = form.save(commit=False)
            booking.booking_type = activity_type
            booking.save()
            return redirect('index')
    else:
        form = BookingForm()

    return render(request, 'bookings/book.html', {
        'form': form,
        'activity': activity_type
    })

def activity_view(request, activity_type):
    date_str = request.GET.get('date', datetime.today().strftime('%Y-%m-%d'))
    selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()

    start_time = datetime.combine(selected_date, datetime.min.time()).replace(hour=8, minute=0)
    end_time = datetime.combine(selected_date, datetime.min.time()).replace(hour=23, minute=59)
    time_slots = []
    current = start_time
    while current < end_time:
        slot_end = current + timedelta(minutes=15)
        time_slots.append((current, slot_end))
        current = slot_end

    bookings = Booking.objects.filter(
        start_time__date=selected_date,
        booking_type=activity_type
    ).order_by('start_time')

    competitions = Competition.objects.filter( # Fetch competitions
        start_time__date=selected_date,
        activity_type=activity_type
    ).order_by('start_time')

    timetable = []
    for slot_start, slot_end in time_slots:
        slot_start_str = slot_start.strftime("%H:%M")
        slot_end_str = slot_end.strftime("%H:%M")
        time_slot_str = f"{slot_start_str} - {slot_end_str}"

        slot_info = {
            "time_slot": time_slot_str,
            "status": "Available",
            "details": None,
            "type": "available",
            "competition_id": None,
            "can_join_competition": False,
            "is_full": False,
            "name": "-",
            "booked_by_user": False,
            "booking_id": None,
            "user_id": None,
        }

        # Check for Competitions first
        competition_entry = competitions.filter(
            start_time__lt=slot_end,
            end_time__gt=slot_start
        ).first()

        if competition_entry:
            user_is_participant = False
            if request.user.is_authenticated:
                user_is_participant = competition_entry.participants.filter(user=request.user).exists()

            slot_info.update({
                "status": "Competition",
                "details": f"Max: {competition_entry.max_joiners}, Joined: {competition_entry.participants.count()}",
                "type": "competition",
                "competition_id": competition_entry.id,
                "is_full": competition_entry.is_full(),
                "can_join_competition": request.user.is_authenticated and competition_entry.creator != request.user and not user_is_participant and not competition_entry.is_full(),
                "user_joined": user_is_participant, # <-- ADD THIS FLAG
                "is_creator": request.user.is_authenticated and competition_entry.creator == request.user, # <-- ADD THIS FLAG
                "name": f"Comp by {competition_entry.creator.username}"
            })
        else:
            # Check for Bookings if no competition
            booking_found = bookings.filter(
                start_time__lt=slot_end,
                end_time__gt=slot_start
            ).first()

            if booking_found:
                 slot_info.update({
                    "status": "Booked",
                    "type": "booked",
                    "name": booking_found.name,
                    "booking_id": booking_found.id,
                    "user_id": booking_found.user_id,
                    "booked_by_user": request.user.is_authenticated and booking_found.name == request.user.username
                 })

        timetable.append(slot_info)

    return render(request, 'bookings/activity.html', {
        "timetable": timetable,
        "activity": activity_type,
        "selected_date": selected_date,
        "title": dict(Booking.BOOKING_TYPES).get(activity_type),
        "user": request.user # Ensure user is passed
    })

@login_required
def save_match_availability(request, activity_type):
    if request.method == 'POST':
        form = MatchAvailabilityForm(request.POST)
        if form.is_valid():
            availability = form.save(commit=False)
            availability.user = request.user
            availability.booking_type = activity_type
            
            # Check for overlapping availabilities
            overlapping = MatchAvailability.objects.filter(
                user=request.user,
                booking_type=activity_type,
                start_time__lt=availability.end_time,
                end_time__gt=availability.start_time
            )
            
            if overlapping.exists():
                # Handle overlapping (merge or reject)
                # For simplicity, you might want to return an error message
                return render(request, 'bookings/match_availability.html', {
                    'form': form,
                    'activity_type': activity_type,
                    'error': 'Time range overlaps with existing match availability'
                })
                
            availability.save()
            return redirect('match_availability', activity_type=activity_type)
    else:
        form = MatchAvailabilityForm(initial={'booking_type': activity_type})

    availabilities = MatchAvailability.objects.filter(
        user=request.user,
        booking_type=activity_type
    ).order_by('start_time')
    
    return render(request, 'bookings/match_availability.html', {
        'form': form,
        'activity_type': activity_type,
        'availabilities': availabilities
    })


def register_user_view(request):
    if request.method == "POST":
        form = registrationform(request.POST)
        if form.is_valid():
            form.save()
            return redirect('index')
    else:
        form = registrationform()
    return render(request, 'bookings/register.html', {
        'form': form
    })

def login_user_view(request):
    if request.method == "POST":
        form = loginform(data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                return redirect('index')
    else:
        form = loginform()
    return render(request, 'bookings/login.html', {
        'form': form
    })

@login_required
def logout_view(request):
    logout(request)
    return redirect('login')



@login_required
@csrf_exempt
@login_required
@csrf_exempt
def create_match_request(request):
    """Create a match request from one user to another."""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            requested_player_id = data.get('requested_player_id')
            activity_type = data.get('activity_type')
            start_time = data.get('start_time')
            end_time = data.get('end_time')

            if not (requested_player_id and activity_type and start_time and end_time):
                return JsonResponse({'success': False, 'message': 'Missing required fields'}, status=400)

            requested_player = User.objects.get(id=requested_player_id)

            # Get the requester's skill rating based on the activity type
            requester_skill = None
            if activity_type == 'pool':
                requester_skill = request.user.userprofile.ranking_pool
            elif activity_type == 'switch':
                requester_skill = request.user.userprofile.ranking_switch
            elif activity_type == 'table_tennis':
                requester_skill = request.user.userprofile.ranking_table_tennis

            # Create the match request and store the requester's skill rating
            BookingRequestmatch.objects.create(
                requester=request.user,
                requested_player=requested_player,
                activity_type=activity_type,
                start_time=start_time,
                end_time=end_time,
                requester_skill=requester_skill  # Save the skill rating
            )
            return JsonResponse({'success': True, 'message': 'Match request sent successfully'})
        except User.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Requested player does not exist'}, status=404)
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)

    return JsonResponse({'success': False, 'message': 'Invalid request method'}, status=400)

@login_required
@csrf_exempt # Keep csrf_exempt for now, but ideally handle CSRF token in JS fetch
@transaction.atomic # Wrap in transaction for safety
def respond_to_match_request(request, booking_request_id):
    """Respond to a match request by confirming or rejecting it."""
    if request.method == 'POST':
        action = request.POST.get('action')  # 'confirm' or 'reject'
        try:
            # Fetch the request, ensuring it's for the logged-in user
            booking_request = BookingRequestmatch.objects.select_related('requester').get(
                id=booking_request_id,
                requested_player=request.user
            )

            # Check if the request was already handled
            if booking_request.is_confirmed or booking_request.is_rejected:
                 return JsonResponse({'success': False, 'message': 'This request has already been responded to.'}, status=400)


            if action == 'confirm':
                # ---- START: Add booking conflict check ----
                existing_booking = Booking.objects.filter(
                    start_time=booking_request.start_time,
                    end_time=booking_request.end_time, # Also check end time for exact match? Or just overlap?
                    booking_type=booking_request.activity_type
                ).first() # Use first() to avoid DoesNotExist error

                if existing_booking:
                    return JsonResponse({
                        'success': False,
                        'message': f"Cannot confirm: A booking for {booking_request.activity_type} already exists at this exact time ({booking_request.start_time.strftime('%H:%M')})."
                    }, status=409) # 409 Conflict is appropriate

                # --- Check for *overlapping* bookings (more robust) ---
                overlapping_bookings = Booking.objects.filter(
                    booking_type=booking_request.activity_type,
                    start_time__lt=booking_request.end_time,
                    end_time__gt=booking_request.start_time
                )
                if overlapping_bookings.exists():
                     # You might want to list the conflicting booking details if possible
                     return JsonResponse({
                         'success': False,
                         'message': f"Cannot confirm: This time overlaps with an existing booking for {booking_request.activity_type}."
                     }, status=409) # 409 Conflict
                # ---- END: Add booking conflict check ----


                # Create a new booking if no conflicts found
                booking = Booking.objects.create(
                    # Changed user_id to store the *requester's* ID as the primary booker
                    user_id=str(booking_request.requester.id),
                    # Keep opponent as the user who accepted (the current request.user)
                    opponent=request.user,
                    name=f"Match: {booking_request.requester.username} vs {request.user.username}", # More descriptive name
                    start_time=booking_request.start_time,
                    end_time=booking_request.end_time,
                    booking_type=booking_request.activity_type,
                    # Initialize results as pending
                    user_result='pending',
                    opponent_result='pending'
                )

                # Remove overlapping match availability timeslots for both users
                # Ensure this query is correct
                MatchAvailability.objects.filter(
                    Q(user=request.user) | Q(user=booking_request.requester),
                    Q(booking_type=booking_request.activity_type), # Add activity_type filter
                    Q(start_time__lt=booking_request.end_time, end_time__gt=booking_request.start_time)
                ).delete()

                booking_request.is_confirmed = True
                booking_request.save()
                return JsonResponse({'success': True, 'message': 'Match confirmed and booking created successfully'})

            elif action == 'reject':
                booking_request.is_rejected = True
                booking_request.save()
                return JsonResponse({'success': True, 'message': 'Match request rejected'})
            else:
                 return JsonResponse({'success': False, 'message': 'Invalid action.'}, status=400)


        except BookingRequestmatch.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Match request not found or you are not the recipient.'}, status=404)
        except Exception as e:
            # Log the exception for debugging
            print(f"Error in respond_to_match_request: {e}") # Basic logging
            # Consider using Django's logging framework: import logging; logger = logging.getLogger(__name__); logger.exception("Error...")
            return JsonResponse({'success': False, 'message': 'An unexpected server error occurred.'}, status=500)


    return JsonResponse({'success': False, 'message': 'Invalid request method.'}, status=400)


@login_required
def create_competition(request):
    if request.method == 'POST':
        form = CompetitionForm(request.POST)
        if form.is_valid():
            competition = form.save(commit=False)
            competition.creator = request.user
            competition.save()
            # Automatically add the creator as the first participant
            CompetitionParticipant.objects.create(competition=competition, user=request.user)
            messages.success(request, f"Competition for {competition.get_activity_type_display()} created successfully!")
            # Redirect to the activity page for the date of the competition
            activity_url = reverse(competition.activity_type) # e.g., reverse('pool')
            return redirect(f"{activity_url}?date={competition.start_time.strftime('%Y-%m-%d')}")
        else:
             # Pass the form with errors back to the template
            pass # Fall through to render the form again
    else:
        form = CompetitionForm()

    return render(request, 'bookings/create_competition.html', {'form': form})

@login_required
@csrf_exempt # Use csrf_exempt carefully or handle CSRF properly via JS fetch headers
def join_competition(request, competition_id):
    if request.method == 'POST':
        competition = get_object_or_404(Competition, id=competition_id)
        user = request.user

        # Check if user is the creator (already joined)
        if competition.creator == user:
             return JsonResponse({'success': False, 'message': 'You are the creator of this competition.'}, status=400)

        # Check if already joined
        if competition.participants.filter(user=user).exists():
            return JsonResponse({'success': False, 'message': 'You have already joined this competition.'}, status=400)

        # Check if full
        if competition.is_full():
            return JsonResponse({'success': False, 'message': 'This competition is already full.'}, status=400)

        # --- UPDATED Conflict Check ---
        # Check for time conflicts: User is creator OR opponent in a Booking
        user_bookings = Booking.objects.filter(
            Q(user_id=str(user.id)) | Q(opponent=user), # Use Q object to check both fields
            start_time__lt=competition.end_time,    # Booking starts before Comp ends
            end_time__gt=competition.start_time     # Booking ends after Comp starts
        )

        # Check for conflicts: User is participant in another Competition
        user_competitions = CompetitionParticipant.objects.filter(
            user=user,
            competition__start_time__lt=competition.end_time,
            competition__end_time__gt=competition.start_time
        ).exclude(competition=competition) # Don't compare with the one being joined

        if user_bookings.exists() or user_competitions.exists():
             # Determine which type of conflict occurred for a potentially clearer message
             conflict_type = "booking" if user_bookings.exists() else "another competition"
             # Optional: Add more details like the time of the conflict if needed
             print(f"DEBUG: Join conflict for user {user.username} joining comp {competition_id}. Conflict with {conflict_type}.") # Debugging
             return JsonResponse({'success': False, 'message': f'You have a time conflict with this competition (due to an existing {conflict_type}).'}, status=400)
        # --- End UPDATED Conflict Check ---

        # If no conflicts, join the competition
        CompetitionParticipant.objects.create(competition=competition, user=user)
        return JsonResponse({'success': True, 'message': 'Successfully joined the competition!'})

    # If not POST method
    return JsonResponse({'success': False, 'message': 'Invalid request method.'}, status=405)

@login_required
def match_history_view(request):
    """Display the match history for the logged-in user."""
    # Get matches where the user is creator (user_id) or opponent
    match_history_qs = Booking.objects.filter(
        Q(user_id=str(request.user.id)) | Q(opponent=request.user)
    ).select_related('opponent').order_by('-start_time') # Include opponent user

    # --- Fetch Creator Usernames ---
    # 1. Collect valid creator IDs (handle potential non-integer user_id values)
    creator_ids_str = set(match.user_id for match in match_history_qs)
    creator_ids_int = set()
    valid_creator_ids_map = {} # Map valid string ID back to integer ID
    for user_id_str in creator_ids_str:
        try:
            user_id_int = int(user_id_str)
            creator_ids_int.add(user_id_int)
            valid_creator_ids_map[user_id_str] = user_id_int
        except (ValueError, TypeError):
            print(f"Warning: Invalid user_id '{user_id_str}' found in Booking records during match history view.")
            pass # Ignore invalid IDs for fetching

    # 2. Fetch User objects for valid creator IDs
    creator_users = User.objects.filter(id__in=creator_ids_int)
    creator_user_map = {user.id: user for user in creator_users} # Map int ID to User object

    # 3. Prepare the final list, adding the creator user object to each match
    match_history_list = []
    for match in match_history_qs:
        creator_user_obj = None
        # Find the creator User object using the maps
        creator_int_id = valid_creator_ids_map.get(match.user_id)
        if creator_int_id:
            creator_user_obj = creator_user_map.get(creator_int_id)

        # Add the found creator user object as an attribute to the match instance
        match.creator_user = creator_user_obj
        match_history_list.append(match)
    # --- End Fetch Creator Usernames ---

    # Debugging: Print match history to the console (optional)
    print("Match History List (with creator_user attached):")
    for match in match_history_list:
        creator_name = match.creator_user.username if match.creator_user else f"ID:{match.user_id}"
        opponent_name = match.opponent.username if match.opponent else "None"
        print(f"  Match ID: {match.id}, Creator: {creator_name}, Opponent: {opponent_name}, User Result: {match.user_result}, Opponent Result: {match.opponent_result}")

    return render(request, 'bookings/match_history.html', {
        'match_history': match_history_list,
        # Passing the logged-in user is usually done automatically by context processors,
        # but ensure 'user': request.user is included if needed by your base template.
        'user': request.user
    })

@login_required
@csrf_exempt
@transaction.atomic
def confirm_result_view(request, booking_id):
    """
    Allow players to confirm the result of a simple 1v1 match (from Booking model)
    and update Elo ranks if results confirm appropriately.
    If results conflict (win/win or loss/loss), reset both to pending.
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            submitted_result = data.get('result')

            if submitted_result not in ['win', 'loss']:
                return JsonResponse({'success': False, 'message': 'Invalid result submitted.'}, status=400)

            booking = Booking.objects.select_related('opponent').get(id=booking_id)
            activity_type = booking.booking_type

            try:
                creator_id = int(booking.user_id)
            except (ValueError, TypeError):
                 print(f"!!! Error: Invalid user_id format '{booking.user_id}' in Booking ID {booking.id}")
                 return JsonResponse({'success': False, 'message': 'Internal server error (invalid user ID).'}, status=500)

            is_creator = request.user.id == creator_id
            is_opponent = booking.opponent and request.user.id == booking.opponent.id

            if not is_creator and not is_opponent:
                 return JsonResponse({'success': False, 'message': 'You are not part of this match.'}, status=403)

            current_user_result_field = 'user_result' if is_creator else 'opponent_result'
            current_result_value = getattr(booking, current_user_result_field)

            # Allow submission only if current state is None or 'pending'
            if current_result_value not in [None, 'pending']:
                 return JsonResponse({'success': False, 'message': 'You have already submitted your result for this match.'}, status=400)

            setattr(booking, current_user_result_field, submitted_result)
            print(f"Match {booking_id}: User {request.user.username} ({'Creator' if is_creator else 'Opponent'}) submitted '{submitted_result}'")
            booking.save()

            user_res = booking.user_result
            opp_res = booking.opponent_result
            print(f"Match {booking_id}: Current results - User='{user_res}', Opponent='{opp_res}'")

            if user_res and user_res != 'pending' and opp_res and opp_res != 'pending':
                print(f"Match {booking_id}: Both results are in. Checking for resolution or conflict...")

                if (user_res == 'win' and opp_res == 'loss') or \
                   (user_res == 'loss' and opp_res == 'win'):
                    print(f"Match {booking_id}: Results confirm the outcome.")

                    # --- Trigger Elo Update ---
                    elo_field = get_elo_field_name(activity_type)
                    print(f"  Elo field: {elo_field}")

                    if not elo_field:
                        print(f"  !!! Elo Warning: Elo field name not found for {activity_type}.")
                        messages.success(request, 'Match result confirmed!')
                        return JsonResponse({'success': True, 'message': 'Match result confirmed (Elo not tracked for this activity).'})

                    try:
                        creator_user = User.objects.get(id=creator_id)
                        opponent_user = booking.opponent
                        if not opponent_user: raise ValueError("Opponent user not found on booking.")

                        creator_profile = UserProfile.objects.get(user=creator_user)
                        opponent_profile = UserProfile.objects.get(user=opponent_user)

                        creator_elo = getattr(creator_profile, elo_field)
                        opponent_elo = getattr(opponent_profile, elo_field)
                        print(f"  Current Elo - Creator ({creator_user.username}): {creator_elo}, Opponent ({opponent_user.username}): {opponent_elo}")

                        if user_res == 'win':
                            new_creator_elo, new_opponent_elo = update_elo_1v1(creator_elo, opponent_elo)
                        else:
                            new_opponent_elo, new_creator_elo = update_elo_1v1(opponent_elo, creator_elo)

                        print(f"  New Elo - Creator: {new_creator_elo}, Opponent: {new_opponent_elo}")

                        setattr(creator_profile, elo_field, new_creator_elo)
                        setattr(opponent_profile, elo_field, new_opponent_elo)
                        creator_profile.save()
                        opponent_profile.save()
                        print(f"  Elo updated and profiles saved.")

                        messages.success(request, 'Match confirmed and ranks updated!')
                        return JsonResponse({'success': True, 'message': 'Match confirmed and ranks updated!'})

                    except (User.DoesNotExist, UserProfile.DoesNotExist, ValueError) as profile_err:
                         print(f"!!! Error finding user/profile or opponent: {profile_err}")
                         messages.warning(request, 'Match result confirmed, but failed to update ranks.')
                         return JsonResponse({'success': True, 'message': f'Match result confirmed, but failed to update ranks ({profile_err}).'})
                    except Exception as e:
                         print(f"!!! Error during Elo update: {e}")
                         messages.error(request, 'An error occurred during rank update.')
                         return JsonResponse({'success': False, 'message': 'An error occurred during rank update.'}, status=500)

                else: # Results conflict (e.g., both 'win' or both 'loss') - RESET TO PENDING
                    print(f"Match {booking_id}: Results submitted by both players conflict. Resetting to pending.")

                    booking.user_result = 'pending'
                    booking.opponent_result = 'pending'
                    booking.save() # Save the reset status

                    # === ADDED DEBUGGING ===
                    # Re-fetch from DB right after save to confirm persisted state
                    try:
                        reloaded_booking = Booking.objects.get(id=booking_id)
                        print(f"Match {booking_id}: CONFIRMED STATE AFTER RESET+SAVE - User='{reloaded_booking.user_result}', Opponent='{reloaded_booking.opponent_result}'")
                    except Booking.DoesNotExist:
                         print(f"!!! Error: Booking {booking_id} not found immediately after save?!")
                    # ========================

                    messages.warning(request, "Conflicting results submitted. Both results reset to pending.")

                    return JsonResponse({
                        'success': True,
                        'message': 'Conflicting results submitted. Both results have been reset to pending. Please coordinate with your opponent and resubmit.'
                    })

            else: # Only one result submitted so far
                print(f"Match {booking_id}: Waiting for opponent's result.")
                messages.info(request, 'Result recorded. Waiting for opponent.')
                return JsonResponse({'success': True, 'message': 'Result recorded. Waiting for opponent.'})

        except Booking.DoesNotExist:
            messages.error(request, 'Match not found.')
            return JsonResponse({'success': False, 'message': 'Match not found.'}, status=404)
        except json.JSONDecodeError:
            messages.error(request, 'Invalid request format.')
            return JsonResponse({'success': False, 'message': 'Invalid request format.'}, status=400)
        except Exception as e:
            print(f"!!! Unexpected Error in confirm_result_view: {type(e).__name__} - {e}")
            import traceback
            traceback.print_exc() # Print full traceback for unexpected errors
            messages.error(request, 'An unexpected server error occurred.')
            return JsonResponse({'success': False, 'message': 'An unexpected server error occurred.'}, status=500)

    return JsonResponse({'success': False, 'message': 'Invalid request method.'}, status=405)




@login_required
@csrf_exempt # Or ensure CSRF token is handled in JS fetch
@transaction.atomic # Ensures the operation is atomic
def leave_competition(request, competition_id):
    if request.method == 'POST': # Using POST for simplicity, DELETE might be semantically better
        competition = get_object_or_404(Competition, id=competition_id)
        user = request.user

        # Prevent creator from leaving via this method
        if competition.creator == user:
            return JsonResponse({'success': False, 'message': 'Creators cannot leave their own competition this way.'}, status=403)

        # Find the participation record
        participation = CompetitionParticipant.objects.filter(competition=competition, user=user).first()

        if participation:
            participation.delete()
            return JsonResponse({'success': True, 'message': 'You have left the competition.'})
        else:
            return JsonResponse({'success': False, 'message': 'You are not currently in this competition.'}, status=404)

    return JsonResponse({'success': False, 'message': 'Invalid request method.'}, status=405)

@login_required
@require_POST # Ensures this view only accepts POST requests
def complete_competition(request, competition_id):
    """Allows the competition creator to mark it as completed."""
    competition = get_object_or_404(Competition, id=competition_id)

    # Permission Check: Only the creator can complete it
    if request.user != competition.creator:
        messages.error(request, "You are not authorized to end this competition.")
        # Redirect somewhere appropriate, maybe the competition detail page if it exists, or index
        # If you create competition_detail view later, redirect there:
        # return redirect('competition_detail', competition_id=competition.id)
        return redirect('index') # Fallback redirect

    # Update status
    competition.status = 'completed'
    competition.save()

    messages.success(request, f"Competition '{competition}' marked as completed.")

    # Redirect back to the competition detail page or the activity page
    # activity_url = reverse(competition.activity_type) # e.g., reverse('pool')
    # return redirect(f"{activity_url}?date={competition.start_time.strftime('%Y-%m-%d')}")
    # Or redirect to competition detail page if you have one:
    # return redirect('competition_detail', competition_id=competition.id)
    return redirect('index') # Fallback redirect for now


@login_required
def competition_detail(request, competition_id):
    """Displays details for a specific competition."""
    competition = get_object_or_404(Competition, id=competition_id)
    participants = CompetitionParticipant.objects.filter(competition=competition).select_related('user')
    # Ensure related participants and users are fetched efficiently
    matches = CompetitionMatch.objects.filter(competition=competition).prefetch_related('participants__user')

    is_creator = (request.user == competition.creator)

    # Check if there is at least one match with status 'completed'
    has_completed_matches = matches.filter(status='completed').exists()

    context = {
        'competition': competition,
        'participants': participants,
        'matches': matches,
        'is_creator': is_creator,
        'has_completed_matches': has_completed_matches, # Pass the boolean flag here
    }
    return render(request, 'bookings/competition_detail.html', context)

@login_required
def add_competition_match(request, competition_id):
    """Allows the competition creator to add a new match shell."""
    competition = get_object_or_404(Competition, id=competition_id)

    # --- Permission Checks ---
    if request.user != competition.creator:
        messages.error(request, "You are not authorized to add matches to this competition.")
        return redirect('competition_detail', competition_id=competition.id)

    if competition.status == 'completed':
        messages.warning(request, "Cannot add matches to a completed competition.")
        return redirect('competition_detail', competition_id=competition.id)
    # --- End Permission Checks ---

    if request.method == 'POST':
        # Pass the competition object to the form if needed for validation
        form = CompetitionMatchForm(request.POST, competition=competition)
        if form.is_valid():
            match = form.save(commit=False)
            match.competition = competition # Link the match to the competition
            match.status = 'pending' # Matches start as pending
            match.save()
            messages.success(request, f"Match ({match.get_match_type_display()}) created successfully. Now add participants.")
            # Redirect back to the detail page where the new match will be listed
            # Consider redirecting to a participant assignment page later:
            # return redirect('assign_match_participants', match_id=match.id)
            return redirect('competition_detail', competition_id=competition.id)
        else:
            # Form is invalid, errors will be displayed by the template rendering below
            messages.error(request, "Please correct the errors below.")
    else: # GET request
        form = CompetitionMatchForm(competition=competition) # Pass competition for potential validation

    context = {
        'form': form,
        'competition': competition,
    }
    return render(request, 'bookings/add_competition_match.html', context)

@login_required
def assign_match_participants(request, match_id):
    """Assign/Manage participants for a specific competition match."""
    match = get_object_or_404(CompetitionMatch, id=match_id)
    competition = match.competition

    # --- Permission Checks ---
    if request.user != competition.creator:
        messages.error(request, "You are not authorized to manage participants for this match.")
        return redirect('competition_detail', competition_id=competition.id)

    if competition.status == 'completed':
        messages.warning(request, "Cannot manage participants for a completed competition.")
        return redirect('competition_detail', competition_id=competition.id)
    # --- End Permission Checks ---

    # Get users who joined the competition
    competition_participants = CompetitionParticipant.objects.filter(competition=competition)
    eligible_user_ids = competition_participants.values_list('user_id', flat=True)
    eligible_users = User.objects.filter(id__in=eligible_user_ids).order_by('username')

    # --- Determine expected number of participants ---
    if match.match_type == '1v1':
        num_participants_expected = 2
    elif match.match_type == '2v2':
        num_participants_expected = 4
    else: # FFA - Handle differently? For now, let's allow adding many.
        # We might need an "Add Player" button & JS for true FFA flexibility
        # Let's set a max for now or allow creator to manage extras
        num_participants_expected = competition.participants.count() # Default to max possible? Or a smaller number? Let's start flexible.
        # Or set extra=1 to add one at a time? For now, let's manage existing + maybe 1 extra.

    # --- Create the Formset ---
    # We manage existing participants + allow adding up to the expected number
    MatchParticipantFormSet = modelformset_factory(
        MatchParticipant,
        form=MatchParticipantForm, # Use our custom form
        fields=('user', 'team'),
        extra=0, # Start with 0 extra forms, we might add dynamically if needed or adjust 'initial'
        can_delete=True # Allow deleting participants from the match
    )

    # Limit user choices in the formset's forms
    formset_kwargs = {
        'form_kwargs': {
            'eligible_users': eligible_users,
            'match_type': match.match_type
        }
    }

    if request.method == 'POST':
        formset = MatchParticipantFormSet(request.POST, queryset=MatchParticipant.objects.filter(match=match), **formset_kwargs)

        if formset.is_valid():
            try:
                with transaction.atomic(): # Ensure all or nothing saves
                    participants = formset.save(commit=False)
                    users_in_formset = set()
                    valid_count = 0

                    for participant in formset.cleaned_data:
                         # Check if the form is marked for deletion
                        if participant.get('DELETE', False):
                            # If instance exists, delete it (formset handles this if commit=True)
                            if participant.get('id'):
                                 participant.get('id').delete()
                            continue # Skip further processing for deleted forms

                        # Check if it's an empty form (can happen with extra forms)
                        if not participant or not participant.get('user'):
                            continue

                        # Check for duplicate users within the submission
                        user = participant.get('user')
                        if user in users_in_formset:
                             raise forms.ValidationError(f"Cannot add the same user '{user.username}' multiple times to the same match.")
                        users_in_formset.add(user)

                        # Check if user is eligible
                        if user.id not in eligible_user_ids:
                             raise forms.ValidationError(f"User '{user.username}' is not registered for this competition.")

                        # Assign match (if creating new)
                        instance = participant.get('id') # Existing instance or None
                        if instance is None: # Creating new
                            new_participant = MatchParticipant(
                                match=match,
                                user=user,
                                team=participant.get('team')
                             )
                            new_participant.save()
                        else: # Updating existing
                             instance.user = user
                             instance.team = participant.get('team')
                             instance.save()
                        valid_count +=1


                    # Final validation based on match type (after processing all forms)
                    if match.match_type in ['1v1', '2v2'] and valid_count != num_participants_expected:
                         raise forms.ValidationError(f"Incorrect number of participants for a {match.get_match_type_display()} match. Expected {num_participants_expected}, got {valid_count}.")
                    # Add validation for 2v2 teams if needed (e.g., ensure teams A and B exist)

                messages.success(request, "Match participants updated successfully.")
                return redirect('competition_detail', competition_id=competition.id)

            except forms.ValidationError as e:
                 # Add non-form errors to be displayed
                 formset.non_form_errors().append(e)
                 messages.error(request, f"Please correct the errors: {e}")

            except Exception as e:
                 # Catch other potential errors during save
                 messages.error(request, f"An unexpected error occurred: {e}")
                 # You might want to add more specific error handling or logging
                 formset.non_form_errors().append(f"An unexpected error occurred: {e}")

        else: # Formset is invalid
             messages.error(request, "Please correct the errors in the form(s) below.")

    else: # GET request
        # Queryset for existing participants
        queryset = MatchParticipant.objects.filter(match=match)
        # Calculate how many extra forms might be needed
        current_participants = queryset.count()

        # For fixed types (1v1, 2v2), set extra to reach the target number
        if match.match_type in ['1v1', '2v2']:
            extra_forms = max(0, num_participants_expected - current_participants)
        else: # FFA - Maybe just allow adding one at a time?
            extra_forms = 1 # Allow adding one more participant

        # Recreate factory with calculated extra forms
        MatchParticipantFormSet = modelformset_factory(
            MatchParticipant,
            form=MatchParticipantForm,
            fields=('user', 'team'),
            extra=extra_forms,
            can_delete=True
        )
        formset = MatchParticipantFormSet(queryset=queryset, **formset_kwargs)

    context = {
        'formset': formset,
        'match': match,
        'competition': competition,
        'match_type': match.match_type, # Pass match_type for template logic
        'eligible_users_count': eligible_users.count() # For display/info
    }
    return render(request, 'bookings/assign_match_participants.html', context)

@login_required
@transaction.atomic # Ensure the view is wrapped
def enter_match_results(request, match_id):
    print(f"\n--- Entering enter_match_results for Match ID: {match_id} ---") # DEBUG
    match = get_object_or_404(CompetitionMatch.objects.select_related('competition'), id=match_id)
    competition = match.competition
    activity_type = competition.activity_type
    print(f"Match Type: {match.match_type}, Activity Type: {activity_type}") # DEBUG

    # --- Permission Checks (keep these) ---
    if request.user != competition.creator:
        # ... error handling ...
        return redirect('competition_detail', competition_id=competition.id)
    if competition.status == 'completed':
        # ... error handling ...
        return redirect('competition_detail', competition_id=competition.id)
    if not match.participants.exists():
        # ... error handling ...
        return redirect('assign_match_participants', match_id=match.id)
    # --- End Permission Checks ---

    is_editing = match.status == 'completed'
    print(f"Is Editing: {is_editing}") # DEBUG

    MatchResultFormSet = modelformset_factory(
        MatchParticipant,
        form=MatchResultForm,
        fields=('result_simple', 'result_rank_score'),
        extra=0
    )
    formset_kwargs = {'form_kwargs': {'match_type': match.match_type}}

    if request.method == 'POST':
        print("Processing POST request...") # DEBUG
        formset = MatchResultFormSet(request.POST, queryset=match.participants.all().select_related('user'), **formset_kwargs)

        if formset.is_valid():
            print("Formset IS valid. Proceeding with saving results and Elo update.") # DEBUG
            # This try/except is now within the @transaction.atomic context
            try:
                participants_data = {}
                ranks_entered = set()
                teams_results = {}

                # First pass: Save individual results and collect data
                print("Saving individual participant results...") # DEBUG
                for form in formset:
                    # Check if form has data AND is valid (though formset.is_valid() checks all)
                    if form.is_valid(): # form.has_changed() might prevent saving unchanged results, re-evaluate if needed
                         instance = form.instance
                         result_simple = form.cleaned_data.get('result_simple')
                         result_rank_score = form.cleaned_data.get('result_rank_score')
                         print(f"  Processing participant: {instance.user.username}, Simple: {result_simple}, Rank/Score: {result_rank_score}") # DEBUG

                         # Your logic to save instance fields based on match type
                         if match.match_type == 'ffa':
                             instance.result_type = 'rank'
                             instance.result_value = result_rank_score
                             instance.save()
                             if result_rank_score: ranks_entered.add(result_rank_score)
                         elif match.match_type in ['1v1', '2v2']:
                             instance.result_type = result_simple
                             instance.result_value = None
                             instance.save()
                             # Collect team info if 2v2
                             if match.match_type == '2v2':
                                 team = instance.team
                                 if not team: raise forms.ValidationError(f"Team missing for {instance.user.username} in 2v2 match.") # Add validation
                                 if team not in teams_results: teams_results[team] = []
                                 teams_results[team].append({'instance': instance, 'result': result_simple})

                         participants_data[instance.id] = {
                             'instance': instance,
                             'simple': result_simple,
                             'rank_score': result_rank_score,
                             'team': instance.team
                         }
                print("Finished saving individual results.") # DEBUG

                # --- Post-save Validation (ensure this happens AFTER saving individuals) ---
                print("Performing post-save validation (1v1 W/L, 2v2 teams, etc.)...") # DEBUG
                # ... (Your existing validation logic here, e.g., checking 1v1 win/loss count) ...
                if match.match_type == '1v1':
                     results = [p['simple'] for p in participants_data.values()]
                     if not ((results.count('win') == 1 and results.count('loss') == 1) or (results.count('draw') == 2)):
                          print("!!! 1v1 Validation Failed: Incorrect Win/Loss/Draw combination.") # DEBUG
                          raise forms.ValidationError("Invalid results for 1v1. Must be one Win & one Loss, or two Draws.")
                # ... add validation checks for 2v2 and FFA ...
                print("Post-save validation passed.")# DEBUG

                # --- Elo Calculation and Update ---
                print("Starting Elo calculation...") # DEBUG
                elo_field = get_elo_field_name(activity_type)
                print(f"  Elo field name: {elo_field}") # DEBUG

                if not elo_field:
                    messages.warning(request, f"Elo ranking not tracked for activity type: {activity_type}")
                    print("!!! Elo Warning: Elo field name not found.") # DEBUG
                else:
                    player_ids = [p['instance'].user.id for p in participants_data.values()]
                    print(f"  Fetching profiles for user IDs: {player_ids}") # DEBUG
                    profiles = UserProfile.objects.filter(user_id__in=player_ids).in_bulk(field_name='user_id')
                    print(f"  Found {len(profiles)} profiles.") # DEBUG

                    if len(profiles) != len(player_ids):
                        messages.error(request, "Could not find User Profiles for all participants. Elo not updated.")
                        print("!!! Elo Error: Mismatch between participants and profiles found.") # DEBUG
                    else:
                         print(f"  Calculating Elo changes for match type: {match.match_type}") # DEBUG
                         # --- 1v1 Elo ---
                         if match.match_type == '1v1':
                             p_list = list(participants_data.values())
                             p1_id, p2_id = p_list[0]['instance'].user_id, p_list[1]['instance'].user_id
                             p1_profile, p2_profile = profiles[p1_id], profiles[p2_id]
                             p1_elo, p2_elo = getattr(p1_profile, elo_field), getattr(p2_profile, elo_field)
                             print(f"    Player {p1_id} Elo: {p1_elo}, Player {p2_id} Elo: {p2_elo}") # DEBUG

                             if p_list[0]['simple'] == 'win':
                                 new_p1_elo, new_p2_elo = update_elo_1v1(p1_elo, p2_elo)
                             elif p_list[0]['simple'] == 'loss':
                                 new_p2_elo, new_p1_elo = update_elo_1v1(p2_elo, p1_elo)
                             else: # Draw
                                 new_p1_elo, new_p2_elo = p1_elo, p2_elo # No change on draw (adjust if needed)

                             print(f"    New Elo -> P{p1_id}: {new_p1_elo}, P{p2_id}: {new_p2_elo}") # DEBUG
                             setattr(p1_profile, elo_field, new_p1_elo)
                             setattr(p2_profile, elo_field, new_p2_elo)
                             p1_profile.save()
                             p2_profile.save()
                             print("    1v1 Elo updated and profiles saved.") # DEBUG

                         # --- 2v2 Elo ---
                         elif match.match_type == '2v2':
                             # (Group players, calculate avg, call update_elo_2v2, save profiles)
                             # Add print statements within this block similar to 1v1
                             print("    Processing 2v2 Elo...") # DEBUG
                             # ... detailed 2v2 logic with prints ...
                             try:
                                teamA_ratings, teamB_ratings = [], []
                                teamA_profiles, teamB_profiles = [], []
                                teamA_won = None
                                for p_data in participants_data.values():
                                    profile = profiles[p_data['instance'].user_id]
                                    rating = getattr(profile, elo_field)
                                    if p_data['team'] == 'A':
                                        teamA_ratings.append(rating)
                                        teamA_profiles.append(profile)
                                        if teamA_won is None and p_data['simple'] in ['win', 'loss']: teamA_won = (p_data['simple'] == 'win')
                                    elif p_data['team'] == 'B':
                                        teamB_ratings.append(rating)
                                        teamB_profiles.append(profile)
                                print(f"      Team A Ratings: {teamA_ratings}, Team B Ratings: {teamB_ratings}, Team A Won: {teamA_won}") # DEBUG
                                if len(teamA_profiles) == 2 and len(teamB_profiles) == 2 and teamA_won is not None:
                                     new_teamA_ratings, new_teamB_ratings = update_elo_2v2(teamA_ratings, teamB_ratings, teamA_won)
                                     print(f"      New Team A: {new_teamA_ratings}, New Team B: {new_teamB_ratings}") # DEBUG
                                     for profile, new_elo in zip(teamA_profiles, new_teamA_ratings): setattr(profile, elo_field, new_elo); profile.save()
                                     for profile, new_elo in zip(teamB_profiles, new_teamB_ratings): setattr(profile, elo_field, new_elo); profile.save()
                                     print("    2v2 Elo updated and profiles saved.") # DEBUG
                                else:
                                     messages.error(request, "Error processing 2v2 teams for Elo update (Wrong team sizes or draw?).")
                                     print("!!! Elo Error: Incorrect 2v2 team setup or draw result found.") # DEBUG
                             except Exception as e:
                                 print(f"!!! Elo Error during 2v2 processing: {e}") # DEBUG
                                 messages.error(request, f"Error calculating 2v2 Elo: {e}")


                         # --- FFA Elo ---
                         elif match.match_type == 'ffa':
                             # (Prepare list of (id, rating, rank), call update_elo_ffa, save profiles)
                             # Add print statements within this block similar to 1v1
                             print("    Processing FFA Elo...") # DEBUG
                             try:
                                ratings_ranks = []
                                for p_data in participants_data.values():
                                    profile = profiles[p_data['instance'].user_id]
                                    rating = getattr(profile, elo_field)
                                    rank = p_data['rank_score']
                                    if rank is not None:
                                        ratings_ranks.append((p_data['instance'].user_id, rating, rank))
                                    else:
                                        print(f"!!! Elo Warning: Missing rank for player {p_data['instance'].user_id}") # DEBUG
                                print(f"      Data for FFA Calc: {ratings_ranks}") # DEBUG
                                if len(ratings_ranks) == len(participants_data):
                                     new_elos = update_elo_ffa(ratings_ranks)
                                     print(f"      New Elos: {new_elos}") # DEBUG
                                     for user_id, new_elo in new_elos.items():
                                         profile_to_update = profiles[user_id]
                                         setattr(profile_to_update, elo_field, new_elo)
                                         profile_to_update.save()
                                     print("    FFA Elo updated and profiles saved.") # DEBUG
                                else:
                                     messages.error(request, "Missing rank data for some participants. FFA Elo not updated.")
                                     print("!!! Elo Error: Mismatch in FFA rank data.") # DEBUG
                             except Exception as e:
                                 print(f"!!! Elo Error during FFA processing: {e}") # DEBUG
                                 messages.error(request, f"Error calculating FFA Elo: {e}")

                         print("Finished Elo calculation and updates.") # DEBUG


                # --- Mark match as completed ---
                if match.status != 'completed':
                    print("Marking match as completed.") # DEBUG
                    match.status = 'completed'
                    match.save()

                messages.success(request, "Match results saved and Elo updated successfully.")
                print("--- Request successful. Redirecting... ---") # DEBUG
                return redirect('competition_detail', competition_id=competition.id)

            # Handle validation errors raised within the transaction
            except forms.ValidationError as e:
                formset.non_form_errors().append(e)
                messages.error(request, f"Please correct the errors: {str(e)}")
                print(f"!!! Validation Error inside try block: {e}") # DEBUG
                # Transaction automatically rolls back here

            # Handle other unexpected errors
            except Exception as e:
                 messages.error(request, f"An unexpected error occurred: {str(e)}")
                 formset.non_form_errors().append(f"An unexpected error occurred: {str(e)}")
                 print(f"!!! Unexpected Error inside try block: {e}") # DEBUG
                 # Consider logging the full traceback here for debugging
                 # Transaction automatically rolls back here

        else: # Formset is invalid
             messages.error(request, "Please correct the errors in the form(s) below.")
             print(f"!!! Formset is invalid: {formset.errors}") # DEBUG
             print(f"    Non-form errors: {formset.non_form_errors()}") # DEBUG
             # Transaction doesn't commit automatically, but no changes were made if formset invalid

    else: # GET request
        print("Processing GET request.") # DEBUG
        formset = MatchResultFormSet(queryset=match.participants.all().select_related('user'), **formset_kwargs)

    context = {
        'formset': formset,
        'match': match,
        'competition': competition,
        'is_editing': is_editing,
    }
    print("--- Rendering template... ---") # DEBUG
    return render(request, 'bookings/enter_match_results.html', context)


@login_required
@require_POST # Ensure this view only accepts POST requests
@csrf_exempt # Or handle CSRF token properly
@transaction.atomic # Good practice for DB modifications
def toggle_slot_availability(request):
    try:
        data = json.loads(request.body)
        time_slot_str = data.get('time_slot') # "HH:MM"
        selected_date_str = data.get('selected_date') # "YYYY-MM-DD"
        activity_type = data.get('activity_type')
        is_selected = data.get('is_selected') # boolean: true if adding, false if removing

        # --- Basic Input Validation ---
        if not all([time_slot_str, selected_date_str, activity_type, isinstance(is_selected, bool)]):
            return JsonResponse({"message": "Missing required parameters (time_slot, selected_date, activity_type, is_selected)."}, status=400)

        try:
            selected_date = date.fromisoformat(selected_date_str)
            hours, minutes = map(int, time_slot_str.split(':'))
            slot_start_time = time(hour=hours, minute=minutes)
            # Optional: Validate time is within allowed range (08:00 - 23:45)
            if not (8 <= hours <= 23):
                 raise ValueError("Time slot outside allowed range (08:00-23:45)")

        except (ValueError, TypeError) as e:
             return JsonResponse({"message": f"Invalid date or time format: {e}"}, status=400)

        if activity_type not in [choice[0] for choice in MatchAvailability._meta.get_field('booking_type').choices]:
             return JsonResponse({"message": "Invalid activity type."}, status=400)
        # --- End Validation ---

        # Calculate datetime objects
        start_datetime = datetime.combine(selected_date, slot_start_time)
        end_datetime = start_datetime + timedelta(minutes=15)

        if is_selected:
            # User wants to ADD or ensure this slot is available
            obj, created = MatchAvailability.objects.update_or_create(
                user=request.user,
                booking_type=activity_type,
                start_time=start_datetime,
                # Also match end_time in filter for update_or_create robustness? Depends on uniqueness.
                # Assuming start_time/user/activity is unique enough for a 15-min slot.
                defaults={
                    'end_time': end_datetime,
                    'is_available': True # Ensure it's marked available
                }
            )
            action = "created" if created else "updated (already existed)"
            print(f"DEBUG: Availability slot {action} for {request.user.username} at {start_datetime}")

        else:
            # User wants to REMOVE availability for this slot
            deleted_count, _ = MatchAvailability.objects.filter(
                user=request.user,
                booking_type=activity_type,
                start_time=start_datetime,
                # Optionally match end_time too for safety
                # end_time=end_datetime
            ).delete()
            action = "deleted" if deleted_count > 0 else "not found (already deleted)"
            print(f"DEBUG: Availability slot {action} for {request.user.username} at {start_datetime}")

        # Send success response
        return JsonResponse({"success": True, "message": f"Availability {action}."})

    except json.JSONDecodeError:
        return JsonResponse({"message": "Invalid JSON format."}, status=400)
    except Exception as e:
        # Log the full error for debugging
        print(f"!!! Error in toggle_slot_availability: {type(e).__name__} - {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({"message": "An unexpected server error occurred."}, status=500)

def leaderboard_view(request):
    """Display the leaderboard sorted by activity ratings."""
    # Get the sorting parameter from the request (default to 'pool_rating')
    sort_by = request.GET.get('sort_by', 'pool_rating')
  # Ensure the sorting parameter is valid
    if sort_by not in ['ranking_pool', 'ranking_switch', 'ranking_table_tennis']:
        # If invalid, default to 'pool_rating'
            sort_by = 'ranking_pool'

        # Fetch users and annotate with their ratings
    leaderboard = User.objects.select_related('userprofile').order_by(f'-userprofile__{sort_by}')

    return render(request, 'bookings/leaderboard.html', {
            'leaderboard': leaderboard,
            'sort_by': sort_by
        })

@login_required
def profile_view(request):
    """Display the profile and rankings of the logged-in user."""
    user = request.user
    userprofile = user.userprofile  # Assuming a UserProfile model exists

    return render(request, 'bookings/profile.html', {
        'user': user,
        'userprofile': userprofile,
    })
