from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from mainapp.decorators import driver_required
from mainapp.models import DriverAssignment, DailyTrip, CurrentLocation, Incident, Booking, Notification
from django.utils import timezone
from datetime import timedelta
from mainapp.forms import DriverIncidentForm
from django.contrib import messages
from django.urls import reverse

@login_required
@user_passes_test(driver_required)
def driver_dashboard(request):
    """
    1. Performs 'Lazy Cleanup': Auto-cancels trips that are >30 mins late and still 'Scheduled'.
    2. Displays the dashboard with valid upcoming trips.
    """
    driver_profile = request.user.driver_profile
    
    # 1. Get current aware datetime
    now = timezone.localtime()
    today = now.date()
    
    # 2. Define the Cutoff (e.g., 30 mins ago)
    # If now is 18:00, cutoff is 17:30.
    # Any trip scheduled before 17:30 that is still 'Scheduled' is considered missed.
    cutoff_datetime = now - timedelta(minutes=30)
    
    # 3. Bulk Update "Zombie" Trips
    # We filter by 'planned_departure__lt' (Less Than) the cutoff datetime.
    # Crucial: This compares DateTime vs DateTime, avoiding the previous TypeError.
    DailyTrip.objects.filter(
        driverassignment__driver=driver_profile,
        trip_date=today,
        status='Scheduled',
        planned_departure__lt=cutoff_datetime 
    ).update(status='Cancelled')

    # 4. Fetch Valid Assignments
    # The .exclude() will now hide the trips we just cancelled.
    assignments = DriverAssignment.objects.filter(
        driver=driver_profile, 
        trip__trip_date=today
    ).exclude(
        trip__status__in=['Completed', 'Cancelled']
    ).order_by('trip__planned_departure')

    return render(request, 'mainapp/driver/dashboard.html', {'assignments': assignments})

@login_required
@user_passes_test(driver_required)
def start_trip(request, trip_id):
    """
    Modified: Checks if it is the correct time before starting the trip.
    """
    trip = get_object_or_404(DailyTrip, trip_id=trip_id)
    
    # 1. Validation: Prevent starting too early (e.g., > 30 mins before)
    now = timezone.now()
    time_diff = trip.planned_departure - now
    
    # If the trip is in the future by more than 30 minutes
    if time_diff > timedelta(minutes=30):
        messages.error(request, f"Too early! You can only start this trip within 30 minutes of departure ({trip.planned_departure.strftime('%H:%M')}).")
        return redirect('view_trip_details', trip_id=trip.trip_id)

    # 2. State Transition (Only if not already active/done)
    if trip.status == 'Scheduled' or trip.status == 'Delayed':
        trip.status = 'In-Progress'
        trip.save()

        # Create initial location for tracking
        CurrentLocation.objects.update_or_create(
            trip=trip,
            defaults={'latitude': 2.9289, 'longitude': 101.6417}
        )
        messages.success(request, f"Trip #{trip.trip_id} Started.")

    elif trip.status == 'Completed':
        messages.warning(request, "This trip is already completed.")
        return redirect('driver_dashboard')

    return render(request, 'mainapp/driver/active_trip.html', {'trip': trip})

@login_required
@user_passes_test(driver_required)
def view_trip_details(request, trip_id):
    """
    New View: Displays trip details without changing its status.
    Solves the 'Bad UX' issue of accidental starts.
    """
    trip = get_object_or_404(DailyTrip, trip_id=trip_id)
    
    # Calculate if the 'Start' button should be enabled
    now = timezone.now()
    is_too_early = (trip.planned_departure - now) > timedelta(minutes=30)
    
    return render(request, 'mainapp/driver/trip_summary.html', {
        'trip': trip,
        'is_too_early': is_too_early
    })

@login_required
@user_passes_test(driver_required)
def notify_arrival(request, trip_id):
    """
    This view triggers an automated notification system to alert all confirmed passengers that their specific bus has arrived at the location.
    
    It queries for all 'Confirmed' bookings associated with the trip, generates a unique check-in URL for each, and creates a Notification record for each student user before redirecting the driver back to the active trip view.
    """
    trip = get_object_or_404(DailyTrip, trip_id=trip_id)
    
    confirmed_bookings = Booking.objects.filter(trip=trip, status='Confirmed')
    
    count = 0
    for booking in confirmed_bookings:
        check_in_url = request.build_absolute_uri(
                reverse('check_in_booking', args=[booking.booking_id])
            )
        Notification.objects.create(
            recipient=booking.student.user,
            sent_by=request.user,
            title="🚌 Bus Arrived!",
            message=f" The bus for {trip.schedule.route.name} has arrived. Please Check-In now."
        )
        count += 1
    
    messages.success(request, f"Sent arrival notification to {count} passengers.")
    return redirect('start_trip', trip_id=trip.trip_id)

@login_required
@user_passes_test(driver_required)
def driver_report_incident(request):
    """
    This view handles the submission of incident reports by drivers, automatically linking the report to the currently active trip if one exists and updating trip status if necessary.
    
    It checks for an 'In-Progress' trip assigned to the driver, processes the DriverIncidentForm, and if the 'mark_delayed' flag is set, it updates the DailyTrip status to 'Delayed' while saving the incident record.
    """
    active_trip = DailyTrip.objects.filter(
        driverassignment__driver=request.user.driver_profile,
        status='In-Progress'
    ).first()

    if request.method == 'POST':
        form = DriverIncidentForm(request.POST)
        if form.is_valid():
            incident = form.save(commit=False)
            incident.reported_by = request.user
            incident.status = 'New'
            
            if active_trip:
                incident.trip = active_trip
                
                if form.cleaned_data['mark_delayed']:
                    active_trip.status = 'Delayed'
                    active_trip.save()
                    messages.warning(request, "Trip marked as DELAYED.")

            incident.save()
            messages.success(request, "Incident reported to Coordinator.")
            return redirect('driver_dashboard')
    else:
        form = DriverIncidentForm()
    
    return render(request, 'mainapp/driver/report_incident.html', {
        'form': form, 
        'active_trip': active_trip
    })

@login_required
@user_passes_test(driver_required)
def finish_trip(request, trip_id):
    """
    This function concludes the trip lifecycle, finalizing the status of the trip itself and reconciling the attendance status of all associated passengers.
    
    It marks the DailyTrip as 'Completed', updates 'Checked-In' passengers to 'Completed', and bulk-updates any passengers who remained 'Confirmed' (but did not check in) to 'Cancelled' or missed status.
    """
    trip = get_object_or_404(DailyTrip, trip_id=trip_id)
    
    trip.status = 'Completed'
    trip.save()
    
    Booking.objects.filter(trip=trip, status='Checked-In').update(status='Completed')
    
    Booking.objects.filter(trip=trip, status='Confirmed').update(status='Cancelled')

    messages.success(request, "Trip ended. Passenger lists have been updated.")
    return redirect('driver_dashboard')