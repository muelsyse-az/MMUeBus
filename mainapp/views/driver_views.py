from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from mainapp.decorators import driver_required
from mainapp.models import DriverAssignment, DailyTrip, CurrentLocation
from django.utils import timezone

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
        defaults={'latitude': 0.0, 'longitude': 0.0}
    )
    return render(request, 'mainapp/driver/active_trip.html', {'trip': trip})