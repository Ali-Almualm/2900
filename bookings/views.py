from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
from datetime import datetime, timedelta
from .models import Booking
from .forms import BookingForm


@csrf_exempt
def api_book(request):
    if request.method == "POST":
        data = json.loads(request.body)
        
        time_range = data.get("start_time")  # e.g., "09:00 - 10:30"
        user_id = data.get("user_id")
        name = data.get("name")
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
                user_id=user_id,
                name=name,
                start_time=start_datetime,
                end_time=end_datetime,
                booking_type=booking_type
            )
            return JsonResponse({"message": "Booking created!"})
        except Exception as e:
            return JsonResponse({"message": f"Error: {str(e)}"}, status=400)


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


def cancel_booking(request, booking_id):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            user_id_input = data.get("user_id", "").strip()

            booking = Booking.objects.filter(id=booking_id).first()
            if not booking:
                return JsonResponse({"message": "Booking not found"}, status=404)

            stored_user_id = booking.user_id.strip()
            if user_id_input != stored_user_id:
                return JsonResponse({"message": "Unauthorized: Incorrect user ID"}, status=403)

            booking.delete()
            return JsonResponse({"message": "Booking canceled successfully"})
        except Exception as e:
            return JsonResponse({"message": f"Error: {str(e)}"}, status=400)


def activity_view(request, activity_type):
    from datetime import datetime, timedelta
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
