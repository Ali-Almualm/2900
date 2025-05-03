from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import logout, login, authenticate
import json
from django.forms import modelformset_factory # Import formset factory
from django import forms
from django.http import JsonResponse
from datetime import datetime, timedelta, date
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
    date_str = request.GET.get('date', datetime.today().strftime('%Y-%m-%d'))
    selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()

    time_slots = []
    start_time = datetime.combine(selected_date, datetime.min.time()).replace(hour=8, minute=0)
    end_time = datetime.combine(selected_date, datetime.min.time()).replace(hour=23, minute=59)

    current = start_time
    while current < end_time:
        slot_end = current + timedelta(minutes=15)
        time_slots.append((current, slot_end)) # Store datetime objects
        current = slot_end

    bookings = Booking.objects.filter(start_time__date=selected_date)
    competitions = Competition.objects.filter(start_time__date=selected_date) # Fetch competitions

    ACTIVITY_TYPES = ["pool", "switch", "table_tennis"]
    timetable_by_activity = {activity: [] for activity in ACTIVITY_TYPES}

    for slot_start_time, slot_end_time in time_slots:
        time_slot_str = f"{slot_start_time.strftime('%H:%M')} - {slot_end_time.strftime('%H:%M')}"

        for activity in ACTIVITY_TYPES:
            slot_info = {
                "time_slot": time_slot_str,
                "start_datetime": slot_start_time, # Keep for potential use
                "status": "Available",
                "details": None,
                "type": "available", # 'available', 'booked', 'competition'
                "competition_id": None,
                "can_join_competition": False,
                "is_full": False,
                "booked_by_user": False,
                "booking_id": None,
                "user_id": None,
            }

            # 1. Check for Competitions first (they might override bookings in display)
            competition_entry = competitions.filter(
                activity_type=activity,
                start_time__lt=slot_end_time,
                end_time__gt=slot_start_time
            ).first()

            if competition_entry:
                slot_info.update({
                    "status": "Competition",
                    "details": f"Max: {competition_entry.max_joiners}, Joined: {competition_entry.participants.count()}",
                    "type": "competition",
                    "competition_id": competition_entry.id,
                    "is_full": competition_entry.is_full(),
                    "can_join_competition": request.user.is_authenticated and competition_entry.can_join(request.user),
                    "name": f"Comp by {competition_entry.creator.username}" # Indicate creator
                })
            else:
                # 2. Check for Bookings if no competition
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
        "selected_date": selected_date,
        "user": request.user # Ensure user is passed for template logic
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
    date_str = request.GET.get('date', date.today().strftime('%Y-%m-%d'))
    selected_date = date.fromisoformat(date_str) # More robust date parsing

    # Filter availabilities by the selected date and user
    availabilities = MatchAvailability.objects.filter(
        user=request.user,
        booking_type=activity_type,
        start_time__date=selected_date
    ).order_by('start_time')

    return render(request, 'bookings/match_availability.html', {
        'activity_type': activity_type,
        'match_availabilities': availabilities,
        'form': MatchAvailabilityForm(initial={'booking_type': activity_type}),
        'today': date.today(), # Add today's date to the context
        'selected_date': selected_date # Pass the selected date as well
    })


