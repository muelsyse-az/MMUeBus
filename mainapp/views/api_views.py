from django.http import JsonResponse
from mainapp.models import DailyTrip, CurrentLocation, Stop, Route, RouteStop, DriverAssignment
from django.utils import timezone
import json, random
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required

# 1. READ: Used by the Map Page (Student/Coord/Admin)
def get_shuttle_locations(request):
    # Only get trips that are actively "In-Progress"
    active_trips = DailyTrip.objects.filter(status='In-Progress')
    
    shuttles = []
    for trip in active_trips:
        # Check if we have location data for this trip
        if hasattr(trip, 'location'):
            loc = trip.location
            # Get Vehicle Info safely
            vehicle_plate = "Unknown"
            assignment = trip.driverassignment_set.first()
            if assignment:
                vehicle_plate = assignment.vehicle.plate_no

            shuttles.append({
                'id': trip.trip_id,
                'lat': float(loc.latitude),
                'lng': float(loc.longitude),
                'route': trip.schedule.route.name,
                'plate': vehicle_plate,
                'status': trip.status
            })
    
    return JsonResponse({'shuttles': shuttles})

# 2. WRITE: Used by the Driver (The "Transmitter")
@login_required # 1. Require Login
def update_location(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            trip_id = data.get('trip_id')
            lat = data.get('lat')
            lng = data.get('lng')

            if not trip_id:
                return JsonResponse({'status': 'error', 'message': 'Missing trip_id'}, status=400)

            trip = DailyTrip.objects.get(trip_id=trip_id)

            # 2. SECURITY CHECK: Is this user the assigned driver?
            # (Admins/Coords can bypass, but regular users/students cannot)
            if request.user.role == 'driver':
                is_assigned = DriverAssignment.objects.filter(
                    trip=trip, 
                    driver__user=request.user
                ).exists()
                
                if not is_assigned:
                    return JsonResponse({'status': 'error', 'message': 'Not authorized for this trip'}, status=403)
            
            # ... Proceed to update ...
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

def get_stops_data(request):
    """Returns all stops to be plotted as static markers."""
    stops = Stop.objects.all()
    data = []
    for s in stops:
        data.append({
            'name': s.name,
            'lat': float(s.latitude),
            'lng': float(s.longitude)
        })
    return JsonResponse({'stops': data})

def get_route_paths(request):
    """
    Returns the path for each route by connecting its stops in order.
    """
    routes = Route.objects.all()
    data = []
    
    # Predefined colors to cycle through
    colors = ['#FF5733', '#33FF57', '#3357FF', '#FF33A1', '#FFD700', '#00CED1']
    
    for i, route in enumerate(routes):
        # Get stops for this route in correct sequence
        route_stops = RouteStop.objects.filter(route=route).order_by('sequence_no')
        
        # Extract coordinates
        path_coords = []
        for rs in route_stops:
            path_coords.append([float(rs.stop.latitude), float(rs.stop.longitude)])
            
        if path_coords:
            data.append({
                'name': route.name,
                'color': colors[i % len(colors)], # Cycle colors
                'coords': path_coords
            })
            
    return JsonResponse({'routes': data})