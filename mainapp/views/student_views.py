from datetime import datetime, date, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from mainapp.decorators import student_required
from mainapp.models import Schedule, DailyTrip, Booking, Route, Incident
from mainapp.services import get_available_seats
from mainapp.forms import StudentIncidentForm
from django.utils import timezone

@login_required
@user_passes_test(student_required)
def student_dashboard(request):
    """
    This view acts as the student's homepage, providing a snapshot of their immediate travel plans by listing active and upcoming bookings.
    
    It retrieves Booking objects associated with the logged-in student profile that have a status of either 'Confirmed' or 'Checked-In' and passes them to the dashboard template.
    """
    upcoming_bookings = Booking.objects.filter(student=request.user.student_profile, status__in=['Confirmed', 'Checked-In'])
    return render(request, 'mainapp/student/dashboard.html', {'my_trips': upcoming_bookings})

def global_map_view(request):
    """
    This view renders the general map interface that allows users to visualize routes and shuttle locations.
    
    It simply returns the map template, which relies on separate API endpoints to fetch the actual coordinate data asynchronously.
    """
    return render(request, 'mainapp/common/map_view.html')

@login_required
def view_routes_schedules(request):
    """
    This view displays a comprehensive list of all transport routes and their standard operating schedules for user reference.
    
    It queries the Route model and uses `prefetch_related` to efficiently load associated schedules and stop data in a single database hit to improve performance.
    """
    routes = Route.objects.prefetch_related('schedule_set', 'routestop_set__stop').all()
    return render(request, 'mainapp/common/routes_schedules.html', {'routes': routes})

@login_required
def view_schedule_trips(request, schedule_id):
    """
    This view lists the specific daily trips available for a chosen schedule on a selected date, calculating real-time seat availability for each.
    
    It filters DailyTrip objects by schedule and date, iterates through them to calculate remaining seats based on vehicle capacity, and constructs a list of data dictionaries for the template.
    """
    schedule = get_object_or_404(Schedule, schedule_id=schedule_id)
    
    date_str = request.GET.get('date')
    if date_str:
        try:
            selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            selected_date = timezone.now().date()
    else:
        selected_date = timezone.now().date()

    trips_query = DailyTrip.objects.filter(
        schedule=schedule, 
        trip_date=selected_date,
        status__in=['Scheduled', 'Delayed', 'In-Progress', 'Completed']
    ).order_by('planned_departure')

    trips_data = []
    for trip in trips_query:
        seats_left = get_available_seats(trip)
        
        capacity = 40 
        assignment = trip.driverassignment_set.first()
        if assignment:
            capacity = assignment.vehicle.capacity
        elif trip.schedule.default_vehicle:
            capacity = trip.schedule.default_vehicle.capacity

        trips_data.append({
            'trip': trip,
            'seats_left': seats_left,
            'capacity': capacity,
            'is_full': seats_left <= 0
        })

    context = {
        'schedule': schedule,
        'trips_data': trips_data,
        'selected_date': selected_date,
    }
    return render(request, 'mainapp/student/book_trips.html', context)

@login_required
@user_passes_test(student_required)
def reserve_seat(request, trip_id):
    """
    This function handles the logic for booking a seat, ensuring that the student isn't double-booked, doesn't have time conflicts, and that the bus has capacity.
    
    It calculates the duration of the requested trip (accounting for overnight travel), checks for overlaps with existing confirmed bookings, and verifies seat availability via a service function before creating the Booking record.
    """
    trip = get_object_or_404(DailyTrip, trip_id=trip_id)
    student = request.user.student_profile
    
    if request.method == 'POST':
        if Booking.objects.filter(student=student, trip=trip, status__in=['Confirmed', 'Checked-In']).exists():
            messages.error(request, "You have already booked a seat on this trip.")
            return redirect('view_schedule_trips', schedule_id=trip.schedule.schedule_id)

        req_start = trip.planned_departure
        
        dummy_date = date.today()
        sch_start = datetime.combine(dummy_date, trip.schedule.start_time)
        sch_end = datetime.combine(dummy_date, trip.schedule.end_time)
        
        if sch_end < sch_start:
            sch_end += timedelta(days=1)
            
        duration = sch_end - sch_start
        req_end = req_start + duration

        existing_bookings = Booking.objects.filter(
            student=student, 
            status='Confirmed',
            trip__trip_date__gte=trip.trip_date - timedelta(days=1),
            trip__trip_date__lte=trip.trip_date + timedelta(days=1)
        )

        for b in existing_bookings:
            exist_start = b.trip.planned_departure
            
            ex_sch_start = datetime.combine(dummy_date, b.trip.schedule.start_time)
            ex_sch_end = datetime.combine(dummy_date, b.trip.schedule.end_time)
            
            if ex_sch_end < ex_sch_start:
                ex_sch_end += timedelta(days=1)
                
            ex_duration = ex_sch_end - ex_sch_start
            exist_end = exist_start + ex_duration

            if req_start < exist_end and exist_start < req_end:
                messages.error(request, f"Time Clash! This overlaps with your trip on route '{b.trip.schedule.route.name}'.")
                return redirect('view_schedule_trips', schedule_id=trip.schedule.schedule_id)

        if get_available_seats(trip) > 0:
            Booking.objects.create(student=student, trip=trip, status='Confirmed')
            messages.success(request, "Seat reserved successfully!")
            return redirect('student_dashboard')
        else:
            messages.error(request, "Bus is full.")

    return render(request, 'mainapp/student/reserve_seat.html', {'trip': trip})

