from datetime import datetime, date, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from mainapp.decorators import student_required
from mainapp.models import Schedule, DailyTrip, Booking, Route, Incident
from mainapp.services import get_available_seats
from mainapp.forms import StudentIncidentForm
from django.utils import timezone

def global_map_view(request):
    return render(request, 'mainapp/common/map_view.html')

@login_required
@user_passes_test(student_required)
def student_dashboard(request):
    # SDS 6.3.1: Dashboard with quick links
    upcoming_bookings = Booking.objects.filter(student=request.user.student_profile, status='Confirmed')
    return render(request, 'mainapp/student/dashboard.html', {'bookings': upcoming_bookings})

@login_required
@user_passes_test(student_required)
def reserve_seat(request, trip_id):
    trip = get_object_or_404(DailyTrip, trip_id=trip_id)
    student = request.user.student_profile
    
    if request.method == 'POST':
        # 1. CHECK DOUBLE BOOKING
        if Booking.objects.filter(student=student, trip=trip, status='Confirmed').exists():
            messages.error(request, "You have already booked a seat on this trip.")
            return redirect('view_schedule_trips', schedule_id=trip.schedule.schedule_id)

        # 2. CHECK TIME CLASHES (FIXED)
        req_start = trip.planned_departure
        
        # Calculate duration correctly handling overnight trips
        dummy_date = date.today()
        sch_start = datetime.combine(dummy_date, trip.schedule.start_time)
        sch_end = datetime.combine(dummy_date, trip.schedule.end_time)
        
        # FIX: If end time is earlier than start time, it means it ends the next day
        if sch_end < sch_start:
            sch_end += timedelta(days=1)
            
        duration = sch_end - sch_start
        req_end = req_start + duration

        # Get all other confirmed bookings for this student
        # Optimization: Filter for bookings roughly in the same time window (today/tomorrow)
        # to avoid fetching entire history.
        existing_bookings = Booking.objects.filter(
            student=student, 
            status='Confirmed',
            trip__trip_date__gte=trip.trip_date - timedelta(days=1),
            trip__trip_date__lte=trip.trip_date + timedelta(days=1)
        )

        for b in existing_bookings:
            exist_start = b.trip.planned_departure
            
            # Recalculate duration for existing trip (apply same overnight fix)
            ex_sch_start = datetime.combine(dummy_date, b.trip.schedule.start_time)
            ex_sch_end = datetime.combine(dummy_date, b.trip.schedule.end_time)
            
            if ex_sch_end < ex_sch_start:
                ex_sch_end += timedelta(days=1)
                
            ex_duration = ex_sch_end - ex_sch_start
            exist_end = exist_start + ex_duration

            # Overlap Logic
            if req_start < exist_end and exist_start < req_end:
                messages.error(request, f"Time Clash! This overlaps with your trip on route '{b.trip.schedule.route.name}'.")
                return redirect('view_schedule_trips', schedule_id=trip.schedule.schedule_id)

        # 3. CHECK SEAT AVAILABILITY
        if get_available_seats(trip) > 0:
            Booking.objects.create(student=student, trip=trip, status='Confirmed')
            messages.success(request, "Seat reserved successfully!")
            return redirect('student_dashboard')
        else:
            messages.error(request, "Bus is full.")

    return render(request, 'mainapp/student/reserve_seat.html', {'trip': trip})

@login_required
@user_passes_test(student_required)
def cancel_booking(request, booking_id):
    """
    Allows a student to cancel their own booking.
    """
    booking = get_object_or_404(Booking, booking_id=booking_id)

    # Security Check: Ensure the booking belongs to the logged-in student
    if booking.student.user != request.user:
        messages.error(request, "You cannot cancel someone else's booking.")
        return redirect('student_dashboard')

    if booking.status == 'Cancelled':
        messages.warning(request, "This booking is already cancelled.")
    else:
        # We change status to 'Cancelled' rather than deleting, to keep a record.
        # The 'get_available_seats' service already excludes 'Cancelled' bookings, so seat is freed.
        booking.status = 'Cancelled'
        booking.save()
        messages.success(request, "Booking cancelled successfully. Seat has been freed.")

    return redirect('student_dashboard')

@login_required
def view_routes_schedules(request):
    """
    Shared view for Students, Drivers, and Coordinators.
    Displays Routes with their associated Schedules and Stops.
    """
    # optimization: prefetch related data to avoid 100+ database queries
    routes = Route.objects.prefetch_related('schedule_set', 'routestop_set__stop').all()

    return render(request, 'mainapp/common/routes_schedules.html', {'routes': routes})

@login_required
def report_incident(request):
    if request.method == 'POST':
        form = StudentIncidentForm(request.POST)
        if form.is_valid():
            incident = form.save(commit=False)
            incident.reported_by = request.user
            incident.status = 'New'
            
            # Logic: If student has a booking for an active trip, we could auto-link it here.
            # For now, we leave trip empty or rely on description.
            
            incident.save()
            messages.success(request, "Report submitted. Thank you for your feedback.")
            return redirect('student_dashboard')
    else:
        form = StudentIncidentForm()
    
    return render(request, 'mainapp/student/report_incident.html', {'form': form})

@login_required
def view_schedule_trips(request, schedule_id):
    """
    Lists upcoming DailyTrips for a specific Schedule so a student can book one.
    """
    schedule = get_object_or_404(Schedule, schedule_id=schedule_id)
    
    # 1. Get upcoming trips (Today onwards)
    # In a real app, you'd filter by date >= today. 
    # For this demo, we just get all 'Scheduled' or 'In-Progress' trips.
    trips_query = DailyTrip.objects.filter(
        schedule=schedule, 
        status__in=['Scheduled', 'Delayed', 'In-Progress']
    ).order_by('trip_date', 'planned_departure')

    # 2. Calculate Availability for each trip
    # We create a custom list of dictionaries to pass to the template
    trips_data = []
    for trip in trips_query:
        seats_left = get_available_seats(trip)
        
        # Get capacity for display (e.g., "5 / 40 seats left")
        capacity = 0
        assignment = trip.driverassignment_set.first()
        if assignment:
            capacity = assignment.vehicle.capacity
            
        trips_data.append({
            'trip': trip,
            'seats_left': seats_left,
            'capacity': capacity,
            'is_full': seats_left <= 0
        })

    context = {
        'schedule': schedule,
        'trips_data': trips_data
    }
    return render(request, 'mainapp/student/view_trips.html', context)

@login_required
@user_passes_test(student_required)
def check_in_booking(request, booking_id):
    booking = get_object_or_404(Booking, booking_id=booking_id)
    
    # Security: Ensure it's their booking
    if booking.student.user != request.user:
        return redirect('student_dashboard')

    # Validation: Can only check in if trip is active
    if booking.trip.status != 'In-Progress':
        messages.error(request, "Cannot check in yet. The bus hasn't started the trip.")
    else:
        booking.status = 'Checked-In'
        booking.save()
        messages.success(request, "✅ Successfully Checked-In! Have a safe trip.")

    return redirect('student_dashboard')