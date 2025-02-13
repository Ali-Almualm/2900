from django.shortcuts import render

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
from datetime import datetime, timedelta
from .models import Booking  # ✅ Ensure this is correctly imported

@csrf_exempt
def api_book(request):
    if request.method == "POST":
        data = json.loads(request.body)
        
        start_time_str = data.get("start_time")
        user_id = data.get("user_id")
        name = data.get("name")
        booking_type = data.get("booking_type")

        try:
            start_time = datetime.strptime(start_time_str.split(" - ")[0], "%H:%M")
            today = datetime.now().date()
            start_time = datetime.combine(today, start_time.time())
            end_time = start_time + timedelta(minutes=15)

            # Check if slot is already booked
            if Booking.objects.filter(start_time=start_time).exists():
                return JsonResponse({"message": "This slot is already booked!"}, status=400)

            # Create booking
            Booking.objects.create(
                user_id=user_id,
                name=name,
                start_time=start_time,
                end_time=end_time,
                booking_type=booking_type
            )
            return JsonResponse({"message": "Booking created!"})
        except Exception as e:
            return JsonResponse({"message": f"Error: {str(e)}"}, status=400)

def index(request):
    # Define today's date
    today = datetime.now().date()

    # Generate time slots from 09:00 to 21:00 in 15-minute increments
    time_slots = []
    start_time = datetime.combine(today, datetime.min.time()).replace(hour=0, minute=0)  # 9:00 AM
    end_time = datetime.combine(today, datetime.min.time()).replace(hour=23, minute=59)  # 9:00 PM

    while start_time < end_time:
        time_slots.append((today, start_time.strftime("%H:%M") + " - " + (start_time + timedelta(minutes=15)).strftime("%H:%M")))
        start_time += timedelta(minutes=15)  # Move to next 15-minute slot

    # Fetch today's bookings
    bookings = Booking.objects.filter(start_time__date=today)

    # Prepare the timetable with booking statuses
    timetable = []
    for date, time_slot in time_slots:
        start_hour, start_minute = map(int, time_slot.split(" - ")[0].split(":"))
        start_time = datetime.combine(date, datetime.min.time()).replace(hour=start_hour, minute=start_minute)
        end_time = start_time + timedelta(minutes=15)

        # Check if the slot is booked
        booked = bookings.filter(start_time=start_time).first()

        timetable.append({
            "time_slot": time_slot,
            "status": "Booked" if booked else "Available",
            "name": booked.name if booked else None,
            "booking_type": booked.booking_type if booked else None
        })

    return render(request, 'bookings/index.html', {"timetable": timetable})

def book(request):
    return render(request, 'bookings/book.html')  # ✅ Corrected path

def cancel_booking(request, booking_id):
    Booking.objects.filter(id=booking_id).delete()
    return redirect('index')
