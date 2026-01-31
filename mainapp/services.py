from django.db.models import Sum
from .models import Booking, Vehicle

def get_available_seats(trip):
    """
    Calculates available seats for a specific trip.
    Formula: Vehicle Capacity - Confirmed Bookings
    """
    # 1. Get the capacity of the vehicle assigned to this trip
    # Note: We need to check if a driver/vehicle is actually assigned
    try:
        assignment = trip.driverassignment_set.first()
        capacity = assignment.vehicle.capacity
    except AttributeError:
        return 0 # No vehicle assigned yet

    # 2. Count active bookings (Confirmed or Checked-In)
    booked_count = Booking.objects.filter(
        trip=trip,
        status__in=['Confirmed', 'Checked-In']
    ).count()

    return max(0, capacity - booked_count)
