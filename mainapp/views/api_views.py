from django.http import JsonResponse
from mainapp.models import DailyTrip, CurrentLocation, Stop, Route, RouteStop, DriverAssignment
from django.utils import timezone
import json
from django.contrib.auth.decorators import login_required

def get_stops_data(request):
    """
    This function retrieves all registered bus stops from the database to allow the frontend map to plot static markers for pickup and drop-off points.
    
    It iterates through all Stop objects, extracts their names and geographic coordinates, and returns them as a JSON list.
    """
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
    This function constructs the visual paths for every available route by linking their respective stops in the correct sequence, allowing the map to draw colored poly lines representing the bus routes.
    
    It queries the RouteStop model to find stops associated with each route ordered by their sequence number, builds a list of coordinate pairs, and assigns a distinct color from a predefined list before returning the data in JSON format.
    """
    routes = Route.objects.all()
    data = []
    colors = ['#FF5733', '#33FF57', '#3357FF', '#FF33A1', '#FFD700', '#00CED1']
    
    for i, route in enumerate(routes):
        route_stops = RouteStop.objects.filter(route=route).order_by('sequence_no')
        path_coords = []
        for rs in route_stops:
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
    This function provides the real-time location data for all active shuttles to the frontend map, enabling users to track buses that are currently in progress.
    
    It filters DailyTrip objects for those with an 'In-Progress' status, accesses their associated CurrentLocation and DriverAssignment models to gather coordinates and vehicle plate numbers, and serializes this information into a JSON response.
    """
    active_trips = DailyTrip.objects.filter(status='In-Progress')
    
    shuttles = []
    for trip in active_trips:
        if hasattr(trip, 'location'):
            loc = trip.location
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

@login_required
def update_location(request):
    """
    This view processes GPS updates sent from a driver's device, verifying the driver's authorization before updating the real-time position of their assigned trip.
    
    It parses the JSON body for coordinates and trip ID, verifies that the requesting user is the assigned driver for that specific trip, and then uses update_or_create to save the new latitude and longitude into the CurrentLocation model.
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            trip_id = data.get('trip_id')
            lat = data.get('lat')
            lng = data.get('lng')

            if not trip_id:
                return JsonResponse({'status': 'error', 'message': 'Missing trip_id'}, status=400)

            trip = DailyTrip.objects.get(trip_id=trip_id)

            if request.user.role == 'driver':
                is_assigned = DriverAssignment.objects.filter(
                    trip=trip, 
                    driver__user=request.user
                ).exists()
                
                if not is_assigned:
                    return JsonResponse({'status': 'error', 'message': 'Not authorized for this trip'}, status=403)
            
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