from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth import get_user_model
from mainapp.models import (
    Student, Driver, TransportCoordinator, Admin, 
    Vehicle, Stop, Route, RouteStop, Schedule, 
    DailyTrip, DriverAssignment, Booking, Incident, Notification
)
import datetime
import random

User = get_user_model()

class Command(BaseCommand):
    help = 'Populates the database with specific routes (Serin, SOHO, Mutiara, Train) and extensive dummy data.'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.WARNING("⚠ Wiping old data..."))
        
        # 1. CLEAN SLATE (Order matters for Foreign Keys)
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
        
        # Only delete non-superuser Users to preserve your login
        User.objects.filter(is_superuser=False).delete()
        
        self.stdout.write(self.style.SUCCESS("Old data wiped. Starting population..."))

        # ==========================================
        # 2. CREATE USERS
        # ==========================================
        def create_user(username, role, first_name, last_name):
            user = User.objects.create_user(
                username=username,
                email=f"{username}@example.com",
                password='password123',
                first_name=first_name,
                last_name=last_name,
                role=role
            )
            return user

        # A. Staff
        create_user('admin', 'admin', 'Super', 'Admin')
        create_user('coordinator', 'coordinator', 'Head', 'Coordinator')
        self.stdout.write("Created Admin & Coordinator")

        # B. 5 Drivers
        drivers = []
        driver_names = [
            ('ali_driver', 'Ali', 'Baba'),
            ('ah_meng', 'Ah', 'Meng'),
            ('muthu_d', 'Muthu', 'Samy'),
            ('sarah_j', 'Sarah', 'Jane'),
            ('david_b', 'David', 'Beck')
        ]
        
        for username, fname, lname in driver_names:
            u = create_user(username, 'driver', fname, lname)
            # Update the profile created by signals.py
            d_profile = u.driver_profile
            d_profile.license_no = f"L-{random.randint(10000, 99999)}"
            d_profile.save()
            drivers.append(d_profile)
            
        self.stdout.write(f"Created {len(drivers)} Drivers")

        # C. 20 Students
        students = []
        for i in range(1, 21):
            u = create_user(f'student{i}', 'student', f'Student', f'{i}')
            u.phone = f"012-34567{i:02d}"
            u.save()
            students.append(u.student_profile)
            
        self.stdout.write(f"Created {len(students)} Students")

        # ==========================================
        # 3. CREATE ASSETS (Vehicles & Stops)
        # ==========================================
        # Vehicles
        vehicle_configs = [
            ('WTA 1234', 44, 'Bus'), ('BMS 5678', 44, 'Bus'), 
            ('PHP 9090', 44, 'Bus'), ('JVX 3344', 12, 'Van'), ('PYT 1122', 12, 'Van')
        ]
        vehicles = []
        for plate, cap, vtype in vehicle_configs:
            v = Vehicle.objects.create(plate_no=plate, capacity=cap, type=vtype)
            vehicles.append(v)

        # Stops (Consolidated list from your request)
        stops_config = [
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
            ('Cyberjaya Utara Station', 2.9507, 101.6567)
        ]
        stop_objs = {}
        for name, lat, lng in stops_config:
            s = Stop.objects.create(name=name, latitude=lat, longitude=lng)
            stop_objs[name] = s

        # ==========================================
        # 4. CREATE ROUTES & SCHEDULES
        # ==========================================
        
        # --- Route 1: Serin Route ---
        route_serin = Route.objects.create(name="Serin Route", description="Route servicing Serin and Cyberia areas.")
        stops_serin = ['MMU Bus Stop', 'Serin Residency', 'Crystal Serin', 'Cyberia Crescent 1', 'MMU Bus Stop']
        for i, s_name in enumerate(stops_serin):
            RouteStop.objects.create(route=route_serin, stop=stop_objs[s_name], sequence_no=i+1, est_minutes=i*5)

        # --- Route 2: SOHO Route ---
        route_soho = Route.objects.create(name="SOHO Route", description="Servicing Third Avenue, Cybersquare, and Kanvas.")
        stops_soho = ['MMU Bus Stop', 'Third Avenue', 'Cybersquare SOHO', 'Kanvas SOHO', 'MMU Bus Stop']
        for i, s_name in enumerate(stops_soho):
            RouteStop.objects.create(route=route_soho, stop=stop_objs[s_name], sequence_no=i+1, est_minutes=i*6)

        # --- Route 3: Mutiara Route ---
        route_mutiara = Route.objects.create(name="Mutiara Route", description="Servicing Lakefront, Mutiara Ville, and The Arc.")
        stops_mutiara = ['MMU Bus Stop', 'Lakefront Villa Stop', 'Mutiara Ville', 'The Arc', 'MMU Bus Stop']
        for i, s_name in enumerate(stops_mutiara):
            RouteStop.objects.create(route=route_mutiara, stop=stop_objs[s_name], sequence_no=i+1, est_minutes=i*5)

        # --- Route 4: Train Route ---
        route_train = Route.objects.create(name="Train Route", description="Direct shuttle to Cyberjaya Utara MRT Station.")
        stops_train = ['MMU Bus Stop', 'Cyberjaya Utara Station', 'MMU Bus Stop']
        for i, s_name in enumerate(stops_train):
            RouteStop.objects.create(route=route_train, stop=stop_objs[s_name], sequence_no=i+1, est_minutes=i*15)

        # Schedules
        today = timezone.now().date()
        next_year = today + datetime.timedelta(days=365)
        
        schedules = []

        # Schedule 1: Serin (Bus 1, Ali)
        schedules.append(Schedule.objects.create(
            route=route_serin,
            days_of_week="Mon,Tue,Wed,Thu,Fri",
            start_time=datetime.time(8, 0),
            end_time=datetime.time(18, 0),
            frequency_min=30,
            valid_from=today,
            valid_to=next_year,
            default_driver=drivers[0], 
            default_vehicle=vehicles[0]
        ))

        # Schedule 2: SOHO (Bus 2, Ah Meng)
        schedules.append(Schedule.objects.create(
            route=route_soho,
            days_of_week="Mon,Tue,Wed,Thu,Fri",
            start_time=datetime.time(8, 15),
            end_time=datetime.time(18, 15),
            frequency_min=45,
            valid_from=today,
            valid_to=next_year,
            default_driver=drivers[1], 
            default_vehicle=vehicles[1]
        ))

        # Schedule 3: Mutiara (Bus 3, Muthu)
        schedules.append(Schedule.objects.create(
            route=route_mutiara,
            days_of_week="Mon,Tue,Wed,Thu,Fri",
            start_time=datetime.time(7, 30),
            end_time=datetime.time(19, 30),
            frequency_min=30,
            valid_from=today,
            valid_to=next_year,
            default_driver=drivers[2], 
            default_vehicle=vehicles[2]
        ))

        # Schedule 4: Train (Van 1, Sarah)
        schedules.append(Schedule.objects.create(
            route=route_train,
            days_of_week="Mon,Tue,Wed,Thu,Fri,Sat,Sun",
            start_time=datetime.time(6, 0),
            end_time=datetime.time(22, 0),
            frequency_min=60,
            valid_from=today,
            valid_to=next_year,
            default_driver=drivers[3], 
            default_vehicle=vehicles[3]
        ))

        self.stdout.write("Created 4 Routes & Schedules")

        # ==========================================
        # 5. GENERATE TRIPS (Past 7 Days + Next 14 Days)
        # ==========================================
        total_trips = 0
        start_date = today - datetime.timedelta(days=7) # 7 days ago
        end_date = today + datetime.timedelta(days=14)  # 14 days ahead
        
        current_date = start_date
        while current_date <= end_date:
            day_str = current_date.strftime('%a') # Mon, Tue...
            
            for sched in schedules:
                if day_str in sched.days_of_week:
                    # Generate slots
                    curr_time = datetime.datetime.combine(current_date, sched.start_time)
                    end_time = datetime.datetime.combine(current_date, sched.end_time)
                    
                    while curr_time < end_time:
                        # Determine Status based on time
                        now = timezone.now()
                        trip_dt = timezone.make_aware(curr_time)
                        
                        if trip_dt < now:
                            status = 'Completed'
                        elif trip_dt.date() == now.date() and abs((trip_dt - now).total_seconds()) < 3600:
                            status = 'In-Progress' # Simulate live trip
                        else:
                            status = 'Scheduled'

                        # Create Trip
                        trip = DailyTrip.objects.create(
                            schedule=sched,
                            trip_date=current_date,
                            planned_departure=trip_dt,
                            status=status
                        )
                        
                        # Assign Driver
                        DriverAssignment.objects.create(
                            trip=trip, 
                            driver=sched.default_driver, 
                            vehicle=sched.default_vehicle
                        )
                        
                        # ==========================================
                        # 6. GENERATE BOOKINGS
                        # ==========================================
                        # Randomly book 0-8 students per trip
                        if status != 'Cancelled':
                            num_bookings = random.randint(0, 8)
                            trip_students = random.sample(students, num_bookings)
                            
                            for stu in trip_students:
                                # Determine booking status
                                if status == 'Completed':
                                    b_status = random.choice(['Confirmed', 'Checked-In'])
                                elif status == 'In-Progress':
                                    b_status = random.choice(['Confirmed', 'Checked-In'])
                                else:
                                    b_status = 'Confirmed'

                                Booking.objects.create(
                                    student=stu,
                                    trip=trip,
                                    status=b_status
                                )

                        total_trips += 1
                        curr_time += datetime.timedelta(minutes=sched.frequency_min)
            
            current_date += datetime.timedelta(days=1)

        self.stdout.write(f"Generated {total_trips} Trips with random bookings.")

        # ==========================================
        # 7. EXTRAS
        # ==========================================
        last_trip = DailyTrip.objects.last()
        Incident.objects.create(
            reported_by=students[0].user,
            trip=last_trip,
            description="Driver skipped the stop at Serin.",
            status='New'
        )
        
        for s in students[:5]:
            Notification.objects.create(
                recipient=s.user,
                sent_by=Admin.objects.first().user,
                title="New Routes Added",
                message="We have updated the routes to include Serin, SOHO, Mutiara, and the Train Station."
            )

        self.stdout.write(self.style.SUCCESS(f"✅ DONE! Database populated with {total_trips} trips, {len(students)} students, and your requested routes."))