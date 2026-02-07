from django.db.models import Sum, Max
from datetime import timedelta
from .models import Booking, Vehicle, DriverAssignment

def get_trip_capacity(trip):
    """
    Determines the total capacity for a trip based on assigned vehicle,
    default schedule vehicle, or a system default.
    """
    # 1. Check specific assignment
    assignment = trip.driverassignment_set.first()
    if assignment:
        return assignment.vehicle.capacity
    
    # 2. Check schedule default
    if trip.schedule.default_vehicle:
        return trip.schedule.default_vehicle.capacity
        
    # 3. Fallback
    return 40

def get_available_seats(trip):
    """
    Calculates available seats for a specific trip.
    Formula: Vehicle Capacity - Confirmed Bookings
    """
    # Use centralized logic instead of hardcoding here
    capacity = get_trip_capacity(trip)

    # 2. Count active bookings (Confirmed or Checked-In)
    booked_count = Booking.objects.filter(
        trip=trip,
        status__in=['Confirmed', 'Checked-In']
    ).count()

    return max(0, capacity - booked_count)

def get_trip_duration(route):
    """
    Calculates the trip duration based on the estimated time of the last stop.
    Defaults to 60 minutes if no stops are configured.
    """
    duration_mins = route.routestop_set.aggregate(Max('est_minutes'))['est_minutes__max']
    return duration_mins if duration_mins else 60

def check_resource_availability(driver, vehicle, trip_date, start_time, duration_minutes, current_assignment_id=None, exclude_schedule_id=None):
    """
    Checks if resources are busy.
    Added 'exclude_schedule_id' to prevent self-conflicts during schedule edits.
    """
    start_dt = start_time
    end_dt = start_dt + timedelta(minutes=duration_minutes)
    
    # 1. Check Driver Availability
    if driver:
        qs = DriverAssignment.objects.filter(
            driver=driver,
            trip__trip_date=trip_date
        ).exclude(assignment_id=current_assignment_id)
        
        if exclude_schedule_id:
            qs = qs.exclude(trip__schedule_id=exclude_schedule_id)
            
        driver_conflicts = qs.select_related('trip', 'trip__schedule__route')

        for assignment in driver_conflicts:
            other_trip = assignment.trip
            other_duration = get_trip_duration(other_trip.schedule.route)
            other_start = other_trip.planned_departure
            other_end = other_start + timedelta(minutes=other_duration)
            
            if start_dt < other_end and end_dt > other_start:
                return False, f"Driver {driver.user.username} is busy with Trip #{other_trip.trip_id} ({other_start.strftime('%H:%M')} - {other_end.strftime('%H:%M')})."

    # 2. Check Vehicle Availability
    if vehicle:
        qs = DriverAssignment.objects.filter(
            vehicle=vehicle,
            trip__trip_date=trip_date
        ).exclude(assignment_id=current_assignment_id)
        
        if exclude_schedule_id:
            qs = qs.exclude(trip__schedule_id=exclude_schedule_id)
            
        vehicle_conflicts = qs.select_related('trip', 'trip__schedule__route')

        for assignment in vehicle_conflicts:
            other_trip = assignment.trip
            other_duration = get_trip_duration(other_trip.schedule.route)
            other_start = other_trip.planned_departure
            other_end = other_start + timedelta(minutes=other_duration)

            if start_dt < other_end and end_dt > other_start:
                return False, f"Vehicle {vehicle.plate_no} is in use for Trip #{other_trip.trip_id}."

    return True, None