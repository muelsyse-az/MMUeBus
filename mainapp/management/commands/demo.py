from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.utils import timezone
from datetime import timedelta, time, datetime
import random

from mainapp.models import (
    Student, Driver, TransportCoordinator, Admin,
    Vehicle, Stop, Route, RouteStop, Schedule,
    DailyTrip, DriverAssignment, Booking, Incident, Notification, CurrentLocation
)

User = get_user_model()

class Command(BaseCommand):
    help = 'Sets up a Minimal Demo environment covering ALL use cases for testing.'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.WARNING('Cleaning database...'))
        self._clear_data()

        self.stdout.write(self.style.SUCCESS('1. Creating User Accounts...'))
        users = self._create_users()

        self.stdout.write(self.style.SUCCESS('2. Creating Infrastructure (Bus, Route, Stops)...'))
        assets = self._create_assets()

        self.stdout.write(self.style.SUCCESS('3. Generating Historical Data (Populating Performance Dashboard)...'))
        self._create_history(users, assets)

        self.stdout.write(self.style.SUCCESS('4. Setting up Live Scenarios (Active & Future)...'))
        self._create_live_scenarios(users, assets)

        self.stdout.write(self.style.SUCCESS('------------------------------------------------'))
        self.stdout.write(self.style.SUCCESS('✅ DEMO ENVIRONMENT READY'))
        self.stdout.write(self.style.SUCCESS('------------------------------------------------'))
        self.stdout.write(self.style.SUCCESS(f"  [Admin]       admin    / pass1234  (Test: Manage Users)"))
        self.stdout.write(self.style.SUCCESS(f"  [Coordinator] coord    / pass1234  (Test: Manage Schedules/Incidents)"))
        self.stdout.write(self.style.SUCCESS(f"  [Driver]      driver1  / pass1234  (Test: Active Trip/Report Delay)"))
        self.stdout.write(self.style.SUCCESS(f"  [Student]     student1 / pass1234  (Test: Check-In/View Location)"))
        self.stdout.write(self.style.SUCCESS(f"  [Student]     student2 / pass1234  (Test: Cancel Reservation)"))
        self.stdout.write(self.style.SUCCESS('------------------------------------------------'))

    def _clear_data(self):
        """Wipes the database clean to ensure no bugs from old data."""
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
        """Creates one user of each role for testing."""
        pw = make_password('pass1234')
        
        # 1. Admin (Manage User Accounts)
        admin = User.objects.create(
            username='admin', email='admin@demo.com', password=pw,
            first_name="System", last_name="Admin", role='admin', 
            is_staff=True, is_superuser=True
        )

        # 2. Coordinator (Manage Routes/Schedules/Incidents)
        coord = User.objects.create(
            username='coord', email='coord@demo.com', password=pw,
            first_name="Alex", last_name="Coordinator", role='coordinator'
        )

        # 3. Driver (Capture Location, Report Delay)
        driver_user = User.objects.create(
            username='driver1', email='driver1@demo.com', password=pw,
            first_name="David", last_name="Driver", role='driver'
        )
        driver = Driver.objects.get(user=driver_user) # Profile created by signal

        # 4. Students (Reserve, Check-In, Cancel)
        s1_user = User.objects.create(
            username='student1', email='student1@demo.com', password=pw,
            first_name="Sarah", last_name="Student", role='student'
        )
        s2_user = User.objects.create(
            username='student2', email='student2@demo.com', password=pw,
            first_name="James", last_name="Student", role='student'
        )
        s1 = Student.objects.get(user=s1_user)
        s2 = Student.objects.get(user=s2_user)

        return {'admin': admin, 'coord': coord, 'driver': driver, 's1': s1, 's2': s2}

    def _create_assets(self):
        """Creates minimal infrastructure."""
        # Vehicle
        bus = Vehicle.objects.create(plate_no="DEMO-888", capacity=30, type="Bus")

        # Stops
        stop1 = Stop.objects.create(name="MMU Main Gate", latitude=2.9289, longitude=101.6417)
        stop2 = Stop.objects.create(name="Cyberia Smarthomes", latitude=2.9211, longitude=101.6416)
        stop3 = Stop.objects.create(name="DPulze Mall", latitude=2.9213, longitude=101.6500)

        # Route
        route = Route.objects.create(name="Campus Loop", description="Main Gate -> Cyberia -> DPulze")
        RouteStop.objects.create(route=route, stop=stop1, sequence_no=1, est_minutes=0)
        RouteStop.objects.create(route=route, stop=stop2, sequence_no=2, est_minutes=10)
        RouteStop.objects.create(route=route, stop=stop3, sequence_no=3, est_minutes=20)
        RouteStop.objects.create(route=route, stop=stop1, sequence_no=4, est_minutes=30)

        # Schedule (Daily 8 AM to 8 PM)
        sched = Schedule.objects.create(
            route=route, days_of_week="Mon,Tue,Wed,Thu,Fri,Sat,Sun",
            start_time=time(8,0), end_time=time(20,0), frequency_min=60,
            valid_from=timezone.now().date() - timedelta(days=30),
            valid_to=timezone.now().date() + timedelta(days=30),
            default_driver=None, default_vehicle=bus
        )

        return {'bus': bus, 'route': route, 'sched': sched, 'stops': [stop1, stop2, stop3]}

    def _create_history(self, users, assets):
        """
        Creates completed trips in the past. 
        CRITICAL: This ensures the Performance Dashboard isn't empty.
        """
        today = timezone.now().date()
        
        # Create 1 trip for each of the last 5 days
        for i in range(1, 6):
            past_date = today - timedelta(days=i)
            # Create a Completed trip
            trip = DailyTrip.objects.create(
                schedule=assets['sched'],
                trip_date=past_date,
                planned_departure=timezone.make_aware(datetime.combine(past_date, time(10, 0))),
                status='Completed'
            )
            DriverAssignment.objects.create(trip=trip, driver=users['driver'], vehicle=assets['bus'])
            
            # Add random completed bookings (Stats)
            for _ in range(random.randint(5, 15)):
                # We reuse student1 for history stats, it doesn't matter who it is
                Booking.objects.create(
                    student=users['s1'], trip=trip, status='Completed'
                )

    def _create_live_scenarios(self, users, assets):
        """
        Creates specific data for manual testing steps.
        """
        now = timezone.localtime()
        today = now.date()

        # ==========================================================
        # SCENARIO A: ACTIVE TRIP (Testing: Tracking, Check-In, Reporting)
        # ==========================================================
        # Trip started 10 mins ago
        active_trip = DailyTrip.objects.create(
            schedule=assets['sched'],
            trip_date=today,
            planned_departure=now - timedelta(minutes=10),
            status='In-Progress' 
        )
        DriverAssignment.objects.create(trip=active_trip, driver=users['driver'], vehicle=assets['bus'])
        
        # 1. Location Data (For "View Shuttle Location")
        CurrentLocation.objects.create(
            trip=active_trip,
            latitude=2.9250, longitude=101.6417, # Somewhere near MMU
            last_update=now
        )
        
        # 2. Booking for Student 1 (For "Check In for Shuttle")
        Booking.objects.create(
            student=users['s1'], trip=active_trip, status='Confirmed'
        )

        # ==========================================================
        # SCENARIO B: FUTURE TRIP (Testing: Reserve, Cancel, View Seats)
        # ==========================================================
        # Trip in 2 hours
        future_trip = DailyTrip.objects.create(
            schedule=assets['sched'],
            trip_date=today,
            planned_departure=now + timedelta(hours=2),
            status='Scheduled'
        )
        DriverAssignment.objects.create(trip=future_trip, driver=users['driver'], vehicle=assets['bus'])

        # 1. Booking for Student 2 (For "Cancel Seat Reservation")
        Booking.objects.create(
            student=users['s2'], trip=future_trip, status='Confirmed'
        )

        # ==========================================================
        # SCENARIO C: INCIDENTS & NOTIFICATIONS (Testing: Management)
        # ==========================================================
        # 1. New Incident (For "Resolve Incidents")
        Incident.objects.create(
            reported_by=users['s1'].user,
            trip=active_trip,
            description="Seatbelt in row 4 is broken.",
            status='New'
        )

        # 2. Notification (For "Receive Notifications")
        Notification.objects.create(
            recipient=users['s1'].user,
            title="Trip Reminder",
            message="Your bus to Cyberia is arriving soon."
        )

        Notification.objects.create(
            recipient=users['coord'].user,
            title="System Alert",
            message="High traffic reported on Main Route."
        )