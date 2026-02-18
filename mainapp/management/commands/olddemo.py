from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.utils import timezone
from django.db import transaction
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
    help = 'High-Performance Data Population: High Load Factor, Small Fleet (3 Buses).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--simulate',
            action='store_true',
            help='Continuously simulate bus movement (Real-time)',
        )

    def handle(self, *args, **kwargs):
        start_time = python_time.time()
        
        self.stdout.write(self.style.WARNING('Deleting old data...'))
        self._clear_data()
        
        with transaction.atomic():
            self.stdout.write(self.style.SUCCESS('Creating Users (Bulk Mode)...'))
            users = self._create_users()
            
            self.stdout.write(self.style.SUCCESS('Creating Infrastructure (3 Buses Only)...'))
            assets = self._create_infrastructure()
            
            self.stdout.write(self.style.SUCCESS('Creating Operations (High Frequency)...'))
            self._create_operations(users, assets)
            
            self.stdout.write(self.style.SUCCESS('Simulating Usage (Packed Buses)...'))
            active_driver_info = self._create_usage(users)

        self.stdout.write(self.style.SUCCESS('Initializing Map Locations...'))
        self._initialize_static_locations()

        active_trip_id = active_driver_info['trip_id'] if active_driver_info else None
        active_username = active_driver_info['username'] if active_driver_info else None
        
        duration = python_time.time() - start_time
        
        self.stdout.write(self.style.SUCCESS('--------------------------------------------------'))
        self.stdout.write(self.style.SUCCESS(f'POPULATION COMPLETE IN {duration:.2f} SECONDS'))
        self.stdout.write(self.style.SUCCESS('--------------------------------------------------'))
        
        if active_username:
             self.stdout.write(self.style.SUCCESS(f"👉 REAL TEST DRIVER: {active_username} / pass1234"))
        
        if kwargs['simulate']:
            self.stdout.write(self.style.WARNING('\n>>> STARTING ORGANIC SIMULATION (Ctrl+C to stop) <<<'))
            self.stdout.write(self.style.SUCCESS('    (Simulation running: Trips take ~20 mins. Ctrl+C to stop)'))
            self._run_simulation(excluded_trip_id=active_trip_id)

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
        password_hash = make_password('pass1234')
        
        admin_user = User.objects.create(
            username='admin', email='admin@goku.com', password=password_hash,
            first_name="System", last_name="Administrator", 
            role='admin', is_staff=True, is_superuser=True
        )

        coord_user = User.objects.create(
            username='coordinator', email='coord@goku.com', password=password_hash,
            first_name="Azman", last_name="Hashim", role='coordinator'
        )

        driver_identities = [
            ("Ahmad", "bin Abdullah"), ("Tan", "Wei Ming"), ("Muthu", "a/l Ramasamy"),
            ("Mohd", "Rizal bin Zakaria"), ("Lee", "Siew Ling"), ("Ravi", "a/l Chandran"),
            ("Wan", "Azman bin Wan Hassan"), ("Wong", "Ah Hock"), ("Suresh", "a/l Krishnan"),
            ("Nurul", "Huda binti Osman")
        ]
        
        driver_users = []
        for i, (first, last) in enumerate(driver_identities, 1):
            u = User(
                username=f'driver{i}', email=f'driver{i}@goku.com', password=password_hash,
                first_name=first, last_name=last, role='driver'
            )
            driver_users.append(u)
        User.objects.bulk_create(driver_users)
        
        saved_drivers = list(User.objects.filter(role='driver').order_by('id'))
        driver_profiles = []
        for u in saved_drivers:
            lic_no = f"{random.choice(['L', 'B'])} {random.randint(100000, 999999)}"
            driver_profiles.append(Driver(user=u, license_no=lic_no))
        Driver.objects.bulk_create(driver_profiles)

        student_users = []
        
        # Extensive list of First Names (Malaysian, Western, International)
        first_names = [
            "Sarah", "Jason", "Divya", "Muhammad", "Chong", "Thara", "Farah", "Vincent", 
            "Siti", "Raj", "Kevin", "Aishah", "Daniel", "Preetha", "Zainal", "Adam", 
            "Mei Ling", "Yusof", "Grace", "Haziq", "Wei Hong", "Kavita", "Nor", "Ryan", 
            "Amir", "Jessica", "Li Wei", "Suresh", "Nadia", "Brandon", "Fatimah", "Kumar", 
            "Alice", "Hakim", "Xin Yi", "Anand", "Huda", "David", "Jia Hao", "Priya", 
            "Omar", "Stephanie", "Ming", "Deepak", "Alya", "Christopher", "Yi Ling", 
            "Arif", "Melissa", "Jun Hao", "Rina", "Alexander", "Pei Shan", "Ganesh", 
            "Nurul", "Jonathan", "Hui Min", "Vikram", "Izzah", "Nicholas", "Siew Lan", 
            "Syed", "Rachel", "Boon", "Lakshmi", "Khairul", "Michelle", "Zhi Xian", 
            "Mahesh", "Miera", "Justin", "Wan", "Shanti", "Taufiq", "Elizabeth"
        ]

        # Extensive list of Last Names (Surnames/Patronyms)
        last_names = [
            "Liyana", "Lim", "Nair", "Haziq", "Pillay", "Tan", "Nurhaliza", "Kumar", 
            "Wong", "Aziz", "Lee", "Menon", "Abidin", "Smith", "Abdullah", "Chen", 
            "Ramasamy", "Ibrahim", "Ng", "Krishnan", "Hashim", "Teoh", "Subramaniam", 
            "Othman", "Chua", "Govindasamy", "Ismail", "Yap", "Chandran", "Rahman", 
            "Koh", "Singh", "Yusoff", "Lau", "Devi", "Zakaria", "Tay", "Fernandes", 
            "Hassan", "Khoo", "Pereira", "Mohamad", "Sim", "Gomez", "Ali", "Low", 
            "D'Cruz", "Mustafa", "Goh", "Alvarez", "Razak", "Soh", "Rodrigues", 
            "Bakar", "Fong", "Da Silva", "Mahmood", "Chan", "Lopez", "Jamil", 
            "Heng", "Martinez", "Salleh", "Ong", "Schmidt", "Kamal", "Yeoh"
        ]
        
        for i in range(1, 501):
            fname = random.choice(first_names)
            lname = random.choice(last_names)
            
            u = User(
                username=f'student{i}', email=f'student{i}@goku.com', password=password_hash,
                # FIX: Removed the {i} suffix from last_name
                first_name=fname, last_name=lname, role='student'
            )
            student_users.append(u)
        
        User.objects.bulk_create(student_users)
        
        saved_students = list(User.objects.filter(role='student'))
        student_profiles = [Student(user=u) for u in saved_students]
        Student.objects.bulk_create(student_profiles)

        final_drivers = list(Driver.objects.select_related('user').all())
        final_students = list(Student.objects.select_related('user').all())

        return {
            'admin': admin_user, 
            'coordinator': coord_user, 
            'drivers': final_drivers, 
            'students': final_students
        }

    def _create_infrastructure(self):
        vehicles = []
        prefixes = ["MMU", "PADU"]
        for i in range(1, 4):
            plate = f"{random.choice(prefixes)} {random.randint(1000, 9999)}"
            v = Vehicle(plate_no=plate, capacity=30, type='Bus')
            vehicles.append(v)
        Vehicle.objects.bulk_create(vehicles)
        saved_vehicles = list(Vehicle.objects.all())
        
        stops_data = {
            "MMU Bus Stop": (2.9251, 101.6420), "Serin Residency": (2.9168, 101.6455),
            "Crystal Serin": (2.9194, 101.6458), "Cyberia Crescent 1": (2.9211, 101.6416),
            "Lakefront Villa Stop": (2.9321, 101.6336), "Mutiara Ville": (2.9230, 101.6325),
            "The Arc": (2.9251, 101.6375), "Cyberjaya Utara Station": (2.9507, 101.6567)
        }
        created_stops = {}
        for name, (lat, lon) in stops_data.items():
            created_stops[name] = Stop.objects.create(name=name, latitude=lat, longitude=lon)

        r1 = Route.objects.create(name="Serin Route", description="Campus -> Serin/Cyberia Loop")
        RouteStop.objects.create(route=r1, stop=created_stops["MMU Bus Stop"], sequence_no=1, est_minutes=0)
        RouteStop.objects.create(route=r1, stop=created_stops["Serin Residency"], sequence_no=2, est_minutes=5)
        RouteStop.objects.create(route=r1, stop=created_stops["Crystal Serin"], sequence_no=3, est_minutes=10)
        RouteStop.objects.create(route=r1, stop=created_stops["Cyberia Crescent 1"], sequence_no=4, est_minutes=15)
        RouteStop.objects.create(route=r1, stop=created_stops["MMU Bus Stop"], sequence_no=5, est_minutes=20)

        r2 = Route.objects.create(name="Mutiara Route", description="Campus -> Lakefront/Arc Loop")
        RouteStop.objects.create(route=r2, stop=created_stops["MMU Bus Stop"], sequence_no=1, est_minutes=0)
        RouteStop.objects.create(route=r2, stop=created_stops["Lakefront Villa Stop"], sequence_no=2, est_minutes=6)
        RouteStop.objects.create(route=r2, stop=created_stops["Mutiara Ville"], sequence_no=3, est_minutes=12)
        RouteStop.objects.create(route=r2, stop=created_stops["The Arc"], sequence_no=4, est_minutes=18)
        RouteStop.objects.create(route=r2, stop=created_stops["MMU Bus Stop"], sequence_no=5, est_minutes=24)

        r3 = Route.objects.create(name="Train Route", description="Campus -> MRT Cyberjaya Utara")
        RouteStop.objects.create(route=r3, stop=created_stops["MMU Bus Stop"], sequence_no=1, est_minutes=0)
        RouteStop.objects.create(route=r3, stop=created_stops["Cyberjaya Utara Station"], sequence_no=2, est_minutes=15)
        RouteStop.objects.create(route=r3, stop=created_stops["MMU Bus Stop"], sequence_no=3, est_minutes=30)

        return {'vehicles': saved_vehicles, 'routes': [r1, r2, r3]}

    def _create_operations(self, users, assets):
        drivers = users['drivers'] 
        vehicles = assets['vehicles']
        routes = assets['routes']
        
        today = timezone.now().date()
        valid_from = today - timedelta(days=7)
        valid_to = today + timedelta(days=90)
        days_str = "Mon,Tue,Wed,Thu,Fri,Sat,Sun"

        pool_serin_d = drivers[0:4]
        pool_serin_v = [vehicles[0]]

        pool_mutiara_d = drivers[4:7]
        pool_mutiara_v = [vehicles[1]]

        pool_train_d = drivers[7:10]
        pool_train_v = [vehicles[2]]

        route_configs = [
            {'route': routes[0], 'd_pool': pool_serin_d, 'v_pool': pool_serin_v},
            {'route': routes[1], 'd_pool': pool_mutiara_d, 'v_pool': pool_mutiara_v},
            {'route': routes[2], 'd_pool': pool_train_d, 'v_pool': pool_train_v},
        ]

        shifts = [
            (time(7, 0), time(11, 0), 30),
            (time(11, 0), time(17, 0), 60),
            (time(17, 0), time(23, 0), 40),
            (time(23, 0), time(7, 0), 60),
        ]

        for config in route_configs:
            for start, end, freq in shifts:
                sched = Schedule.objects.create(
                    route=config['route'], days_of_week=days_str,
                    start_time=start, end_time=end, frequency_min=freq,
                    valid_from=valid_from, valid_to=valid_to,
                    default_driver=config['d_pool'][0],
                    default_vehicle=config['v_pool'][0]
                )

                trip_counter = 0
                for day_offset in [-1, 0, 1]: 
                    target_date = today + timedelta(days=day_offset)
                    try:
                        current_dt = datetime.combine(target_date, start)
                        end_dt = datetime.combine(target_date, end)
                        if end < start: end_dt += timedelta(days=1)
                    except: continue

                    while current_dt < end_dt:
                        trip_aware = timezone.make_aware(current_dt)
                        status = 'Scheduled'
                        age_seconds = (timezone.now() - trip_aware).total_seconds()
                        
                        if age_seconds > 0:
                            status = 'Completed'
                            if random.random() < 0.2:
                                status = 'Delayed'
                            
                            if age_seconds < (freq * 60):
                                status = 'In-Progress'
                        
                        trip = DailyTrip.objects.create(
                            schedule=sched, trip_date=target_date, planned_departure=trip_aware, status=status
                        )
                        
                        d = config['d_pool'][trip_counter % len(config['d_pool'])]
                        v = config['v_pool'][trip_counter % len(config['v_pool'])]
                        
                        DriverAssignment.objects.create(trip=trip, driver=d, vehicle=v)
                        
                        current_dt += timedelta(minutes=freq)
                        trip_counter += 1

    def _create_usage(self, users):
        students = users['students']
        today = timezone.now().date()
        trips_today = DailyTrip.objects.filter(trip_date=today)
        
        active_trip = trips_today.filter(status='In-Progress').first()
        result_info = None

        if active_trip:
            active_trip.planned_departure = timezone.now() - timedelta(minutes=2)
            active_trip.save()
            
            assign = active_trip.driverassignment_set.first()
            if assign:
                result_info = {'username': assign.driver.user.username, 'trip_id': active_trip.trip_id}

            bookings = []
            bookings.append(Booking(student=students[0], trip=active_trip, status='Checked-In'))
            for s in students[1:29]:
                 bookings.append(Booking(student=s, trip=active_trip, status='Confirmed'))
            Booking.objects.bulk_create(bookings)
            
            Incident.objects.create(
                reported_by=students[2].user, trip=active_trip, 
                description="AC is not working.", status='New'
            )

        past_trips = trips_today.filter(status__in=['Completed', 'Delayed'])
        all_past_bookings = []
        
        for trip in past_trips:
            num_passengers = random.randint(25, 35)
            trip_students = random.sample(students, num_passengers)
            for s in trip_students:
                all_past_bookings.append(Booking(student=s, trip=trip, status='Confirmed'))
        
        Booking.objects.bulk_create(all_past_bookings)

        future_trip = trips_today.filter(status='Scheduled').order_by('planned_departure').first()
        if future_trip:
            Booking.objects.create(student=students[0], trip=future_trip, status='Confirmed')
            Notification.objects.create(
                recipient=students[0].user, title="Booking Reminder",
                message=f"Don't forget your trip at {future_trip.planned_departure.strftime('%H:%M')}."
            )
        
        return result_info

    def _initialize_static_locations(self):
        active_trips = DailyTrip.objects.filter(status='In-Progress')
        locations = []
        for trip in active_trips:
            first_stop = trip.schedule.route.routestop_set.order_by('sequence_no').first()
            if first_stop:
                locations.append(CurrentLocation(
                    trip=trip, 
                    latitude=first_stop.stop.latitude, 
                    longitude=first_stop.stop.longitude
                ))
        CurrentLocation.objects.bulk_create(locations, ignore_conflicts=True)

