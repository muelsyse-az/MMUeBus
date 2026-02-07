from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta, datetime, time
import random
import time as python_time
import requests

from mainapp.models import (
    Student, Driver, TransportCoordinator, Admin,
    Vehicle, Stop, Route, RouteStop, Schedule,
    DailyTrip, DriverAssignment, Booking, Incident, Notification, CurrentLocation
)

User = get_user_model()

class Command(BaseCommand):
    help = 'Populates DB with demo data. Use --simulate to start live tracking immediately.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--simulate',
            action='store_true',
            help='After populating data, continuously update bus locations (Infinite Loop)',
        )

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.WARNING('Deleting old data...'))
        self._clear_data()
        
        self.stdout.write(self.style.SUCCESS('Creating Users...'))
        users = self._create_users()
        
        self.stdout.write(self.style.SUCCESS('Creating Infrastructure...'))
        assets = self._create_infrastructure()
        
        self.stdout.write(self.style.SUCCESS('Creating Schedules & Trips...'))
        self._create_operations(users, assets)
        
        self.stdout.write(self.style.SUCCESS('Simulating Usage (Bookings, Incidents)...'))
        self._create_usage(users)
        
        # Initialize locations so map isn't empty even without simulation
        self._initialize_static_locations()

        self.stdout.write(self.style.SUCCESS('--------------------------------------------------'))
        self.stdout.write(self.style.SUCCESS('DATA POPULATION COMPLETE!'))
        self.stdout.write(self.style.SUCCESS('--------------------------------------------------'))
        self.stdout.write(f"  - Admin:       {users['admin'].username} / pass1234")
        self.stdout.write(f"  - Coordinator: {users['coordinator'].username} / pass1234")
        self.stdout.write(f"  - Driver:      {users['drivers'][0].user.username} / pass1234")
        self.stdout.write(f"  - Student:     {users['students'][0].user.username} / pass1234")
        
        if kwargs['simulate']:
            self.stdout.write(self.style.WARNING('\n>>> STARTING LIVE SIMULATION (Ctrl+C to stop) <<<'))
            self._run_simulation()

    def _clear_data(self):
        CurrentLocation.objects.all().delete()
        Notification.objects.all().delete()
        Incident.objects.all().delete()
        Booking.objects.all().delete()
        DriverAssignment.objects.all().delete()
        DailyTrip.objects.all().delete()
        Schedule.objects.all().delete()
        RouteStop.objects.all().delete()
        Route.objects.all().delete()
        Stop.objects.all().delete()
        Vehicle.objects.all().delete()
        User.objects.all().delete()

    def _create_users(self):
        # 1. Admin
        # create_superuser automatically sets role='admin', triggering the signal.
        admin_user = User.objects.create_superuser('admin', 'admin@mmu.edu.my', 'pass1234')
        admin_user.first_name = "Super"
        admin_user.last_name = "Admin"
        admin_user.save()
        # FIX: Do not call Admin.objects.create(), signal already did it.

        # 2. Coordinator
        # We pass role='coordinator' so the signal creates the correct profile immediately.
        coord_user = User.objects.create_user(
            'coordinator', 'coord@mmu.edu.my', 'pass1234', role='coordinator'
        )
        coord_user.first_name = "Operations"
        coord_user.last_name = "Manager"
        coord_user.save()
        # FIX: Do not call TransportCoordinator.objects.create()

        # 3. Drivers (4)
        drivers = []
        for i in range(1, 5):
            u = User.objects.create_user(
                f'driver{i}', f'driver{i}@mmu.edu.my', 'pass1234', role='driver'
            )
            u.first_name = "Ali" if i%2 else "Ah Hock"
            u.last_name = f"Bin Abu {i}"
            u.save()
            
            # FIX: Fetch the auto-created profile and update it
            d = u.driver_profile
            d.license_no = f"L{1000+i}MY"
            d.save()
            drivers.append(d)

        # 4. Students (50)
        students = []
        names = ["Sarah", "Jason", "Mei Ling", "Muthu", "Aishah", "David", "Chong", "Priya"]
        for i in range(1, 51):
            u = User.objects.create_user(
                f'student{i}', f'student{i}@student.mmu.edu.my', 'pass1234', role='student'
            )
            u.first_name = names[i % len(names)]
            u.last_name = f"Student {i}"
            u.save()
            
            # FIX: Fetch auto-created profile
            s = u.student_profile
            students.append(s)

        return {'admin': admin_user, 'coordinator': coord_user, 'drivers': drivers, 'students': students}

    def _create_infrastructure(self):
        # Vehicles
        vehicles = []
        for i in range(1, 5):
            v = Vehicle.objects.create(plate_no=f"W{100+i}X", capacity=40, type='Bus')
            vehicles.append(v)

        # Stops
        stops_data = {
            "MMU Bus Stop": (2.9251, 101.6420),
            "Serin Residency": (2.9168, 101.6455),
            "Crystal Serin": (2.9194, 101.6458),
            "Cyberia Crescent 1": (2.9211, 101.6416),
            "Third Avenue": (2.9292, 101.6554),
            "Cybersquare SOHO": (2.9192, 101.6582),
            "Kanvas SOHO": (2.9136, 101.6552),
            "Lakefront Villa Stop": (2.9321, 101.6336),
            "Mutiara Ville": (2.9230, 101.6325),
            "The Arc": (2.9251, 101.6375)
        }
        
        created_stops = {}
        for name, (lat, lon) in stops_data.items():
            s = Stop.objects.create(name=name, latitude=lat, longitude=lon)
            created_stops[name] = s

        # Routes
        r1 = Route.objects.create(name="Serin Route", description="Campus -> Serin/Cyberia Loop")
        r1_stops = ["MMU Bus Stop", "Serin Residency", "Crystal Serin", "Cyberia Crescent 1", "MMU Bus Stop"]
        for idx, stop_name in enumerate(r1_stops):
            RouteStop.objects.create(route=r1, stop=created_stops[stop_name], sequence_no=idx+1, est_minutes=idx*5)

        r2 = Route.objects.create(name="SOHO Route", description="Campus -> Cybersquare/Kanvas")
        r2_stops = ["MMU Bus Stop", "Third Avenue", "Cybersquare SOHO", "Kanvas SOHO", "MMU Bus Stop"]
        for idx, stop_name in enumerate(r2_stops):
            RouteStop.objects.create(route=r2, stop=created_stops[stop_name], sequence_no=idx+1, est_minutes=idx*7)

        r3 = Route.objects.create(name="Mutiara Route", description="Campus -> Lakefront/Arc")
        r3_stops = ["MMU Bus Stop", "Lakefront Villa Stop", "Mutiara Ville", "The Arc", "MMU Bus Stop"]
        for idx, stop_name in enumerate(r3_stops):
            RouteStop.objects.create(route=r3, stop=created_stops[stop_name], sequence_no=idx+1, est_minutes=idx*6)

        return {'vehicles': vehicles, 'routes': [r1, r2, r3]}

    def _create_operations(self, users, assets):
        drivers = users['drivers']
        vehicles = assets['vehicles']
        routes = assets['routes']
        
        today = timezone.now().date()
        valid_from = today - timedelta(days=7)
        valid_to = today + timedelta(days=90)
        days_str = "Mon,Tue,Wed,Thu,Fri,Sat,Sun"

        schedules = [
            Schedule.objects.create(route=routes[0], days_of_week=days_str, start_time=time(7, 30), end_time=time(10, 30), frequency_min=30, valid_from=valid_from, valid_to=valid_to, default_driver=drivers[0], default_vehicle=vehicles[0]),
            Schedule.objects.create(route=routes[1], days_of_week=days_str, start_time=time(11, 00), end_time=time(14, 00), frequency_min=60, valid_from=valid_from, valid_to=valid_to, default_driver=drivers[1], default_vehicle=vehicles[1]),
            Schedule.objects.create(route=routes[2], days_of_week=days_str, start_time=time(17, 00), end_time=time(20, 00), frequency_min=45, valid_from=valid_from, valid_to=valid_to, default_driver=drivers[2], default_vehicle=vehicles[2])
        ]

        for day_offset in [-1, 0, 1]:
            target_date = today + timedelta(days=day_offset)
            for sched in schedules:
                current_dt = datetime.combine(target_date, sched.start_time)
                end_dt = datetime.combine(target_date, sched.end_time)
                
                while current_dt < end_dt:
                    now = timezone.now()
                    trip_aware = timezone.make_aware(current_dt)
                    
                    status = 'Scheduled'
                    if trip_aware < now:
                        status = 'Completed'
                    
                    # Force In-Progress trips for Today
                    if day_offset == 0:
                        # Make trip active if it's roughly "now" (or recent past)
                        time_diff = (now - trip_aware).total_seconds()
                        if 0 <= time_diff < 3600: # Active if started in last hour
                            status = 'In-Progress'
                    
                    # Force at least one active trip per route for DEMO purposes
                    if day_offset == 0 and status != 'Completed' and current_dt.time() == sched.start_time:
                         status = 'In-Progress'

                    trip = DailyTrip.objects.create(
                        schedule=sched, trip_date=target_date, planned_departure=trip_aware, status=status
                    )
                    DriverAssignment.objects.create(trip=trip, driver=sched.default_driver, vehicle=sched.default_vehicle)
                    current_dt += timedelta(minutes=sched.frequency_min)

    def _create_usage(self, users):
        students = users['students']
        today = timezone.now().date()
        trips_today = DailyTrip.objects.filter(trip_date=today)
        demo_student = students[0]
        
        active_trip = trips_today.filter(status='In-Progress').first()
        if active_trip:
            Booking.objects.create(student=demo_student, trip=active_trip, status='Checked-In')
            for s in students[1:20]:
                 Booking.objects.create(student=s, trip=active_trip, status='Confirmed')
            
            # Create a New incident
            Incident.objects.create(reported_by=students[2].user, trip=active_trip, description="Bus driving too fast.", status='New')

        future_trip = trips_today.filter(status='Scheduled').last()
        if future_trip:
            Booking.objects.create(student=demo_student, trip=future_trip, status='Confirmed')
            Notification.objects.create(
                recipient=demo_student.user, title="Booking Confirmed",
                message=f"Seat confirmed for {future_trip.schedule.route.name} at {future_trip.planned_departure.strftime('%H:%M')}."
            )

    def _initialize_static_locations(self):
        """Sets initial GPS coordinates for all active trips so they appear on map immediately."""
        active_trips = DailyTrip.objects.filter(status='In-Progress')
        for trip in active_trips:
            first_stop = trip.schedule.route.routestop_set.order_by('sequence_no').first()
            if first_stop:
                CurrentLocation.objects.update_or_create(
                    trip=trip,
                    defaults={'latitude': first_stop.stop.latitude, 'longitude': first_stop.stop.longitude}
                )

    # --- SIMULATION LOGIC ---
    route_cache = {}
    trip_progress = {}

    def get_osrm_path(self, stops):
        coordinates = ";".join([f"{s.stop.longitude},{s.stop.latitude}" for s in stops])
        url = f"http://router.project-osrm.org/route/v1/driving/{coordinates}?overview=full&geometries=geojson"
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                path = data['routes'][0]['geometry']['coordinates']
                return [[coord[1], coord[0]] for coord in path]
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"OSRM Error: {e}"))
        return [[float(s.stop.latitude), float(s.stop.longitude)] for s in stops]

    def _run_simulation(self):
        while True:
            active_trips = DailyTrip.objects.filter(status='In-Progress')
            if not active_trips.exists():
                self.stdout.write("No active trips. Waiting...", ending='\r')
                python_time.sleep(5)
                continue

            for trip in active_trips:
                route_id = trip.schedule.route.route_id
                if route_id not in self.route_cache:
                    stops = RouteStop.objects.filter(route=trip.schedule.route).order_by('sequence_no')
                    self.route_cache[route_id] = self.get_osrm_path(stops)

                path_points = self.route_cache[route_id]
                
                if trip.trip_id not in self.trip_progress:
                    self.trip_progress[trip.trip_id] = 0
                
                current_idx = self.trip_progress[trip.trip_id]
                lat, lng = path_points[current_idx]
                
                CurrentLocation.objects.update_or_create(
                    trip=trip, defaults={'latitude': lat, 'longitude': lng, 'last_update': timezone.now()}
                )

                # Move marker (Speed: 3 points per tick)
                next_idx = current_idx + 3
                if next_idx >= len(path_points): next_idx = 0
                self.trip_progress[trip.trip_id] = next_idx

            self.stdout.write(f"Updated {active_trips.count()} shuttles at {timezone.now().time()}", ending='\r')
            python_time.sleep(2)