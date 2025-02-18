from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
from datetime import datetime, timedelta
from .models import Booking  # ✅ Ensure this is correctly imported
from .forms import BookingForm


@csrf_exempt
def api_book(request):
    if request.method == "POST":
        data = json.loads(request.body)
        
        start_time_str = data.get("start_time")
        user_id = data.get("user_id")
        name = data.get("name")
        booking_type = data.get("booking_type")
        selected_date_str = data.get("booking_date")  # ✅ Get selected date from frontend

        try:
            # Convert date and time to datetime object
            selected_date = datetime.strptime(selected_date_str, "%Y-%m-%d").date()
            start_time = datetime.strptime(start_time_str.split(" - ")[0], "%H:%M").time()
            start_datetime = datetime.combine(selected_date, start_time)
            end_datetime = start_datetime + timedelta(minutes=15)

            # Check if slot is already booked for the same activity type
            if Booking.objects.filter(start_time=start_datetime, booking_type=booking_type).exists():
                return JsonResponse({"message": "This slot is already booked for this activity!"}, status=400)

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
    from datetime import datetime, timedelta
    from .models import Booking

    # ✅ Get selected date from query parameters (default to today)
    date_str = request.GET.get('date', datetime.today().strftime('%Y-%m-%d'))
    selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()

    # ✅ Generate 15-minute time slots for the selected date
    time_slots = []
    start_time = datetime.combine(selected_date, datetime.min.time()).replace(hour=0, minute=0)
    end_time = datetime.combine(selected_date, datetime.min.time()).replace(hour=23, minute=59)

    while start_time < end_time:
        time_slots.append(start_time.strftime("%H:%M") + " - " + (start_time + timedelta(minutes=15)).strftime("%H:%M"))
        start_time += timedelta(minutes=15)

    # ✅ Fetch all bookings for the selected date
    bookings = Booking.objects.filter(start_time__date=selected_date)

    # ✅ Organize timetable per activity type
    ACTIVITY_TYPES = ["pool", "switch", "table_tennis"]
    timetable_by_activity = {activity: [] for activity in ACTIVITY_TYPES}

    for time_slot in time_slots:
        start_hour, start_minute = map(int, time_slot.split(" - ")[0].split(":"))
        slot_start_time = datetime.combine(selected_date, datetime.min.time()).replace(hour=start_hour, minute=start_minute)
        slot_end_time = slot_start_time + timedelta(minutes=15)

        for activity in ACTIVITY_TYPES:
            # ✅ Check if this time slot is booked
            booked_entry = bookings.filter(start_time=slot_start_time, booking_type=activity).first()

            # ✅ If booked, store the name and mark as "Booked"
            timetable_by_activity[activity].append({
                "time_slot": time_slot,
                "status": "Booked" if booked_entry else "Available",
                "name": booked_entry.name if booked_entry else None,
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
            return redirect('index')  # or redirect to a specific activity page
    else:
        form = BookingForm()

    return render(request, 'bookings/book.html', {
        'form': form,
        'activity': activity_type
    })


def cancel_booking(request, booking_id):
    Booking.objects.filter(id=booking_id).delete()
    return redirect('index')

def activity_view(request, activity_type):
    # Let user pick the date just like index
    date_str = request.GET.get('date', datetime.today().strftime('%Y-%m-%d'))
    selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()

    # Generate 15-min slots from 00:00 to 23:59
    start_time = datetime.combine(selected_date, datetime.min.time()).replace(hour=0, minute=0)
    end_time = datetime.combine(selected_date, datetime.min.time()).replace(hour=23, minute=59)

    time_slots = []
    current = start_time
    while current < end_time:
        slot_end = current + timedelta(minutes=15)
        time_slots.append((current.time(), slot_end.time()))
        current = slot_end

    # Filter bookings for that date & activity
    bookings = Booking.objects.filter(
        start_time__date=selected_date,
        booking_type=activity_type
    ).order_by('start_time')

    timetable = []
    for slot_start, slot_end in time_slots:
        occupied = False
        booked_by = ""
        for booking in bookings:
            # Compare times
            if booking.start_time.time() == slot_start:
                occupied = True
                booked_by = booking.name
                break

        timetable.append({
            "time_slot": f"{slot_start.strftime('%H:%M')} - {slot_end.strftime('%H:%M')}",
            "status": "Booked" if occupied else "Available",
            "name": booked_by
        })

    return render(request, 'bookings/activity.html', {
        "timetable": timetable,
        "activity": activity_type,
        "selected_date": selected_date,
        "title": dict(Booking.BOOKING_TYPES).get(activity_type)
    })
