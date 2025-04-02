from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import logout, login, authenticate
import json
from django.http import JsonResponse
from datetime import datetime, timedelta, date
from .models import Booking, UserProfile, MatchAvailability 
#  SE HER!!!!!!! MATCH
from .forms import BookingForm, registrationform, loginform, MatchAvailabilityForm 
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
    # Get selected date from query parameters (default to today)
    date_str = request.GET.get('date', datetime.today().strftime('%Y-%m-%d'))
    selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()

    # Generate 15-minute time slots for the selected date
    time_slots = []
    start_time = datetime.combine(selected_date, datetime.min.time()).replace(hour=0, minute=0)
    end_time = datetime.combine(selected_date, datetime.min.time()).replace(hour=23, minute=59)

    while start_time < end_time:
        slot_str = f"{start_time.strftime('%H:%M')} - {(start_time + timedelta(minutes=15)).strftime('%H:%M')}"
        time_slots.append(slot_str)
        start_time += timedelta(minutes=15)

    # Fetch all bookings for the selected date
    bookings = Booking.objects.filter(start_time__date=selected_date)

    # Organize timetable per activity type
    ACTIVITY_TYPES = ["pool", "switch", "table_tennis"]
    timetable_by_activity = {activity: [] for activity in ACTIVITY_TYPES}

    for time_slot in time_slots:
        # Parse out the slot's start/end times
        start_str, end_str = time_slot.split(" - ")
        start_hour, start_minute = map(int, start_str.split(":"))
        slot_start_time = datetime.combine(selected_date, datetime.min.time()).replace(
            hour=start_hour, minute=start_minute
        )
        slot_end_time = slot_start_time + timedelta(minutes=15)

        for activity in ACTIVITY_TYPES:
            # Check for any booking that overlaps this 15-min slot
            booked_entry = bookings.filter(
                booking_type=activity,
                start_time__lt=slot_end_time,
                end_time__gt=slot_start_time
            ).first()

            timetable_by_activity[activity].append({
                "time_slot": time_slot,
                "status": "Booked" if booked_entry else "Available",
                "name": booked_entry.name if booked_entry else None,
                "booking_id": booked_entry.id if booked_entry else None,
                "user_id": booked_entry.user_id if booked_entry else None,
                "booking_type": activity
            })

    return render(request, 'bookings/index.html', {
        "timetable_by_activity": timetable_by_activity,
        "selected_date": selected_date
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
    """Find users who have matching availability for the given activity"""
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
    user_match_availability  = MatchAvailability.objects.filter(
        user=request.user,
        booking_type=activity_type,
        is_available=True
    )
    
    if not user_match_availability .exists():
        return render(request, 'bookings/matches.html', {
            'activity_type': activity_type,
            'matches': [],
            'error': 'You need to set your match availability before finding matches'
        })
    
    # Find all other users with availability for this activity
    matches = []
    other_users = User.objects.exclude(id=request.user.id)
    
    for other_user in other_users:
        # Get their availability
        other_match_availability  = MatchAvailability.objects.filter(
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
    
    return render(request, 'bookings/matches.html', {
        'activity_type': activity_type,
        'matches': matches
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
    # Get selected date (default to today)
    date_str = request.GET.get('date', datetime.today().strftime('%Y-%m-%d'))
    selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()

    # Generate 15-minute slots for the day (from 00:00 to 23:59)
    start_time = datetime.combine(selected_date, datetime.min.time()).replace(hour=0, minute=0)
    end_time = datetime.combine(selected_date, datetime.min.time()).replace(hour=23, minute=59)
    time_slots = []
    current = start_time
    while current < end_time:
        slot_end = current + timedelta(minutes=15)
        time_slots.append((current.time(), slot_end.time()))
        current = slot_end

    # Get all bookings for this date and activity
    bookings = Booking.objects.filter(
        start_time__date=selected_date,
        booking_type=activity_type
    ).order_by('start_time')

    # Build the timetable: for each 15-minute slot, check for overlap with a booking
    timetable = []
    for slot_start, slot_end in time_slots:
        slot_start_str = slot_start.strftime("%H:%M")
        slot_end_str = slot_end.strftime("%H:%M")
        time_slot_str = f"{slot_start_str} - {slot_end_str}"

        # Combine the slot times with the selected date to get full datetimes
        full_slot_start = datetime.combine(selected_date, slot_start)
        full_slot_end = datetime.combine(selected_date, slot_end)

        # Check for any booking overlapping this slot (i.e. booking starts before slot end and ends after slot start)
        booking_found = bookings.filter(
            start_time__lt=full_slot_end,
            end_time__gt=full_slot_start
        ).first()

        if booking_found:
            occupied = True
            booked_by = booking_found.name
            booking_id = booking_found.id
            user_id = booking_found.user_id  # Ensure this is stored as a string (e.g. the user's email)
        else:
            occupied = False
            booked_by = ""
            booking_id = ""
            user_id = ""

        timetable.append({
            "time_slot": time_slot_str,
            "start_time": slot_start_str,
            "status": "Booked" if occupied else "Available",
            "name": booked_by,
            "booking_id": booking_id,
            "user_id": user_id
        })

    return render(request, 'bookings/activity.html', {
        "timetable": timetable,
        "activity": activity_type,
        "selected_date": selected_date,
        "title": dict(Booking.BOOKING_TYPES).get(activity_type)
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