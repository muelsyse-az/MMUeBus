from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from mainapp.decorators import student_required
from mainapp.models import Schedule, DailyTrip, Booking, Route, Incident
from mainapp.services import get_available_seats
from mainapp.forms import StudentIncidentForm

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
    # SDS 2.1.3.3: Reserve Seat
    trip = get_object_or_404(DailyTrip, trip_id=trip_id)

    if request.method == 'POST':
        if get_available_seats(trip) > 0:
            Booking.objects.create(
                student=request.user.student_profile,
                trip=trip,
                status='Confirmed'
            )
            messages.success(request, "Seat reserved successfully!")
            return redirect('student_dashboard')
        else:
            messages.error(request, "Bus is full.")

    return render(request, 'mainapp/student/reserve_seat.html', {'trip': trip})

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
