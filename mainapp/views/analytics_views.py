from django.shortcuts import render
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Count
from mainapp.decorators import staff_required
from mainapp.models import Route, DailyTrip, Booking, Incident

@login_required
@user_passes_test(staff_required)
def performance_dashboard(request):
    # 1. Route Analytics
    route_stats = Route.objects.annotate(
        total_bookings=Count('schedule__dailytrip__booking')
    ).order_by('-total_bookings')[:5]

    route_labels = [r.name for r in route_stats]
    route_data = [r.total_bookings for r in route_stats]

    # 2. Trip Status Analytics
    trip_stats = DailyTrip.objects.values('status').annotate(count=Count('status'))
    status_counts = {'Completed': 0, 'Delayed': 0, 'Cancelled': 0, 'In-Progress': 0}
    
    for item in trip_stats:
        if item['status'] in status_counts:
            status_counts[item['status']] = item['count']

    status_labels = list(status_counts.keys())
    status_data = list(status_counts.values())

    # 3. Key Metrics
    total_incidents = Incident.objects.count()
    
    # --- CHANGED: Calculate Load Factor instead of just Total Passengers ---
    # We only care about trips that actually happened (excluding 'Scheduled')
    active_trips = DailyTrip.objects.exclude(status='Scheduled').prefetch_related(
        'booking_set', 
        'driverassignment_set__vehicle', 
        'schedule__default_vehicle'
    )

    total_seats_available = 0
    total_seats_occupied = 0

    for trip in active_trips:
        # Determine Capacity (Logic mirrors services.py)
        capacity = 40 # Default fallback
        assignment = trip.driverassignment_set.first()
        
        if assignment:
            capacity = assignment.vehicle.capacity
        elif trip.schedule.default_vehicle:
            capacity = trip.schedule.default_vehicle.capacity
        
        total_seats_available += capacity
        
        # Count only valid passengers (Confirmed or Checked-In)
        # Note: We filter in Python to avoid complex DB grouping, efficient enough for dashboard
        passengers = trip.booking_set.filter(status__in=['Confirmed', 'Checked-In']).count()
        total_seats_occupied += passengers

    if total_seats_available > 0:
        load_factor = round((total_seats_occupied / total_seats_available) * 100, 1)
    else:
        load_factor = 0
    # ---------------------------------------------------------------------

    # Calculate Reliability
    total_trips_run = active_trips.count()
    if total_trips_run > 0:
        delayed_trips = status_counts['Delayed']
        reliability_rate = round(((total_trips_run - delayed_trips) / total_trips_run) * 100, 1)
    else:
        reliability_rate = 100

    context = {
        'route_labels': route_labels,
        'route_data': route_data,
        'status_labels': status_labels,
        'status_data': status_data,
        'route_stats': route_stats, 
        
        # Updated Metric
        'load_factor': load_factor, 
        
        'total_incidents': total_incidents,
        'reliability_rate': reliability_rate,
        'completed_trips': status_counts['Completed'],
    }

    return render(request, 'mainapp/coordinator/performance_dashboard.html', context)