from django.http import JsonResponse
from mainapp.models import DailyTrip, CurrentLocation, Stop, Route, RouteStop, DriverAssignment
from django.utils import timezone
import json
from django.contrib.auth.decorators import login_required

def get_stops_data(request):
    stops = Stop.objects.all()
    data = []
    for s in stops:
        if s.latitude and s.longitude:
            data.append({
                'name': s.name,
                'lat': float(s.latitude),
                'lng': float(s.longitude)
            })
    return JsonResponse({'stops': data})

def get_route_paths(request):
    routes = Route.objects.all()
    data = []
    colors = ['#FF5733', '#33FF57', '#3357FF', '#FF33A1', '#FFD700', '#00CED1']
    
    for i, route in enumerate(routes):
        route_stops = RouteStop.objects.filter(route=route).order_by('sequence_no')
        path_coords = []
        for rs in route_stops:
            if rs.stop.latitude and rs.stop.longitude:
                path_coords.append([float(rs.stop.latitude), float(rs.stop.longitude)])
            
        if path_coords:
            data.append({
                'name': route.name,
                'color': colors[i % len(colors)],
                'coords': path_coords
            })
            
    return JsonResponse({'routes': data})

def get_shuttle_locations(request):
    """
    Returns real-time locations.
    FIX: Added safe float conversion to prevent Server 500 errors or NaNs.
    """
    active_trips = DailyTrip.objects.filter(status='In-Progress')
    
    shuttles = []
    for trip in active_trips:
        if hasattr(trip, 'location') and trip.location:
            loc = trip.location
            
            # Skip if coordinates are missing
            if loc.latitude is None or loc.longitude is None:
                continue

            try:
                lat = float(loc.latitude)
                lng = float(loc.longitude)
            except (ValueError, TypeError):
                continue # Skip bad data

            vehicle_plate = "Unknown"
            assignment = trip.driverassignment_set.first()
            if assignment:
                vehicle_plate = assignment.vehicle.plate_no
            elif trip.schedule.default_vehicle:
                vehicle_plate = trip.schedule.default_vehicle.plate_no

            shuttles.append({
                'id': trip.trip_id,
                'lat': lat,
                'lng': lng,
                'route': trip.schedule.route.name,
                'plate': vehicle_plate,
                'status': trip.status
            })
    
    return JsonResponse({'shuttles': shuttles})

@login_required
def update_location(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            trip_id = data.get('trip_id')
            lat = data.get('lat')
            lng = data.get('lng')

            if not trip_id or lat is None or lng is None:
                return JsonResponse({'status': 'error', 'message': 'Invalid data'}, status=400)

            trip = DailyTrip.objects.get(trip_id=trip_id)

            if request.user.role == 'driver':
                is_assigned = DriverAssignment.objects.filter(
                    trip=trip, 
                    driver__user=request.user
                ).exists()
                
                if not is_assigned:
                    return JsonResponse({'status': 'error', 'message': 'Not authorized'}, status=403)
            
            CurrentLocation.objects.update_or_create(
                trip=trip,
                defaults={
                    'latitude': lat,
                    'longitude': lng,
                    'last_update': timezone.now()
                }
            )
            return JsonResponse({'status': 'success'})
        except DailyTrip.DoesNotExist:
             return JsonResponse({'status': 'error', 'message': 'Trip not found'}, status=404)
        except Exception as e:
            print(f"Error updating location: {e}")
            return JsonResponse({'status': 'error'}, status=500)
            
    return JsonResponse({'status': 'invalid method'}, status=405)