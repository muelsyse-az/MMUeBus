from django.db.models import Sum
from .models import Booking, Vehicle

def get_available_seats(trip):
    """
    Calculates available seats for a specific trip.
    Formula: Vehicle Capacity - Confirmed Bookings
    """
    # 1. Determine Capacity (FIXED)
    capacity = 0
    
    # A. Check if a specific vehicle is assigned to this trip
    assignment = trip.driverassignment_set.first()
    if assignment:
        capacity = assignment.vehicle.capacity
    else:
        # B. Fallback: Check if the Schedule has a default vehicle
        if trip.schedule.default_vehicle:
            capacity = trip.schedule.default_vehicle.capacity
        else:
            # C. Fallback: Default to standard bus capacity (e.g. 40) 
            # so bookings remain open even if unassigned.
            capacity = 40 

    # 2. Count active bookings (Confirmed or Checked-In)
    booked_count = Booking.objects.filter(
        trip=trip,
        status__in=['Confirmed', 'Checked-In']
    ).count()

    return max(0, capacity - booked_count)
