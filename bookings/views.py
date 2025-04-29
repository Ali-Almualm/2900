from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import logout, login, authenticate
import json
from django.http import JsonResponse
from datetime import datetime, timedelta, date
from django.contrib import messages
from django.urls import reverse # For redirects

from .models import Booking, UserProfile, MatchAvailability , BookingRequestmatch, Competition, CompetitionParticipant
#  SE HER!!!!!!! MATCH
from django.contrib.auth.models import User
from .forms import BookingForm, registrationform, loginform, MatchAvailabilityForm, CompetitionForm
from django.contrib.auth.decorators import login_required

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
    start_time = datetime.combine(selected_date, datetime.min.time()).replace(hour=0, minute=0)
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

    start_time = datetime.combine(selected_date, datetime.min.time()).replace(hour=0, minute=0)
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
            slot_info.update({
                "status": "Competition",
                "details": f"Max: {competition_entry.max_joiners}, Joined: {competition_entry.participants.count()}",
                "type": "competition",
                "competition_id": competition_entry.id,
                "is_full": competition_entry.is_full(),
                 "can_join_competition": request.user.is_authenticated and competition_entry.can_join(request.user),
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
                # Create a new booking automatically
                Booking.objects.create(
                    user_id=request.user.id,
                    name=f"Match between {booking_request.requester.username} and {request.user.username}",
                    start_time=booking_request.start_time,
                    end_time=booking_request.end_time,
                    booking_type=booking_request.activity_type
                )
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