@login_required
@csrf_exempt
def update_match_availability(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        selected_times = data.get('times', [])
        activity_type = data.get('activity_type')
        selected_date = data.get('selected_date')
        
        if not activity_type or not selected_date:
            return JsonResponse({"message": "Missing activity type or date"}, status=400)
            
        selected_date = datetime.strptime(selected_date, '%Y-%m-%d').date()
        
        # Convert time strings to datetime objects
        availability_objects = []
        for time_str in selected_times:
            try:
                # Assuming time_str is like "09:00"
                hours, minutes = map(int, time_str.split(':'))
                start_time = datetime.combine(selected_date, datetime.min.time()).replace(
                    hour=hours, minute=minutes
                )
                end_time = start_time + timedelta(minutes=15)
                
                # Create or update availability
                availability, created = MatchAvailability.objects.get_or_create(
                    user=request.user,
                    booking_type=activity_type,
                    start_time=start_time,
                    end_time=end_time,
                    defaults={'is_available': True}
                )
                
                if not created:
                    availability.is_available = True
                    availability.save()
                    
                availability_objects.append(availability)
            except Exception as e:
                return JsonResponse({"message": f"Error processing time: {str(e)}"}, status=400)
                
        return JsonResponse({
            "message": f"Successfully updated {len(availability_objects)} availability slots",
            "count": len(availability_objects)
        })
        
    return JsonResponse({"message": "Invalid request method"}, status=400)

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
    """Find users who have matching availability for the given activity and handle pending requests."""
    user_profile = request.user.userprofile

    # Get the user's skill level for this activity
    if activity_type == 'pool':
        user_skill = user_profile.ranking_pool
    elif activity_type == 'switch':
        user_skill = user_profile.ranking_switch
    elif activity_type == 'table_tennis':
        user_skill = user_profile.ranking_table_tennis
    else:
        user_skill = 0

    # Get the user's availability for this activity
    user_match_availability = MatchAvailability.objects.filter(
        user=request.user,
        booking_type=activity_type,
        is_available=True
    )

    if not user_match_availability.exists():
        return render(request, 'bookings/matches.html', {
            'activity_type': activity_type,
            'matches': [],
            'pending_requests': [],
            'error': 'You need to set your match availability before finding matches'
        })

    # Find all other users with availability for this activity
    matches = []
    other_users = User.objects.exclude(id=request.user.id)

    for other_user in other_users:
        # Get their availability
        other_match_availability = MatchAvailability.objects.filter(
            user=other_user,
            booking_type=activity_type,
            is_available=True
        )

        if not other_match_availability.exists():
            continue

        # Check for overlapping availability
        overlapping_times = []

        for user_slot in user_match_availability:
            for other_slot in other_match_availability:
                # Check if times overlap
                if (user_slot.start_time < other_slot.end_time and
                        user_slot.end_time > other_slot.start_time):

                    # Calculate the overlap period
                    overlap_start = max(user_slot.start_time, other_slot.start_time)
                    overlap_end = min(user_slot.end_time, other_slot.end_time)

                    overlapping_times.append({
                        'start': overlap_start,
                        'end': overlap_end,
                        'duration_minutes': (overlap_end - overlap_start).total_seconds() / 60
                    })

        if overlapping_times:
            # Get other user's skill level
            try:
                other_profile = other_user.userprofile
                if activity_type == 'pool':
                    other_skill = other_profile.ranking_pool
                elif activity_type == 'switch':
                    other_skill = other_profile.ranking_switch
                elif activity_type == 'table_tennis':
                    other_skill = other_profile.ranking_table_tennis
                else:
                    other_skill = 0

                # Calculate skill difference
                skill_difference = abs(user_skill - other_skill)

                matches.append({
                    'user': other_user,
                    'overlapping_times': overlapping_times,
                    'skill_level': other_skill,
                    'skill_difference': skill_difference
                })
            except UserProfile.DoesNotExist:
                continue

    # Sort matches by skill difference (closer matches first)
    matches.sort(key=lambda x: x['skill_difference'])

    # Fetch pending match requests for the logged-in user
    pending_requests = BookingRequestmatch.objects.filter(
        requested_player=request.user,
        is_confirmed=False,
        is_rejected=False
    )

    return render(request, 'bookings/matches.html', {
        'activity_type': activity_type,
        'matches': matches,
        'pending_requests': pending_requests
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
@csrf_exempt
def respond_to_match_request(request, booking_request_id):
    """Respond to a match request by confirming or rejecting it."""
    if request.method == 'POST':
        action = request.POST.get('action')  # 'confirm' or 'reject'
        try:
            booking_request = BookingRequestmatch.objects.get(id=booking_request_id, requested_player=request.user)

            if action == 'confirm':
                # Create a new booking and populate the opponent field
                booking = Booking.objects.create(
                    user_id=request.user.id,
                    opponent=booking_request.requester,  # Populate the opponent field
                    name=f"Match between {booking_request.requester.username} and {request.user.username}",
                    start_time=booking_request.start_time,
                    end_time=booking_request.end_time,
                    booking_type=booking_request.activity_type
                )

                # Remove overlapping match availability timeslots for both users
                MatchAvailability.objects.filter(
                    Q(user=request.user) | Q(user=booking_request.requester),
                    Q(start_time__lt=booking_request.end_time, end_time__gt=booking_request.start_time)
                ).delete()

                booking_request.is_confirmed = True
                booking_request.save()
                return JsonResponse({'success': True, 'message': 'Booking confirmed and created successfully'})

            elif action == 'reject':
                booking_request.is_rejected = True
                booking_request.save()
                return JsonResponse({'success': True, 'message': 'Match request rejected'})

        except BookingRequestmatch.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Match request does not exist'}, status=404)

    return JsonResponse({'success': False, 'message': 'Invalid request method'}, status=400)


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

        # Check for time conflicts with user's existing bookings/competitions (optional but good)
        user_bookings = Booking.objects.filter(
            user_id=str(user.id), # Assuming user_id is string in Booking model
            start_time__lt=competition.end_time,
            end_time__gt=competition.start_time
        )
        user_competitions = CompetitionParticipant.objects.filter(
            user=user,
            competition__start_time__lt=competition.end_time,
            competition__end_time__gt=competition.start_time
        ).exclude(competition=competition) # Don't compare with itself

        if user_bookings.exists() or user_competitions.exists():
             return JsonResponse({'success': False, 'message': 'You have a time conflict with this competition.'}, status=400)


        # Join the competition
        CompetitionParticipant.objects.create(competition=competition, user=user)
        return JsonResponse({'success': True, 'message': 'Successfully joined the competition!'})

    return JsonResponse({'success': False, 'message': 'Invalid request method.'}, status=405)

@login_required
def match_history_view(request):
    """Display the match history for the logged-in user."""
    match_history = Booking.objects.filter(
        models.Q(user_id=str(request.user.id)) | models.Q(opponent=request.user)
    ).order_by('-start_time')

    # Debugging: Print match history to the console
    print("Match History Queryset:")
    for match in match_history:
        print(f"Match ID: {match.id}, User ID: {match.user_id}, Opponent: {match.opponent}, User Result: {match.user_result}, Opponent Result: {match.opponent_result}")

    return render(request, 'bookings/match_history.html', {
        'match_history': match_history
    })

@login_required
@csrf_exempt
def confirm_result_view(request, booking_id):
    """Allow players to confirm the result of a match."""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            result = data.get('result')  # 'win' or 'loss'

            # Fetch the booking
            booking = Booking.objects.get(id=booking_id)

            # Ensure the logged-in user is part of the match
            if str(request.user.id) == booking.user_id:
                # Update the user's result
                booking.user_result = result
            elif request.user == booking.opponent:
                # Update the opponent's result
                booking.opponent_result = result
            else:
                return JsonResponse({'success': False, 'message': 'You are not part of this match.'}, status=403)

            # Save the updated booking
            booking.save()

            return JsonResponse({'success': True, 'message': 'Result updated successfully.'})
        except Booking.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Match not found.'}, status=404)
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)

    return JsonResponse({'success': False, 'message': 'Invalid request method.'}, status=400)


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
def enter_match_results(request, match_id):
    """Allows the competition creator to enter OR EDIT results for a specific match."""
    # Fetch related competition to minimize queries
    match = get_object_or_404(CompetitionMatch.objects.select_related('competition'), id=match_id)
    competition = match.competition

    # --- Permission Checks ---
    if request.user != competition.creator:
        messages.error(request, "You are not authorized to enter or edit results for this match.")
        return redirect('competition_detail', competition_id=competition.id)

    # Cannot edit results if OVERALL competition is completed
    if competition.status == 'completed':
        messages.warning(request, "Cannot enter or edit results for a completed competition.")
        return redirect('competition_detail', competition_id=competition.id)

    # Check if participants are assigned (needed before results)
    if not match.participants.exists():
        messages.error(request, "Participants must be assigned before entering results.")
        return redirect('assign_match_participants', match_id=match.id)
    # --- End Permission Checks ---

    # Determine if we are editing existing results (for template display)
    is_editing = match.status == 'completed'

    # Use modelformset_factory to edit existing MatchParticipant results
    MatchResultFormSet = modelformset_factory(
        MatchParticipant,
        form=MatchResultForm,
        fields=('result_simple', 'result_rank_score'), # Fields editable via the custom form logic
        extra=0 # Don't allow adding new participants here
    )

    # Pass match_type to the forms within the formset for dynamic field display/validation
    formset_kwargs = {'form_kwargs': {'match_type': match.match_type}}

    if request.method == 'POST':
        # Provide the queryset for validation/saving existing instances
        formset = MatchResultFormSet(request.POST, queryset=match.participants.all().select_related('user'), **formset_kwargs)

        if formset.is_valid():
            try:
                # Use a transaction to ensure all results save or none do
                with transaction.atomic():
                    participants_data = {} # To store cleaned data for cross-form validation
                    ranks_entered = set() # For FFA duplicate rank check
                    teams_results = {} # For 2v2 team result consistency check

                    # Loop through each form in the formset
                    for form in formset:
                        # Although formset.is_valid() passed, individual form errors might exist
                        # if cleaned but not saved yet. Re-check validity is safer.
                        # Only process forms that have actually changed to avoid unnecessary saves
                        if form.is_valid() and form.has_changed():
                            instance = form.instance # The MatchParticipant instance being edited
                            result_simple = form.cleaned_data.get('result_simple')
                            result_rank_score = form.cleaned_data.get('result_rank_score')

                            # Store cleaned data for later validation
                            participants_data[instance.id] = {
                                'instance': instance,
                                'simple': result_simple,
                                'rank_score': result_rank_score,
                                'team': instance.team
                            }

                            # --- Update the MatchParticipant instance based on match type ---
                            if match.match_type == 'ffa':
                                # Validate rank/score for FFA
                                if result_rank_score is None or result_rank_score < 1:
                                    form.add_error('result_rank_score', f"Invalid rank/score for {instance.user.username}.")
                                    raise forms.ValidationError("Invalid rank/score entered.") # Raise to trigger rollback

                                if result_rank_score in ranks_entered:
                                    form.add_error('result_rank_score', f"Duplicate rank/score '{result_rank_score}'.")
                                    raise forms.ValidationError("Duplicate rank/score entered.")
                                ranks_entered.add(result_rank_score)

                                # Set the appropriate result fields
                                instance.result_type = 'rank' # Or 'score' if using scores
                                instance.result_value = result_rank_score
                                instance.save() # Save the updated participant result

                            elif match.match_type in ['1v1', '2v2']:
                                # Validate simple result for 1v1/2v2
                                if not result_simple or result_simple == 'pending' or result_simple == '': # Check blank choice too
                                    form.add_error('result_simple', f"Select Win/Loss/Draw for {instance.user.username}.")
                                    raise forms.ValidationError("Result not selected.")

                                # Set the appropriate result fields
                                instance.result_type = result_simple
                                instance.result_value = None # Clear rank/score value
                                instance.save() # Save the updated participant result

                                # Store team results for 2v2 cross-validation
                                if match.match_type == '2v2':
                                    team = instance.team
                                    if not team: # Should have been set during assignment
                                        form.add_error(None, f"Team missing for {instance.user.username} in 2v2 match.")
                                        raise forms.ValidationError("Team missing for 2v2.")
                                    if team not in teams_results: teams_results[team] = set()
                                    teams_results[team].add(result_simple)

                    # --- Post-loop Cross-Form Validation ---
                    num_participants_processed = len(participants_data)
                    num_total_participants = match.participants.count()

                    # Ensure all participants were processed (unless formset had issues)
                    if num_participants_processed != num_total_participants and formset.is_valid():
                         # This case might indicate an issue if some forms didn't change but results are incomplete
                         pass # Or add stricter checks if needed

                    if match.match_type == '1v1':
                        if num_participants_processed != 2:
                             raise forms.ValidationError("Expected results for exactly 2 participants in 1v1.")
                        results = [p['simple'] for p in participants_data.values()]
                        if not ( (results.count('win') == 1 and results.count('loss') == 1) or \
                                 (results.count('draw') == 2) ):
                            raise forms.ValidationError("Invalid results for 1v1. Must be one Win & one Loss, or two Draws.")

                    elif match.match_type == '2v2':
                        if num_participants_processed != 4:
                             raise forms.ValidationError("Expected results for exactly 4 participants in 2v2.")
                        if len(teams_results) != 2:
                            raise forms.ValidationError("Expected results for exactly two teams (e.g., 'A' and 'B') in 2v2.")

                        team_results_list = list(teams_results.values())
                        # Check all players in a team have the same result
                        if not all(len(res) == 1 for res in team_results_list):
                             raise forms.ValidationError("All players in the same team must have the same result (Win, Loss, or Draw).")
                        # Check team results are consistent (W/L or D/D)
                        team_results_flat = [list(res)[0] for res in team_results_list]
                        if not ( ('win' in team_results_flat and 'loss' in team_results_flat) or \
                                 (team_results_flat.count('draw') == 2) ):
                             raise forms.ValidationError("Invalid team results for 2v2. Must be one team Win/one team Loss, or both teams Draw.")

                    elif match.match_type == 'ffa':
                        # Ensure all participants have results if validation passed loop
                        if num_participants_processed != num_total_participants:
                             raise forms.ValidationError("Not all participants have valid results entered for FFA.")
                        # Optional: Check if ranks are consecutive integers from 1
                        # sorted_ranks = sorted(list(ranks_entered))
                        # if sorted_ranks != list(range(1, len(sorted_ranks) + 1)):
                        #     raise forms.ValidationError("Ranks must be consecutive positive integers starting from 1.")


                    # If all validation passes, mark match as completed (or ensure it stays completed)
                    if match.status != 'completed':
                        match.status = 'completed'
                        match.save()

                # --- End Transaction ---

                # Success message outside the transaction block
                messages.success(request, "Match results saved successfully.")
                return redirect('competition_detail', competition_id=competition.id)

            # Handle validation errors raised within the transaction
            except forms.ValidationError as e:
                # Add error to non_form_errors for display in template
                formset.non_form_errors().append(e)
                messages.error(request, f"Please correct the errors: {str(e)}")
                # The invalid formset will be re-rendered below

            # Handle other unexpected errors
            except Exception as e:
                messages.error(request, f"An unexpected error occurred: {str(e)}")
                formset.non_form_errors().append(f"An unexpected error occurred: {str(e)}")
                # Consider logging the full traceback here for debugging
                # The formset might be in an inconsistent state, re-rendering might show errors

        else: # Formset is invalid (individual form fields failed validation)
             messages.error(request, "Please correct the errors in the form(s) below.")
             # The invalid formset will be re-rendered below

    else: # GET request
        # Load existing participant data into the formset for display/editing
        formset = MatchResultFormSet(queryset=match.participants.all().select_related('user'), **formset_kwargs)

    # Prepare context for rendering
    context = {
        'formset': formset,
        'match': match,
        'competition': competition,
        'is_editing': is_editing, # Pass flag for template heading adjustment
    }
    # Render the same template for both GET and POST (if validation fails)
    return render(request, 'bookings/enter_match_results.html', context)
