from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from mainapp.decorators import student_required
from mainapp.models import Schedule, DailyTrip, Booking
from mainapp.services import get_available_seats

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
