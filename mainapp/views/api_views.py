from django.http import JsonResponse
from mainapp.models import CurrentLocation

def get_shuttle_locations(request):
    # Used by Leaflet to plot buses on the map
    active_buses = CurrentLocation.objects.filter(trip__status='In-Progress')

    data = []
    for loc in active_buses:
        data.append({
            'trip_id': loc.trip.trip_id,
            'lat': float(loc.latitude),
            'lng': float(loc.longitude),
            'route_name': loc.trip.schedule.route.name,
            'plate_no': loc.trip.driverassignment_set.first().vehicle.plate_no
        })

    return JsonResponse({'shuttles': data})