@login_required
@user_passes_test(student_required)
def check_in_booking(request, booking_id):
    """
    This view processes the boarding procedure, allowing a student to mark themselves as present on the bus if the trip is currently active.
    
    It verifies that the trip status is 'In-Progress', ensures the student isn't already checked into a different concurrent trip, and updates the Booking status to 'Checked-In'.
    """
    booking = get_object_or_404(Booking, booking_id=booking_id)
    
    if booking.student.user != request.user:
        return redirect('student_dashboard')
    
    active_checkin = Booking.objects.filter(
            student=request.user.student_profile, 
            status='Checked-In'
        ).exists()
    
    if active_checkin:
        messages.error(request, "You are already checked-in to another trip. Please complete that trip first.")
        return redirect('student_dashboard')
    
    if booking.trip.status == 'In-Progress':
        booking.status = 'Checked-In'
        booking.save()
        messages.success(request, "✅ Checked-In! Welcome aboard.")
    else:
        messages.error(request, "Cannot check in. The bus is not currently active.")

    return redirect('student_dashboard')

@login_required
@user_passes_test(student_required)
def cancel_booking(request, booking_id):
    """
    This view allows a student to voluntarily release their reserved seat, freeing it up for other users.
    
    It verifies that the booking belongs to the requesting user and updates the status to 'Cancelled' instead of deleting the record, preserving the data for historical analysis.
    """
    booking = get_object_or_404(Booking, booking_id=booking_id)

    if booking.student.user != request.user:
        messages.error(request, "You cannot cancel someone else's booking.")
        return redirect('student_dashboard')

    if booking.status == 'Cancelled':
        messages.warning(request, "This booking is already cancelled.")
    else:
        booking.status = 'Cancelled'
        booking.save()
        messages.success(request, "Booking cancelled successfully. Seat has been freed.")

    return redirect('student_dashboard')

@login_required
@user_passes_test(student_required)
def student_view_trips(request):
    """
    This view displays the complete history of a student's travel, including past completed trips and future reservations.
    
    It queries all Booking objects for the student profile, uses `select_related` to efficiently fetch route and trip details, and orders the results by date.
    """
    student = request.user.student_profile
    bookings = Booking.objects.filter(student=student).select_related(
        'trip', 'trip__schedule__route'
    ).order_by('-trip__trip_date')
    
    return render(request, 'mainapp/student/view_trips.html', {'trips': bookings})

@login_required
def report_incident(request):
    """
    This view provides a channel for students to submit feedback or report safety issues regarding the service.
    
    It renders a form for incident submission and, upon valid POST, saves the incident record with the status 'New', linked to the reporting user.
    """
    if request.method == 'POST':
        form = StudentIncidentForm(request.POST)
        if form.is_valid():
            incident = form.save(commit=False)
            incident.reported_by = request.user
            incident.status = 'New'
            
            incident.save()
            messages.success(request, "Report submitted. Thank you for your feedback.")
            return redirect('student_dashboard')
    else:
        form = StudentIncidentForm()
    
    return render(request, 'mainapp/student/report_incident.html', {'form': form})