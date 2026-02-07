from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta, datetime, time
from mainapp.models import (
    Student, Driver, TransportCoordinator, Admin,
    Vehicle, Stop, Route, RouteStop, Schedule,
    DailyTrip, DriverAssignment, Booking, Incident, Notification, CurrentLocation
)

User = get_user_model()

class Command(BaseCommand):
    help = 'MINIMAL SCRIPT: 1 Admin, 1 Coord, 1 Driver, 1 Student, 1 24-Hour Trip.'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.WARNING('Deleting old data...'))
        self._clear_data()
        
        self.stdout.write(self.style.SUCCESS('Creating Users...'))
        users = self._create_users()
        
        self.stdout.write(self.style.SUCCESS('Creating Infrastructure...'))
        assets = self._create_infrastructure()
        
        self.stdout.write(self.style.SUCCESS('Creating 24-Hour Schedule & Trip (For NOW)...'))
        self._create_operations(users, assets)
        
        self.stdout.write(self.style.SUCCESS('--------------------------------------------------'))
        self.stdout.write(self.style.SUCCESS('MINIMAL POPULATION COMPLETE'))
        self.stdout.write(self.style.SUCCESS('--------------------------------------------------'))
        self.stdout.write(f"Admin:       admin / pass1234")
        self.stdout.write(f"Coordinator: coordinator / pass1234")
        self.stdout.write(f"Driver:      driver1 / pass1234 (Trip ready immediately)")
        self.stdout.write(f"Student:     student1 / pass1234")

    def _clear_data(self):
        # Order matters to avoid Foreign Key errors
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
        admin_user.first_name = "System"; admin_user.last_name = "Admin"; admin_user.save()

        # 2. Coordinator
        coord_user = User.objects.create_user('coordinator', 'coord@mmu.edu.my', 'pass1234', role='coordinator')
        coord_user.first_name = "Mr."; coord_user.last_name = "Coordinator"; coord_user.save()

        # 3. Driver
        driver_user = User.objects.create_user('driver1', 'driver1@mmu.edu.my', 'pass1234', role='driver')
        driver_user.first_name = "Ali"; driver_user.last_name = "Abu"; driver_user.save()
        
        # Profile creation handled by signals usually, but let's be safe and fetch/update
        driver = driver_user.driver_profile
        driver.license_no = "L 123456"
        driver.save()

        # 4. Student
        student_user = User.objects.create_user('student1', 'student1@mmu.edu.my', 'pass1234', role='student')
        student_user.first_name = "Siti"; student_user.last_name = "Aminah"; student_user.save()
        student = student_user.student_profile

        return {'driver': driver, 'student': student}

    def _create_infrastructure(self):
        # 1 Vehicle
        vehicle = Vehicle.objects.create(plate_no="MMU 1234", capacity=40, type='Bus')

        # 2 Stops
        # Need to create stops first so we can link them
        s1 = Stop.objects.create(name="MMU Main Gate", latitude=2.9251, longitude=101.6420)
        s2 = Stop.objects.create(name="Cyberia Townhouse", latitude=2.9211, longitude=101.6416)

        # 1 Route
        route = Route.objects.create(name="Test Route", description="Simple Loop")
        
        # Stops linked to Route
        RouteStop.objects.create(route=route, stop=s1, sequence_no=1, est_minutes=0)
        RouteStop.objects.create(route=route, stop=s2, sequence_no=2, est_minutes=5)
        RouteStop.objects.create(route=route, stop=s1, sequence_no=3, est_minutes=10)

        return {'vehicle': vehicle, 'route': route}

    def _create_operations(self, users, assets):
        now = timezone.now()
        
        # Create a 24-hour schedule (00:00 to 23:59)
        # This ensures there is ALWAYS a valid shift
        schedule = Schedule.objects.create(
            route=assets['route'],
            days_of_week="Mon,Tue,Wed,Thu,Fri,Sat,Sun",
            start_time=time(0, 0),    # Midnight start
            end_time=time(23, 59),    # Midnight end
            frequency_min=60,         # Hourly trips
            valid_from=now.date() - timedelta(days=1),
            valid_to=now.date() + timedelta(days=365),
            default_driver=users['driver'],
            default_vehicle=assets['vehicle']
        )

        # Create 1 Trip Scheduled for roughly NOW so it appears at the top
        # We set it to 'Scheduled' so the driver can click 'Start'
        trip = DailyTrip.objects.create(
            schedule=schedule,
            trip_date=now.date(),
            planned_departure=now, 
            status='Scheduled' 
        )

        DriverAssignment.objects.create(
            trip=trip,
            driver=users['driver'],
            vehicle=assets['vehicle']
        )