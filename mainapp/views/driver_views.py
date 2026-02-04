from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from mainapp.decorators import driver_required
from mainapp.models import DriverAssignment, DailyTrip, CurrentLocation, Incident, Booking, Notification
from django.utils import timezone
from mainapp.forms import DriverIncidentForm
from django.contrib import messages
from django.urls import reverse

@login_required
@user_passes_test(driver_required)
def driver_dashboard(request):
    """
    This view renders the main interface for drivers, displaying a list of their assigned trips for the current day while filtering out completed or cancelled work.
    
    It retrieves the driver's profile, filters DriverAssignment objects for the current date excluding inactive statuses, and orders them by departure time before passing the list to the template.
    """
    driver_profile = request.user.driver_profile
    today = timezone.now().date()
    
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
    This function initializes a trip lifecycle, changing its status to active and establishing an initial GPS location to begin tracking.
    
    It fetches the specific DailyTrip object, updates its status to 'In-Progress', and creates a default CurrentLocation entry so the API has a record to update subsequently.
    """
    trip = get_object_or_404(DailyTrip, trip_id=trip_id)
    trip.status = 'In-Progress'
    trip.save()

    CurrentLocation.objects.update_or_create(
        trip=trip,
        defaults={'latitude': 2.9289, 'longitude': 101.6417}
    )
    return render(request, 'mainapp/driver/active_trip.html', {'trip': trip})

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