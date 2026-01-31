from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone

# ==========================================
# 1. USER MANAGEMENT (SDS 3.3.1 - 3.3.5)
# ==========================================

class User(AbstractUser):
    """
    Custom User model supporting the 4 roles defined in the SDS.
    Fields inherited from AbstractUser: username, password, first_name, last_name, email.
    """
    ROLE_CHOICES = (
        ('student', 'Student'),
        ('driver', 'Driver'),
        ('coordinator', 'Transport Coordinator'),
        ('admin', 'Admin'),
    )

    # SDS 3.3.1 USERS Array
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    phone = models.CharField(max_length=15, blank=True, null=True)
    status = models.CharField(max_length=20, default='active')

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"

class Student(models.Model):
    # SDS 3.3.2 STUDENTS Array
    user = models.OneToOneField(User, on_delete=models.CASCADE, primary_key=True, related_name='student_profile')

    def __str__(self):
        return f"Student: {self.user.username}"

class Driver(models.Model):
    # SDS 3.3.3 DRIVERS Array
    user = models.OneToOneField(User, on_delete=models.CASCADE, primary_key=True, related_name='driver_profile')
    license_no = models.CharField(max_length=20)

    def __str__(self):
        return f"Driver: {self.user.username} ({self.license_no})"

class TransportCoordinator(models.Model):
    # SDS 3.3.4 COORDINATORS Array
    user = models.OneToOneField(User, on_delete=models.CASCADE, primary_key=True, related_name='coordinator_profile')

    def __str__(self):
        return f"Coordinator: {self.user.username}"

class Admin(models.Model):
    # SDS 3.3.5 ADMINS Array
    user = models.OneToOneField(User, on_delete=models.CASCADE, primary_key=True, related_name='admin_profile')

    def __str__(self):
        return f"Admin: {self.user.username}"


# ==========================================
# 2. TRANSPORT ASSETS (SDS 3.3.6, 3.3.7, 3.3.12)
# ==========================================

class Vehicle(models.Model):
    # SDS 3.3.12 VEHICLES Array
    VEHICLE_TYPES = (('Bus', 'Bus'), ('Van', 'Van'))

    vehicle_id = models.AutoField(primary_key=True)
    plate_no = models.CharField(max_length=15, unique=True)
    capacity = models.IntegerField()
    type = models.CharField(max_length=20, choices=VEHICLE_TYPES)

    def __str__(self):
        return f"{self.plate_no} ({self.type})"

class Stop(models.Model):
    # SDS 3.3.7 STOPS Array
    stop_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    # Using DecimalField for Lat/Long is standard practice for precision over Float
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)

    def __str__(self):
        return self.name

class Route(models.Model):
    # SDS 3.3.6 ROUTES Array
    route_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=50)
    description = models.TextField(blank=True, null=True)
    # Many-to-Many relationship with Stop via a 'through' model to store sequence
    stops = models.ManyToManyField(Stop, through='RouteStop')

    def __str__(self):
        return self.name

class RouteStop(models.Model):
    # SDS 3.3.8 ROUTE_STOPS Array
    route = models.ForeignKey(Route, on_delete=models.CASCADE)
    stop = models.ForeignKey(Stop, on_delete=models.CASCADE)
    sequence_no = models.PositiveIntegerField()  # Order of the stop
    est_minutes = models.IntegerField(help_text="Estimated minutes from start or previous stop")

    class Meta:
        ordering = ['sequence_no']
        unique_together = ('route', 'sequence_no') # Ensure no two stops have same order


# ==========================================
# 3. SCHEDULING & OPERATIONS (SDS 3.3.9 - 3.3.11, 3.3.13)
# ==========================================

class Schedule(models.Model):
    # SDS 3.3.9 SCHEDULES Array
    schedule_id = models.AutoField(primary_key=True)
    route = models.ForeignKey(Route, on_delete=models.CASCADE)
    days_of_week = models.CharField(max_length=50, help_text="Comma-separated days, e.g., 'Mon,Tue,Wed'")
    start_time = models.TimeField()
    end_time = models.TimeField()
    frequency_min = models.IntegerField()
    valid_from = models.DateField()
    valid_to = models.DateField()

    def __str__(self):
        return f"{self.route.name} ({self.start_time} - {self.end_time})"

class DailyTrip(models.Model):
    # SDS 3.3.10 DAILY_TRIPS Array
    STATUS_CHOICES = (
        ('Scheduled', 'Scheduled'),
        ('In-Progress', 'In-Progress'),
        ('Completed', 'Completed'),
        ('Cancelled', 'Cancelled'),
        ('Delayed', 'Delayed'),
    )

    trip_id = models.AutoField(primary_key=True)
    schedule = models.ForeignKey(Schedule, on_delete=models.CASCADE)
    trip_date = models.DateField()
    planned_departure = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Scheduled')

    def __str__(self):
        return f"Trip {self.trip_id} - {self.schedule.route.name} on {self.trip_date}"

class DriverAssignment(models.Model):
    # SDS 3.3.13 DRIVE_ASSIGNMENTS Array
    assignment_id = models.AutoField(primary_key=True)
    trip = models.ForeignKey(DailyTrip, on_delete=models.CASCADE)
    driver = models.ForeignKey(Driver, on_delete=models.CASCADE)
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE)
    assignment_date = models.DateField(auto_now_add=True)

class CurrentLocation(models.Model):
    # SDS 3.3.11 CURRENT_LOCATION Array
    # OneToOne because a trip has only one current location at a time
    trip = models.OneToOneField(DailyTrip, on_delete=models.CASCADE, primary_key=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    last_update = models.DateTimeField(auto_now=True)


# ==========================================
# 4. TRANSACTIONS & EVENTS (SDS 3.3.14 - 3.3.16)
# ==========================================

class Booking(models.Model):
    # SDS 3.3.14 BOOKING Array
    STATUS_CHOICES = (('Confirmed', 'Confirmed'), ('Checked-In', 'Checked-In'), ('Cancelled', 'Cancelled'))

    booking_id = models.AutoField(primary_key=True)
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    trip = models.ForeignKey(DailyTrip, on_delete=models.CASCADE)
    booking_time = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Confirmed')

class Incident(models.Model):
    # SDS 3.3.15 INCIDENTS Array
    STATUS_CHOICES = (('New', 'New'), ('Resolved', 'Resolved'))

    incident_id = models.AutoField(primary_key=True)
    reported_by = models.ForeignKey(User, on_delete=models.CASCADE)
    trip = models.ForeignKey(DailyTrip, on_delete=models.SET_NULL, null=True, blank=True)
    stop = models.ForeignKey(Stop, on_delete=models.SET_NULL, null=True, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    location_text = models.CharField(max_length=255, blank=True)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='New')
    reported_at = models.DateTimeField(auto_now_add=True)

class Notification(models.Model):
    # SDS 3.3.16 NOTIFICATIONS Array
    notif_id = models.AutoField(primary_key=True)
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    sent_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='sent_notifications')
    title = models.CharField(max_length=100)
    message = models.TextField()
    sent_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    # Optional context fields based on SDS
    related_trip = models.ForeignKey(DailyTrip, on_delete=models.SET_NULL, null=True, blank=True)
