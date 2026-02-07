from django.shortcuts import render
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Count, Sum
from mainapp.decorators import staff_required
from mainapp.models import Route, DailyTrip, Booking, Incident

@login_required
@user_passes_test(staff_required)
def performance_dashboard(request):
    # 1. Route Analytics (Top 5 by Popularity)
    route_stats = Route.objects.annotate(
        total_bookings=Count('schedule__dailytrip__booking')
    ).order_by('-total_bookings')[:5]

    # Calculate Total Bookings across these top routes for percentage calc
    total_top_bookings = sum(r.total_bookings for r in route_stats)
    if total_top_bookings == 0: total_top_bookings = 1 # Avoid division by zero

    # --- NEW: Calculate Per-Route Efficiency (Load Factor) ---
    for route in route_stats:
        # A. Calculate Percentage Share (Fixes the visual bug)
        route.share_percentage = (route.total_bookings / total_top_bookings) * 100

        # B. Calculate Load Factor for THIS specific route
        route_trips = DailyTrip.objects.filter(
            schedule__route=route
        ).exclude(status='Scheduled').prefetch_related('driverassignment_set__vehicle')
        
        r_seats = 0
        r_occupied = 0
        
        for trip in route_trips:
            # Capacity Logic
            cap = 40
            assignment = trip.driverassignment_set.first()
            if assignment: cap = assignment.vehicle.capacity
            elif trip.schedule.default_vehicle: cap = trip.schedule.default_vehicle.capacity
            
            r_seats += cap
            r_occupied += trip.booking_set.filter(status__in=['Confirmed', 'Checked-In']).count()
        
        if r_seats > 0:
            route.avg_load_factor = round((r_occupied / r_seats) * 100, 1)
        else:
            route.avg_load_factor = 0
    # ---------------------------------------------------------

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

    # 3. Global Key Metrics
    total_incidents = Incident.objects.count()
    
    # Global Load Factor Calculation
    active_trips = DailyTrip.objects.exclude(status='Scheduled').prefetch_related(
        'booking_set', 'driverassignment_set__vehicle'
    )

    total_seats_available = 0
    total_seats_occupied = 0

    for trip in active_trips:
        capacity = 40
        assignment = trip.driverassignment_set.first()
        if assignment:
            capacity = assignment.vehicle.capacity
        elif trip.schedule.default_vehicle:
            capacity = trip.schedule.default_vehicle.capacity
        
        total_seats_available += capacity
        passengers = trip.booking_set.filter(status__in=['Confirmed', 'Checked-In']).count()
        total_seats_occupied += passengers

    if total_seats_available > 0:
        load_factor = round((total_seats_occupied / total_seats_available) * 100, 1)
    else:
        load_factor = 0

    # Reliability Calculation
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
        'load_factor': load_factor, 
        'total_incidents': total_incidents,
        'reliability_rate': reliability_rate,
        'completed_trips': status_counts['Completed'],
    }

    return render(request, 'mainapp/coordinator/performance_dashboard.html', context)