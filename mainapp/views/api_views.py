from django.http import JsonResponse
from mainapp.models import DailyTrip, CurrentLocation
from django.utils import timezone
import json
from django.views.decorators.csrf import csrf_exempt

# 1. READ: Used by the Map Page (Student/Coord/Admin)
def get_shuttle_locations(request):
    # Only get trips that are actively "In-Progress"
    active_trips = DailyTrip.objects.filter(status='In-Progress')
    
    shuttles = []
    for trip in active_trips:
        # Check if we have location data for this trip
        if hasattr(trip, 'currentlocation'):
            loc = trip.currentlocation
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
            
            # Update or Create the location record
            CurrentLocation.objects.update_or_create(
                trip=trip,
                defaults={
                    'latitude': lat,
                    'longitude': lng,
                    'last_update': timezone.now()
                }
            )
            return JsonResponse({'status': 'success'})
        except Exception as e:
            print(f"Error updating location: {e}")
            return JsonResponse({'status': 'error'}, status=500)
            
    return JsonResponse({'status': 'invalid method'}, status=405)
