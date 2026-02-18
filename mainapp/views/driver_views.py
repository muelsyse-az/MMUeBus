from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from mainapp.decorators import driver_required
from mainapp.models import DriverAssignment, DailyTrip, CurrentLocation, Incident, Booking, Notification
from django.utils import timezone
from datetime import timedelta
from mainapp.forms import DriverIncidentForm
from django.contrib import messages
from django.urls import reverse

# --- Helper Function ---
def get_active_trip(user):
    """Returns the currently active 'In-Progress' trip for the driver, if any."""
    if hasattr(user, 'driver_profile'):
        return DailyTrip.objects.filter(
            driverassignment__driver=user.driver_profile,
            status='In-Progress'
        ).first()
    return None

@login_required
@user_passes_test(driver_required)
def driver_dashboard(request):
    """
    1. Performs 'Lazy Cleanup': Auto-cancels trips that are >30 mins late and still 'Scheduled'.
    2. Displays the dashboard with valid upcoming trips.
    3. NEW: Locks navigation if a trip is In-Progress.
    """
    # --- 0. Safety Lock: Redirect if Trip is In-Progress ---
    active_trip = get_active_trip(request.user)
    if active_trip:
        messages.warning(request, f"You have an active trip (Trip #{active_trip.trip_id}). Please complete it first.")
        return redirect('start_trip', trip_id=active_trip.trip_id)
    # -------------------------------------------------------

    driver_profile = request.user.driver_profile
    
    # 1. Get current aware datetime
    now = timezone.localtime()
    today = now.date()
    
    # 2. Define the Cutoff (e.g., 30 mins ago)
    cutoff_datetime = now - timedelta(minutes=30)
    
    # 3. Bulk Update "Zombie" Trips
    DailyTrip.objects.filter(
        driverassignment__driver=driver_profile,
        trip_date=today,
        status='Scheduled',
        planned_departure__lt=cutoff_datetime 
    ).update(status='Cancelled')

    # 4. Fetch Valid Assignments
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
    Now initializes location based on the Route's first stop.
    NEW: Enforces focus on the currently active trip.
    """
    # --- 0. Safety Lock: Ensure we are on the correct active trip ---
    active_trip = get_active_trip(request.user)
    if active_trip and active_trip.trip_id != int(trip_id):
        messages.error(request, "You cannot start a new trip while another is active!")
        return redirect('start_trip', trip_id=active_trip.trip_id)
    # ----------------------------------------------------------------

    trip = get_object_or_404(DailyTrip, trip_id=trip_id)
    
    # 1. Validation: Prevent starting too early (e.g., > 30 mins before)
    # Skip this check if the trip is ALREADY In-Progress (just refreshing page)
    if trip.status != 'In-Progress':
        now = timezone.now()
        time_diff = trip.planned_departure - now
        
        if time_diff > timedelta(minutes=30):
            messages.error(request, f"Too early! You can only start this trip within 30 minutes of departure ({trip.planned_departure.strftime('%H:%M')}).")
            return redirect('view_trip_details', trip_id=trip.trip_id)

    # 2. State Transition (Only if not already active/done)
    if trip.status == 'Scheduled' or trip.status == 'Delayed':
        trip.status = 'In-Progress'
        trip.save()

        # FIX: Dynamically fetch the Start Point coordinates from the route
        first_stop = trip.schedule.route.routestop_set.order_by('sequence_no').first()
        
        if first_stop:
            initial_lat = first_stop.stop.latitude
            initial_lng = first_stop.stop.longitude
        else:
            # Fallback only if no stops exist
            initial_lat = 2.9289
            initial_lng = 101.6417

        # Create initial location for tracking
        CurrentLocation.objects.update_or_create(
            trip=trip,
            defaults={'latitude': initial_lat, 'longitude': initial_lng}
        )
        if trip.status == 'Scheduled': # Only show message on first start
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
    NEW: Locks navigation if another trip is In-Progress.
    """
    # --- 0. Safety Lock: Redirect if Trip is In-Progress ---
    active_trip = get_active_trip(request.user)
    if active_trip and active_trip.trip_id != int(trip_id):
        messages.warning(request, "Please complete your active trip first.")
        return redirect('start_trip', trip_id=active_trip.trip_id)
    # -------------------------------------------------------

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
    This view triggers an automated notification system to alert all confirmed passengers.
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
    This view handles the submission of incident reports by drivers.
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
            # Redirect to dashboard -> which will redirect back to start_trip/active view
            # (unless marked Delayed, in which case dashboard is accessible)
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
    This function concludes the trip lifecycle.
    """
    trip = get_object_or_404(DailyTrip, trip_id=trip_id)
    
    trip.status = 'Completed'
    trip.save()
    
    Booking.objects.filter(trip=trip, status='Checked-In').update(status='Completed')
    
    Booking.objects.filter(trip=trip, status='Confirmed').update(status='Cancelled')

    messages.success(request, "Trip ended. Passenger lists have been updated.")
    return redirect('driver_dashboard')