# ================= ORGANIC SIMULATION ENGINE (OPTIMIZED) =================
    route_data_cache = {}
    trip_state = {}

    def get_route_geometry(self, route):
        # (Keep this method exactly as it was in your file, no changes needed here)
        stops = RouteStop.objects.filter(route=route).order_by('sequence_no')
        coordinates = ";".join([f"{s.stop.longitude},{s.stop.latitude}" for s in stops])
        url = f"http://router.project-osrm.org/route/v1/driving/{coordinates}?overview=full&geometries=geojson"
        path = []
        stop_indices = []

        try:
            response = requests.get(url, timeout=3)
            if response.status_code == 200:
                data = response.json()
                raw_coords = data['routes'][0]['geometry']['coordinates']
                path = [[c[1], c[0]] for c in raw_coords]
                for s in stops:
                    lat, lng = float(s.stop.latitude), float(s.stop.longitude)
                    closest_idx = 0
                    min_dist = 99999
                    for i, p in enumerate(path):
                        dist = (p[0]-lat)**2 + (p[1]-lng)**2
                        if dist < min_dist:
                            min_dist = dist
                            closest_idx = i
                    stop_indices.append(closest_idx)
                return {'path': path, 'stops': stop_indices}
        except:
            pass 

        stops_list = list(stops)
        path = []
        stop_indices = []
        current_idx = 0
        POINTS_BETWEEN_STOPS = 50

        for i in range(len(stops_list) - 1):
            start = stops_list[i].stop
            end = stops_list[i+1].stop
            stop_indices.append(current_idx)
            for j in range(POINTS_BETWEEN_STOPS):
                ratio = j / POINTS_BETWEEN_STOPS
                lat = float(start.latitude) + (float(end.latitude) - float(start.latitude)) * ratio
                lng = float(start.longitude) + (float(end.longitude) - float(start.longitude)) * ratio
                path.append([lat, lng])
                current_idx += 1
        last_stop = stops_list[-1].stop
        path.append([float(last_stop.latitude), float(last_stop.longitude)])
        stop_indices.append(current_idx)

        return {'path': path, 'stops': stop_indices}

    def _run_simulation(self, excluded_trip_id=None):
        # CONFIGURATION: Reduced update rate to prevent browser/DB lag
        TICK_RATE = 5.0   # Update DB every 5 seconds (was 2.0)
        DWELL_TIME = 10.0 # Stop at bus stops for 10 seconds
        SPEED_MULTIPLIER = 1.0 
        
        from django.db import connections

        self.stdout.write(self.style.SUCCESS(f'    (Optimized Mode: Updating map every {TICK_RATE} seconds)'))

        while True:
            now = timezone.now()

            # 1. AUTO-DISPATCH: Start Scheduled trips
            # Use select_related to prevent extra DB queries
            pending_starts = DailyTrip.objects.filter(
                status='Scheduled',
                planned_departure__lte=now,
                planned_departure__gte=now - timedelta(minutes=10) 
            ).select_related('schedule__route')

            for trip in pending_starts:
                # Check existance efficiently
                if not DailyTrip.objects.filter(schedule=trip.schedule, status='In-Progress').exists():
                    trip.status = 'In-Progress'
                    trip.save()
                    self.stdout.write(f"[{now.strftime('%H:%M:%S')}] DISPATCH: #{trip.trip_id} ({trip.schedule.route.name})")

            # 2. MOVE BUSES
            # Optimized: Fetch related route data in the main query to avoid N+1 problem
            active_trips = DailyTrip.objects.filter(status='In-Progress').select_related('schedule__route')

            if not active_trips.exists():
                self.stdout.write(f"[{now.strftime('%H:%M:%S')}] Waiting for schedule...", ending='\r')
                
                # Close DB connection while sleeping to release locks for other users
                connections.close_all()
                python_time.sleep(TICK_RATE)
                continue

            for trip in active_trips:
                if excluded_trip_id and trip.trip_id == excluded_trip_id:
                    continue

                rid = trip.schedule.route.route_id
                if rid not in self.route_data_cache:
                    # Note: This might block for 1-2s on first run, but only once per route
                    self.route_data_cache[rid] = self.get_route_geometry(trip.schedule.route)
                
                data = self.route_data_cache[rid]
                path = data['path']
                stop_indices = set(data['stops'])

                if trip.trip_id not in self.trip_state:
                    self.trip_state[trip.trip_id] = {'idx': 0.0, 'dwell': 0}
                
                state = self.trip_state[trip.trip_id]

                # Handle Dwell Time (Waiting at bus stop)
                if state['dwell'] > 0:
                    state['dwell'] -= (1 * TICK_RATE) # Burn dwell time
                    
                    # Ensure we don't crash if index is out of bounds (safety check)
                    safe_idx = min(int(state['idx']), len(path) - 1)
                    lat, lng = path[safe_idx]
                    
                    CurrentLocation.objects.update_or_create(
                        trip=trip, 
                        defaults={'latitude': lat, 'longitude': lng, 'last_update': now}
                    )
                    continue

                # Move the Bus
                # Logic: Total Trip = 20 mins (1200s). 
                # Speed = Total Points / 1200. 
                # Step = Speed * Time_Passed.
                moving_time = 1200.0 
                speed = len(path) / moving_time 
                
                # Calculate jump based on TICK_RATE (5s jump is larger than 2s jump)
                state['idx'] += (speed * TICK_RATE * SPEED_MULTIPLIER)
                current_int_idx = int(state['idx'])

                if current_int_idx >= len(path):
                    trip.status = 'Completed'
                    trip.save()
                    del self.trip_state[trip.trip_id]
                    self.stdout.write(f"[{now.strftime('%H:%M:%S')}] ARRIVAL: #{trip.trip_id} Finished.")
                else:
                    # Check if we passed a bus stop during this jump
                    prev_idx = int(state['idx'] - (speed * TICK_RATE * SPEED_MULTIPLIER))
                    
                    # Update Location in DB
                    lat, lng = path[current_int_idx]
                    CurrentLocation.objects.update_or_create(
                        trip=trip, 
                        defaults={'latitude': lat, 'longitude': lng, 'last_update': now}
                    )
                    
                    # Check for stops
                    for s_idx in stop_indices:
                        if prev_idx < s_idx <= current_int_idx:
                            state['idx'] = float(s_idx) # Snap to stop
                            state['dwell'] = int(DWELL_TIME)
                            current_int_idx = s_idx
                            break
            
            # Explicitly close connections to free up SQLite locks for the Browser
            connections.close_all()
            python_time.sleep(TICK_RATE)