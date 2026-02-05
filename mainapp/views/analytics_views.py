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
    total_passengers = Booking.objects.count()
    total_incidents = Incident.objects.count()
    total_trips_run = DailyTrip.objects.exclude(status='Scheduled').count()
    
    # Calculate Reliability
    if total_trips_run > 0:
        delayed_trips = status_counts['Delayed']
        reliability_rate = round(((total_trips_run - delayed_trips) / total_trips_run) * 100, 1)
    else:
        reliability_rate = 100

    context = {
        # Charts Data
        'route_labels': route_labels,
        'route_data': route_data,
        'status_labels': status_labels,
        'status_data': status_data,
        
        # Raw Data for Tables
        'route_stats': route_stats, 

        # KPI Metrics
        'total_passengers': total_passengers,
        'total_incidents': total_incidents,
        'reliability_rate': reliability_rate,
        'completed_trips': status_counts['Completed'], # Added this explicitly
    }

    return render(request, 'mainapp/coordinator/performance_dashboard.html', context)