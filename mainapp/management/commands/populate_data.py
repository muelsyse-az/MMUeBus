from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth import get_user_model
from mainapp.models import (
    Student, Driver, TransportCoordinator, Admin, 
    Vehicle, Stop, Route, RouteStop, Schedule, 
    DailyTrip, DriverAssignment, Booking, Incident, Notification, CurrentLocation
)
import datetime
import random

User = get_user_model()

class Command(BaseCommand):
    help = 'Populates DB with realistic schedules, student behaviors, and active live tracking.'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.WARNING("⚠ Wiping old data..."))
        
        # 1. CLEAN SLATE
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
        User.objects.filter(is_superuser=False).delete()
        
        self.stdout.write(self.style.SUCCESS("Old data wiped. Starting population..."))

        # ==========================================
        # 2. CREATE USERS
        # ==========================================
        def create_user(username, role, first_name, last_name):
            return User.objects.create_user(
                username=username,
                email=f"{username}@example.com",
                password='password123',
                first_name=first_name,
                last_name=last_name,
                role=role
            )

        # Staff
        create_user('admin', 'admin', 'Super', 'Admin')
        create_user('coordinator', 'coordinator', 'Head', 'Coordinator')

        # Drivers
        drivers = []
        driver_data = [
            ('ali_driver', 'Ali', 'Baba'), ('ah_meng', 'Ah', 'Meng'),
            ('muthu_d', 'Muthu', 'Samy'), ('sara_j', 'Sara', 'Jane'),
            ('david_b', 'David', 'Beck')
        ]
        for u_name, f, l in driver_data:
            u = create_user(u_name, 'driver', f, l)
            d = u.driver_profile
            d.license_no = f"L-{random.randint(10000,99999)}"
            d.save()
            drivers.append(d)

        # Students (20 students)
        students = []
        for i in range(1, 21):
            u = create_user(f'student{i}', 'student', 'Student', f'{i}')
            u.phone = f"012-34567{i:02d}"
            u.save()
            students.append(u.student_profile)

        self.stdout.write(f"Users Created: {len(students)} Students, {len(drivers)} Drivers.")

        # ==========================================
        # 3. ASSETS & STOPS
        # ==========================================
        # Vehicles (Mix of Buses and Vans)
        vehicles = [
            Vehicle.objects.create(plate_no='WTA 1234', capacity=44, type='Bus'),
            Vehicle.objects.create(plate_no='BMS 5678', capacity=44, type='Bus'),
            Vehicle.objects.create(plate_no='PHP 9090', capacity=44, type='Bus'),
            Vehicle.objects.create(plate_no='JVX 3344', capacity=12, type='Van'),
            Vehicle.objects.create(plate_no='PYT 1122', capacity=12, type='Van'),
        ]

        # Stops
        stops_data = [
            ('MMU Bus Stop', 2.9251, 101.6420),
            ('Serin Residency', 2.9168, 101.6455),
            ('Crystal Serin', 2.9194, 101.6458),
            ('Cyberia Crescent 1', 2.9211, 101.6416),
            ('Third Avenue', 2.9292, 101.6554),
            ('Cybersquare SOHO', 2.9192, 101.6582),
            ('Kanvas SOHO', 2.9136, 101.6552),
            ('Lakefront Villa Stop', 2.9321, 101.6336),
            ('Mutiara Ville', 2.9230, 101.6325),
            ('The Arc', 2.9251, 101.6375),
            ('Cyberjaya Utara Station', 2.9507, 101.6567),
        ]
        stop_objs = {name: Stop.objects.create(name=name, latitude=lat, longitude=lng) for name, lat, lng in stops_data}

        # ==========================================
        # 4. REALISTIC ROUTES & TIMING
        # ==========================================
        routes_config = [
            {
                "name": "Serin Route", 
                "stops": [
                    ('MMU Bus Stop', 0), ('Serin Residency', 8), ('Crystal Serin', 12), 
                    ('Cyberia Crescent 1', 15), ('MMU Bus Stop', 25)
                ]
            },
            {
                "name": "SOHO Route", 
                "stops": [
                    ('MMU Bus Stop', 0), ('Third Avenue', 10), ('Cybersquare SOHO', 16), 
                    ('Kanvas SOHO', 22), ('MMU Bus Stop', 35)
                ]
            },
            {
                "name": "Mutiara Route", 
                "stops": [
                    ('MMU Bus Stop', 0), ('Lakefront Villa Stop', 12), ('Mutiara Ville', 18), 
                    ('The Arc', 24), ('MMU Bus Stop', 30)
                ]
            },
            {
                "name": "Train Route", 
                "stops": [
                    ('MMU Bus Stop', 0), ('Cyberjaya Utara Station', 15), ('MMU Bus Stop', 30)
                ]
            }
        ]

        created_routes = []
        for r_conf in routes_config:
            route = Route.objects.create(name=r_conf['name'])
            created_routes.append(route)
            for seq, (s_name, mins) in enumerate(r_conf['stops']):
                RouteStop.objects.create(
                    route=route, stop=stop_objs[s_name], sequence_no=seq+1, est_minutes=mins
                )

        # ==========================================
        # 5. REALISTIC SCHEDULES (Rush Hours)
        # ==========================================
        today = timezone.now().date()
        next_year = today + datetime.timedelta(days=365)
        schedules = []

        # Logic: 
        # - Morning Rush (7:30 - 10:30) - High Frequency (30m)
        # - Lunch Connector (12:00 - 14:00) - Medium Frequency (60m)
        # - Evening Rush (16:30 - 19:30) - High Frequency (30m)
        
        # We assign specific vehicles/drivers to routes to keep it consistent
        route_assignments = [
            (0, drivers[0], vehicles[0]), # Serin - Bus
            (1, drivers[1], vehicles[1]), # SOHO - Bus
            (2, drivers[2], vehicles[2]), # Mutiara - Bus
            (3, drivers[3], vehicles[3]), # Train - Van
        ]

        for r_idx, drv, veh in route_assignments:
            route = created_routes[r_idx]
            
            # Morning Rush
            schedules.append(Schedule.objects.create(
                route=route, days_of_week="Mon,Tue,Wed,Thu,Fri",
                start_time=datetime.time(7, 30), end_time=datetime.time(10, 30),
                frequency_min=30, valid_from=today, valid_to=next_year,
                default_driver=drv, default_vehicle=veh
            ))

            # Lunch
            schedules.append(Schedule.objects.create(
                route=route, days_of_week="Mon,Tue,Wed,Thu,Fri",
                start_time=datetime.time(12, 0), end_time=datetime.time(14, 0),
                frequency_min=60, valid_from=today, valid_to=next_year,
                default_driver=drv, default_vehicle=veh
            ))

            # Evening Rush
            schedules.append(Schedule.objects.create(
                route=route, days_of_week="Mon,Tue,Wed,Thu,Fri",
                start_time=datetime.time(16, 30), end_time=datetime.time(19, 30),
                frequency_min=30, valid_from=today, valid_to=next_year,
                default_driver=drv, default_vehicle=veh
            ))

        self.stdout.write("Schedules Initialized (Morning/Lunch/Evening blocks).")

        # ==========================================
        # 6. GENERATE TRIPS (Today Only) & ACTIVE TRACKING
        # ==========================================
        trips_generated = 0
        active_trips_count = 0
        now = timezone.now()
        day_str = now.strftime('%a')

        # We want to force at least one trip to be "active" right now for demo purposes
        # even if the schedule doesn't perfectly align.
        demo_active_trip_created = False 

        for sched in schedules:
            if day_str in sched.days_of_week:
                curr_time = datetime.datetime.combine(today, sched.start_time)
                end_time = datetime.datetime.combine(today, sched.end_time)
                
                while curr_time < end_time:
                    trip_dt = timezone.make_aware(curr_time)
                    
                    # Logic to determine status
                    time_diff = (now - trip_dt).total_seconds()
                    
                    # Trip duration approx 45 mins
                    is_happening_now = 0 <= time_diff <= (45 * 60)
                    is_past = time_diff > (45 * 60)
                    
                    if is_past:
                        status = 'Completed'
                    elif is_happening_now:
                        status = 'In-Progress'
                    else:
                        status = 'Scheduled'

                    # FORCE DEMO: If no active trip yet and this is a future trip near now,
                    # force it to be active for the demo.
                    if not demo_active_trip_created and status == 'Scheduled' and abs(time_diff) < 3600:
                        status = 'In-Progress'
                        demo_active_trip_created = True

                    # Create Trip
                    trip = DailyTrip.objects.create(
                        schedule=sched,
                        trip_date=today,
                        planned_departure=trip_dt,
                        status=status
                    )
                    
                    DriverAssignment.objects.create(
                        trip=trip, driver=sched.default_driver, vehicle=sched.default_vehicle
                    )

                    # IF ACTIVE: Add Dummy Location Data
                    if status == 'In-Progress':
                        active_trips_count += 1
                        # Pick a random point slightly offset from MMU to simulate movement
                        lat_offset = random.uniform(-0.005, 0.005)
                        lng_offset = random.uniform(-0.005, 0.005)
                        CurrentLocation.objects.create(
                            trip=trip,
                            latitude=2.9289 + lat_offset,
                            longitude=101.6417 + lng_offset
                        )

                    trips_generated += 1
                    curr_time += datetime.timedelta(minutes=sched.frequency_min)

        # ==========================================
        # 7. REALISTIC BOOKINGS
        # ==========================================
        # Assign students to "Home Routes"
        # 0-5: Serin, 6-10: SOHO, 11-15: Mutiara, 16-19: Train
        bookings_count = 0
        
        for i, student in enumerate(students):
            if i < 5: preferred_route_idx = 0
            elif i < 10: preferred_route_idx = 1
            elif i < 15: preferred_route_idx = 2
            else: preferred_route_idx = 3 # Train
            
            target_route = created_routes[preferred_route_idx]
            
            # Find 1 Morning Trip (To Campus)
            morning_trip = DailyTrip.objects.filter(
                schedule__route=target_route,
                planned_departure__hour__lt=12,
                status__in=['Scheduled', 'In-Progress', 'Completed']
            ).order_by('?').first() # Random morning trip
            
            # Find 1 Evening Trip (To Home)
            evening_trip = DailyTrip.objects.filter(
                schedule__route=target_route,
                planned_departure__hour__gte=16,
                status__in=['Scheduled', 'In-Progress']
            ).order_by('?').first()

            # Create Bookings
            if morning_trip:
                # If trip is completed, assume they rode it
                status = 'Checked-In' if morning_trip.status == 'Completed' else 'Confirmed'
                Booking.objects.create(student=student, trip=morning_trip, status=status)
                bookings_count += 1
                
            if evening_trip:
                Booking.objects.create(student=student, trip=evening_trip, status='Confirmed')
                bookings_count += 1

        self.stdout.write(self.style.SUCCESS(f"✅ DONE!"))
        self.stdout.write(f"- {trips_generated} trips generated for today.")
        self.stdout.write(f"- {active_trips_count} trips are currently 'In-Progress' and visible on the map.")
        self.stdout.write(f"- {bookings_count} realistic bookings created (Morning/Evening commute).")