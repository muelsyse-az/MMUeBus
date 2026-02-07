from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta, datetime, time
import random
import time as python_time
import math
import requests

from mainapp.models import (
    Student, Driver, TransportCoordinator, Admin,
    Vehicle, Stop, Route, RouteStop, Schedule,
    DailyTrip, DriverAssignment, Booking, Incident, Notification, CurrentLocation
)

User = get_user_model()

class Command(BaseCommand):
    help = 'Populates DB with realistic 24/7 schedules. EXCLUDES active driver from simulation.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--simulate',
            action='store_true',
            help='Continuously simulate bus movement (Real-time)',
        )

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.WARNING('Deleting old data...'))
        self._clear_data()
        
        self.stdout.write(self.style.SUCCESS('Creating Users...'))
        users = self._create_users()
        
        self.stdout.write(self.style.SUCCESS('Creating Infrastructure...'))
        assets = self._create_infrastructure()
        
        self.stdout.write(self.style.SUCCESS('Creating Operations...'))
        self._create_operations(users, assets)
        
        self.stdout.write(self.style.SUCCESS('Simulating Usage...'))
        # Capture the Trip ID of the active driver
        active_driver_info = self._create_usage(users)
        active_trip_id = active_driver_info['trip_id'] if active_driver_info else None
        active_username = active_driver_info['username'] if active_driver_info else None
        
        self.stdout.write(self.style.SUCCESS('Initializing Map Locations...'))
        self._initialize_static_locations()

        self.stdout.write(self.style.SUCCESS('--------------------------------------------------'))
        self.stdout.write(self.style.SUCCESS('POPULATION COMPLETE'))
        self.stdout.write(self.style.SUCCESS('--------------------------------------------------'))
        
        if active_username:
             self.stdout.write(self.style.SUCCESS(f"👉 REAL TEST DRIVER: {active_username} / pass1234"))
             self.stdout.write(self.style.WARNING(f"   (Trip #{active_trip_id} is EXCLUDED from simulation so you can provide real GPS)"))
        
        if kwargs['simulate']:
            self.stdout.write(self.style.WARNING('\n>>> STARTING ORGANIC SIMULATION (Ctrl+C to stop) <<<'))
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
        # 1. Admin
        admin_user = User.objects.create_superuser('admin', 'admin@mmu.edu.my', 'pass1234')
        admin_user.first_name = "System"
        admin_user.last_name = "Administrator"
        admin_user.save()

        # 2. Coordinator
        coord_user = User.objects.create_user('coordinator', 'coord@mmu.edu.my', 'pass1234', role='coordinator')
        coord_user.first_name = "Azman"
        coord_user.last_name = "Hashim"
        coord_user.save()

        # 3. Drivers (10 Realistic Malaysian Names)
        driver_identities = [
            ("Ahmad", "bin Abdullah"), ("Tan", "Wei Ming"), ("Muthu", "a/l Ramasamy"),
            ("Mohd", "Rizal bin Zakaria"), ("Lee", "Siew Ling"), ("Ravi", "a/l Chandran"),
            ("Wan", "Azman bin Wan Hassan"), ("Wong", "Ah Hock"), ("Suresh", "a/l Krishnan"),
            ("Nurul", "Huda binti Osman")
        ]
        
        drivers = []
        for i, (first, last) in enumerate(driver_identities, 1):
            u = User.objects.create_user(f'driver{i}', f'driver{i}@mmu.edu.my', 'pass1234', role='driver')
            u.first_name = first
            u.last_name = last
            u.save()
            d = u.driver_profile
            d.license_no = f"{random.choice(['L', 'B'])} {random.randint(100000, 999999)}"
            d.save()
            drivers.append(d)

        # 4. Students (50 Mix)
        student_names = [
            ("Sarah", "Liyana"), ("Jason", "Lim"), ("Divya", "Nair"), ("Muhammad", "Haziq"),
            ("Chong", "Wei Hong"), ("Thara", "Pillay"), ("Farah", "Liyana"), ("Vincent", "Tan"),
            ("Siti", "Nurhaliza"), ("Raj", "Kumar"), ("Kevin", "Wong"), ("Aishah", "Aziz"),
            ("Daniel", "Lee"), ("Preetha", "Menon"), ("Zainal", "Abidin")
        ]
        
        students = []
        for i in range(1, 51):
            u = User.objects.create_user(f'student{i}', f'student{i}@student.mmu.edu.my', 'pass1234', role='student')
            fname, lname = student_names[i % len(student_names)]
            u.first_name = fname
            u.last_name = f"{lname} {i}"
            u.save()
            students.append(u.student_profile)

        return {'admin': admin_user, 'coordinator': coord_user, 'drivers': drivers, 'students': students}

    def _create_infrastructure(self):
        # 10 Vehicles
        vehicles = []
        prefixes = ["MMU", "PADU"]
        
        for i in range(1, 11):
            prefix = random.choice(prefixes)
            number = random.randint(1000, 9999)
            plate = f"{prefix} {number}"
            v = Vehicle.objects.create(plate_no=plate, capacity=40, type='Bus')
            vehicles.append(v)
        
        # Stops
        stops_data = {
            "MMU Bus Stop": (2.9251, 101.6420), "Serin Residency": (2.9168, 101.6455),
            "Crystal Serin": (2.9194, 101.6458), "Cyberia Crescent 1": (2.9211, 101.6416),
            "Lakefront Villa Stop": (2.9321, 101.6336), "Mutiara Ville": (2.9230, 101.6325),
            "The Arc": (2.9251, 101.6375), "Cyberjaya Utara Station": (2.9507, 101.6567)
        }
        created_stops = {name: Stop.objects.create(name=name, latitude=lat, longitude=lon) for name, (lat, lon) in stops_data.items()}

        r1 = Route.objects.create(name="Serin Route", description="Campus -> Serin/Cyberia Loop")
        r1_list = ["MMU Bus Stop", "Serin Residency", "Crystal Serin", "Cyberia Crescent 1", "MMU Bus Stop"]
        for idx, s in enumerate(r1_list):
            RouteStop.objects.create(route=r1, stop=created_stops[s], sequence_no=idx+1, est_minutes=idx*5)

        r2 = Route.objects.create(name="Mutiara Route", description="Campus -> Lakefront/Arc Loop")
        r2_list = ["MMU Bus Stop", "Lakefront Villa Stop", "Mutiara Ville", "The Arc", "MMU Bus Stop"]
        for idx, s in enumerate(r2_list):
            RouteStop.objects.create(route=r2, stop=created_stops[s], sequence_no=idx+1, est_minutes=idx*6)

        r3 = Route.objects.create(name="Train Route", description="Campus -> MRT Cyberjaya Utara")
        r3_list = ["MMU Bus Stop", "Cyberjaya Utara Station", "MMU Bus Stop"]
        for idx, s in enumerate(r3_list):
            RouteStop.objects.create(route=r3, stop=created_stops[s], sequence_no=idx+1, est_minutes=idx*15)

        return {'vehicles': vehicles, 'routes': [r1, r2, r3]}

    def _create_operations(self, users, assets):
        drivers = users['drivers']
        vehicles = assets['vehicles']
        routes = assets['routes']
        
        today = timezone.now().date()
        valid_from = today - timedelta(days=7)
        valid_to = today + timedelta(days=90)
        days_str = "Mon,Tue,Wed,Thu,Fri,Sat,Sun"

        pool_serin_drivers = drivers[0:4]
        pool_serin_vehicles = vehicles[0:4]

        pool_mutiara_drivers = drivers[4:7]
        pool_mutiara_vehicles = vehicles[4:7]

        pool_train_drivers = drivers[7:10]
        pool_train_vehicles = vehicles[7:10]

        route_configs = [
            {'route': routes[0], 'd_pool': pool_serin_drivers, 'v_pool': pool_serin_vehicles},
            {'route': routes[1], 'd_pool': pool_mutiara_drivers, 'v_pool': pool_mutiara_vehicles},
            {'route': routes[2], 'd_pool': pool_train_drivers, 'v_pool': pool_train_vehicles},
        ]

        # 24/7 Schedules
        shifts = [
            (time(7, 0), time(11, 0), 15),  # Morning
            (time(11, 0), time(17, 0), 60), # Afternoon
            (time(17, 0), time(23, 0), 20), # Evening
            (time(23, 0), time(7, 0), 60),  # Night
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
                            if age_seconds < (freq * 60):
                                status = 'In-Progress'
                        
                        trip = DailyTrip.objects.create(
                            schedule=sched, trip_date=target_date, planned_departure=trip_aware, status=status
                        )
                        
                        assigned_driver = config['d_pool'][trip_counter % len(config['d_pool'])]
                        assigned_vehicle = config['v_pool'][trip_counter % len(config['v_pool'])]
                        
                        DriverAssignment.objects.create(trip=trip, driver=assigned_driver, vehicle=assigned_vehicle)
                        
                        current_dt += timedelta(minutes=freq)
                        trip_counter += 1

    def _create_usage(self, users):
        students = users['students']
        today = timezone.now().date()
        trips_today = DailyTrip.objects.filter(trip_date=today)
        demo_student = students[0]
        
        active_trip = trips_today.filter(status='In-Progress').first()
        result_info = None

        if active_trip:
            # Shift timestamp to NOW for demo
            active_trip.planned_departure = timezone.now() - timedelta(minutes=2)
            active_trip.save()
            
            # Find the assigned driver
            assign = active_trip.driverassignment_set.first()
            if assign:
                result_info = {
                    'username': assign.driver.user.username,
                    'trip_id': active_trip.trip_id
                }

            Booking.objects.create(student=demo_student, trip=active_trip, status='Checked-In')
            for s in students[1:25]:
                 Booking.objects.create(student=s, trip=active_trip, status='Confirmed')
            Incident.objects.create(
                reported_by=students[2].user, trip=active_trip, 
                description="AC is not working.", status='New'
            )

        # Future Trip
        future_trip = trips_today.filter(status='Scheduled').order_by('planned_departure').first()
        if future_trip:
            Booking.objects.create(student=demo_student, trip=future_trip, status='Confirmed')
            Notification.objects.create(
                recipient=demo_student.user, title="Booking Reminder",
                message=f"Don't forget your trip at {future_trip.planned_departure.strftime('%H:%M')}."
            )
        
        return result_info

    def _initialize_static_locations(self):
        active_trips = DailyTrip.objects.filter(status='In-Progress')
        for trip in active_trips:
            first_stop = trip.schedule.route.routestop_set.order_by('sequence_no').first()
            if first_stop:
                CurrentLocation.objects.update_or_create(
                    trip=trip,
                    defaults={'latitude': first_stop.stop.latitude, 'longitude': first_stop.stop.longitude}
                )

    # ================= ORGANIC SIMULATION ENGINE =================
    route_data_cache = {}
    trip_state = {}

    def get_route_geometry(self, route):
        stops = RouteStop.objects.filter(route=route).order_by('sequence_no')
        coordinates = ";".join([f"{s.stop.longitude},{s.stop.latitude}" for s in stops])
        url = f"http://router.project-osrm.org/route/v1/driving/{coordinates}?overview=full&geometries=geojson"
        path = []
        stop_indices = []
        try:
            response = requests.get(url, timeout=5)
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
            else:
                path = [[float(s.stop.latitude), float(s.stop.longitude)] for s in stops]
                stop_indices = list(range(len(path)))
        except:
            path = [[float(s.stop.latitude), float(s.stop.longitude)] for s in stops]
            stop_indices = list(range(len(path)))

        return {'path': path, 'stops': stop_indices}

    def _run_simulation(self, excluded_trip_id=None):
        """
        Runs the simulation loop.
        excluded_trip_id: If provided, this trip ID will NOT be updated by the simulator
                          (allows real driver to send GPS updates).
        """
        TICK_RATE = 1.0 
        DWELL_TIME = 15.0 

        while True:
            now = timezone.now()

            # 1. DISPATCHER
            pending_starts = DailyTrip.objects.filter(
                status='Scheduled',
                planned_departure__lte=now,
                planned_departure__gte=now - timedelta(minutes=10) 
            )
            for trip in pending_starts:
                if not DailyTrip.objects.filter(schedule=trip.schedule, status='In-Progress').exists():
                    trip.status = 'In-Progress'
                    trip.save()
                    self.stdout.write(f"[{now.strftime('%H:%M:%S')}] DISPATCH: #{trip.trip_id} ({trip.schedule.route.name})")

            # 2. MOVEMENT
            active_trips = DailyTrip.objects.filter(status='In-Progress')

            if not active_trips.exists():
                self.stdout.write(f"[{now.strftime('%H:%M:%S')}] Waiting for schedule...", ending='\r')
                python_time.sleep(2)
                continue

            for trip in active_trips:
                # SKIP if this is the real driver's trip
                if excluded_trip_id and trip.trip_id == excluded_trip_id:
                    continue

                rid = trip.schedule.route.route_id
                if rid not in self.route_data_cache:
                    self.route_data_cache[rid] = self.get_route_geometry(trip.schedule.route)
                
                data = self.route_data_cache[rid]
                path = data['path']
                stop_indices = set(data['stops'])

                if trip.trip_id not in self.trip_state:
                    self.trip_state[trip.trip_id] = {'idx': 0.0, 'dwell': 0}
                
                state = self.trip_state[trip.trip_id]

                if state['dwell'] > 0:
                    state['dwell'] -= 1
                    lat, lng = path[int(state['idx'])]
                    CurrentLocation.objects.update_or_create(trip=trip, defaults={'latitude': lat, 'longitude': lng, 'last_update': now})
                    continue

                freq_sec = trip.schedule.frequency_min * 60
                moving_time = max(freq_sec - (len(data['stops']) * DWELL_TIME), 300)
                speed = len(path) / moving_time 
                
                state['idx'] += (speed * TICK_RATE)
                current_int_idx = int(state['idx'])

                if current_int_idx >= len(path):
                    trip.status = 'Completed'
                    trip.save()
                    del self.trip_state[trip.trip_id]
                    self.stdout.write(f"[{now.strftime('%H:%M:%S')}] ARRIVAL: #{trip.trip_id} Finished.")
                else:
                    prev_idx = int(state['idx'] - (speed * TICK_RATE))
                    for s_idx in stop_indices:
                        if prev_idx < s_idx <= current_int_idx:
                            state['idx'] = float(s_idx)
                            state['dwell'] = int(DWELL_TIME / TICK_RATE)
                            current_int_idx = s_idx
                            break
                    
                    lat, lng = path[current_int_idx]
                    CurrentLocation.objects.update_or_create(trip=trip, defaults={'latitude': lat, 'longitude': lng, 'last_update': now})

            python_time.sleep(TICK_RATE)