from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from mainapp.decorators import driver_required
from mainapp.models import DriverAssignment, DailyTrip, CurrentLocation, Incident
from django.utils import timezone
from mainapp.forms import DriverIncidentForm

@login_required
@user_passes_test(driver_required)
def driver_dashboard(request):
    # Get today's assignments
    driver_profile = request.user.driver_profile
    today = timezone.now().date()
    assignments = DriverAssignment.objects.filter(driver=driver_profile, trip__trip_date=today)
    return render(request, 'mainapp/driver/dashboard.html', {'assignments': assignments})

@login_required
@user_passes_test(driver_required)
def start_trip(request, trip_id):
    # SDS 2.1.4.1 Capture Vehicle Location (Start)
    trip = get_object_or_404(DailyTrip, trip_id=trip_id)
    trip.status = 'In-Progress'
    trip.save()

    # Initialize location (0,0) - real updates come via API later
    CurrentLocation.objects.update_or_create(
        trip=trip,
        defaults={'latitude': 2.9289, 'longitude': 101.6417}
    )
    return render(request, 'mainapp/driver/active_trip.html', {'trip': trip})

@login_required
@user_passes_test(driver_required)
def driver_report_incident(request):
    # 1. Find if Driver has an active trip (Status = In-Progress)
    # We look for a trip assigned to this driver that is currently running
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
            
            # Auto-link the active trip if it exists
            if active_trip:
                incident.trip = active_trip
                
                # Handle "Mark Delayed" Checkbox
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