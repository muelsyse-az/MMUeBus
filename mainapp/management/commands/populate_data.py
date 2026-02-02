from django.core.management.base import BaseCommand
from django.utils import timezone
from mainapp.models import User, Student, Driver, TransportCoordinator, Admin, Vehicle, Stop, Route, RouteStop, Schedule, DailyTrip, DriverAssignment, Booking, Incident, Notification
import datetime
import random

class Command(BaseCommand):
    help = 'Populates the database with dummy data. Wipes old data first.'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.WARNING("⚠ Wiping old data to prevent conflicts..."))
        
        # 1. CLEAN SLATE (Delete in order to respect Foreign Keys)
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
        
        # Delete Profiles first
        Student.objects.all().delete()
        Driver.objects.all().delete()
        TransportCoordinator.objects.all().delete()
        Admin.objects.all().delete()
        
        # Delete Users (except superusers to keep your login if you have one)
        User.objects.filter(is_superuser=False).delete()
        
        self.stdout.write(self.style.SUCCESS("Old data wiped. Starting population..."))

        # ==========================================
        # 2. CREATE USERS (Robust Method)
        # ==========================================
        def create_user(username, role, password='password123'):
            # Get or Create User
            user, created = User.objects.get_or_create(username=username, defaults={
                'email': f'{username}@example.com',
                'first_name': username.split('_')[0].capitalize(),
                'last_name': 'User',
                'role': role
            })
            
            if created:
                user.set_password(password)
                user.save()

            # Get or Create Profile (Safe for re-runs)
            if role == 'student':
                Student.objects.get_or_create(user=user)
            elif role == 'driver':
                Driver.objects.get_or_create(user=user, defaults={'license_no': f'L-{random.randint(10000,99999)}'})
            elif role == 'coordinator':
                TransportCoordinator.objects.get_or_create(user=user)
            elif role == 'admin':
                Admin.objects.get_or_create(user=user)
                
            return user

        # Staff
        admin = create_user('admin', 'admin')
        coord = create_user('coordinator', 'coordinator')

        # 5 Drivers
        drivers = []
        driver_names = ['ahmad', 'muthu', 'chong', 'sara', 'david']
        for name in driver_names:
            u = create_user(f'{name}_driver', 'driver')
            drivers.append(u.driver_profile)
        self.stdout.write(f"Created {len(drivers)} Drivers")

        # 20 Students
        students = []
        for i in range(1, 21):
            u = create_user(f'student_{i}', 'student')
            students.append(u.student_profile)
        self.stdout.write(f"Created {len(students)} Students")

        # ==========================================
        # 3. CREATE VEHICLES
        # ==========================================
        vehicles_data = [
            ('WTA 1234', 40, 'Bus'), ('BMS 5678', 40, 'Bus'), 
            ('PHP 9090', 40, 'Bus'), ('JVX 3344', 12, 'Van'), ('PYT 1122', 12, 'Van')
        ]
        vehicles = []
        for plate, cap, vtype in vehicles_data:
            v, _ = Vehicle.objects.get_or_create(plate_no=plate, defaults={'capacity': cap, 'type': vtype})
            vehicles.append(v)
        self.stdout.write(f"Created {len(vehicles)} Vehicles")

        # ==========================================
        # 4. CREATE STOPS
        # ==========================================
        stops_config = [
            ('MMU Main Gate', 2.9289, 101.6417), ('Cyberia Smarthomes', 2.9245, 101.6360),
            ('The Arc', 2.9220, 101.6385), ('The Place', 2.9300, 101.6550),
            ('Solstice / Pan\'gaea', 2.9215, 101.6500), ('Verdi Eco-dominiums', 2.9180, 101.6450),
            ('Symphony Hills', 2.9160, 101.6520), ('D-Pulze Mall', 2.9210, 101.6505),
        ]
        stop_objs = {}
        for name, lat, lng in stops_config:
            s, _ = Stop.objects.get_or_create(name=name, defaults={'latitude': lat, 'longitude': lng})
            stop_objs[name] = s
        self.stdout.write("Created Stops")

        # ==========================================
        # 5. CREATE ROUTES
        # ==========================================
        routes_config = [
            {'name': 'Route A: Cyberia Loop', 'stops': ['Cyberia Smarthomes', 'MMU Main Gate']},
            {'name': 'Route B: Arc & Place', 'stops': ['The Arc', 'The Place', 'MMU Main Gate']},
            {'name': 'Route C: Pan\'gaea Shuttle', 'stops': ['Solstice / Pan\'gaea', 'D-Pulze Mall', 'MMU Main Gate']},
            {'name': 'Route D: Luxury Loop', 'stops': ['Verdi Eco-dominiums', 'Symphony Hills', 'MMU Main Gate']}
        ]
        
        created_routes = []
        for r_data in routes_config:
            route, _ = Route.objects.get_or_create(name=r_data['name'])
            created_routes.append(route)
            # Create RouteStops
            for i, stop_name in enumerate(r_data['stops']):
                RouteStop.objects.get_or_create(
                    route=route, stop=stop_objs[stop_name], sequence_no=i+1, defaults={'est_minutes': i*10}
                )

        # ==========================================
        # 6. SCHEDULES & TRIPS
        # ==========================================
        today = datetime.date.today()
        now = timezone.now()

        # Helper to create schedule + trip
        def create_schedule_trip(route_idx, driver_idx, vehicle_idx, start_h, status):
            sched, _ = Schedule.objects.get_or_create(
                route=created_routes[route_idx],
                start_time=datetime.time(start_h, 0),
                defaults={
                    'days_of_week': 'Mon,Tue,Wed,Thu,Fri', 'end_time': datetime.time(start_h+4, 0),
                    'frequency_min': 30, 'valid_from': today, 'valid_to': today + datetime.timedelta(days=365),
                    'default_driver': drivers[driver_idx], 'default_vehicle': vehicles[vehicle_idx]
                }
            )
            
            trip, _ = DailyTrip.objects.get_or_create(
                schedule=sched, trip_date=today, 
                defaults={'planned_departure': now, 'status': status}
            )
            
            DriverAssignment.objects.get_or_create(trip=trip, driver=drivers[driver_idx], vehicle=vehicles[vehicle_idx])
            return trip

        # 1. Active Trip (For Tracking)
        create_schedule_trip(0, 0, 0, 8, 'In-Progress') # Route A, Ahmad
        # 2. Scheduled Trip
        create_schedule_trip(1, 1, 1, 9, 'Scheduled')   # Route B, Muthu
        # 3. Delayed Trip
        create_schedule_trip(2, 2, 2, 8, 'Delayed')     # Route C, Chong

        self.stdout.write(self.style.SUCCESS("Database populated successfully!"))