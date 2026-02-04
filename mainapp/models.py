from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.utils import timezone

# 1. USERS
class CustomUserManager(BaseUserManager):
    def create_user(self, username, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(username=username, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        
        # --- FIX: Force the role to be 'admin' ---
        extra_fields.setdefault('role', 'admin') 

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(username, email, password, **extra_fields)

class User(AbstractUser):
    ROLE_CHOICES = (
        ('student', 'Student'),
        ('driver', 'Driver'),
        ('coordinator', 'Transport Coordinator'),
        ('admin', 'Admin'),
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    phone = models.CharField(max_length=15, blank=True, null=True)
    status = models.CharField(max_length=20, default='active')

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='student')
    objects = CustomUserManager()

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"

class Student(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, primary_key=True, related_name='student_profile')
    def __str__(self): return f"Student: {self.user.username}"

class Driver(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, primary_key=True, related_name='driver_profile')
    license_no = models.CharField(max_length=20)
    def __str__(self): return f"Driver: {self.user.username}"

class TransportCoordinator(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, primary_key=True, related_name='coordinator_profile')
    def __str__(self): return f"Coordinator: {self.user.username}"

class Admin(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, primary_key=True, related_name='admin_profile')
    def __str__(self): return f"Admin: {self.user.username}"

# 2. ASSETS
class Vehicle(models.Model):
    VEHICLE_TYPES = (('Bus', 'Bus'), ('Van', 'Van'))
    vehicle_id = models.AutoField(primary_key=True)
    plate_no = models.CharField(max_length=15, unique=True)
    capacity = models.IntegerField()
    type = models.CharField(max_length=20, choices=VEHICLE_TYPES)
    def __str__(self): return f"{self.plate_no} ({self.type})"

class Stop(models.Model):
    stop_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    def __str__(self): return self.name

class Route(models.Model):
    route_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=50)
    description = models.TextField(blank=True, null=True)
    stops = models.ManyToManyField(Stop, through='RouteStop')
    def __str__(self): return self.name

class RouteStop(models.Model):
    route = models.ForeignKey(Route, on_delete=models.CASCADE)
    stop = models.ForeignKey(Stop, on_delete=models.CASCADE)
    sequence_no = models.PositiveIntegerField()
    est_minutes = models.IntegerField(help_text="Estimated minutes from start")
    class Meta:
        ordering = ['sequence_no']
        unique_together = ('route', 'sequence_no')

# 3. OPERATIONS
class Schedule(models.Model):
    schedule_id = models.AutoField(primary_key=True)
    route = models.ForeignKey(Route, on_delete=models.CASCADE)
    days_of_week = models.CharField(max_length=50) # "Mon,Tue,Wed"
    start_time = models.TimeField()
    end_time = models.TimeField()
    frequency_min = models.IntegerField()
    valid_from = models.DateField()
    valid_to = models.DateField()
    
    # ADDED: Default assignment to make Coordinator's life easier
    default_driver = models.ForeignKey(Driver, on_delete=models.SET_NULL, null=True, blank=True)
    default_vehicle = models.ForeignKey(Vehicle, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self): return f"{self.route.name} ({self.start_time})"

class DailyTrip(models.Model):
    STATUS_CHOICES = (
        ('Scheduled', 'Scheduled'),
        ('In-Progress', 'In-Progress'),
        ('Delayed', 'Delayed'),
        ('Completed', 'Completed'),
        ('Cancelled', 'Cancelled'),
    )
    trip_id = models.AutoField(primary_key=True)
    schedule = models.ForeignKey(Schedule, on_delete=models.CASCADE)
    trip_date = models.DateField()
    planned_departure = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Scheduled')

    def __str__(self): return f"Trip {self.trip_id} - {self.trip_date}"

class DriverAssignment(models.Model):
    assignment_id = models.AutoField(primary_key=True)
    trip = models.ForeignKey(DailyTrip, on_delete=models.CASCADE)
    driver = models.ForeignKey(Driver, on_delete=models.CASCADE)
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE)
    assignment_date = models.DateField(auto_now_add=True)

class CurrentLocation(models.Model):
    # UPDATED: Added related_name='location'
    trip = models.OneToOneField(DailyTrip, on_delete=models.CASCADE, primary_key=True, related_name='location')
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    last_update = models.DateTimeField(auto_now=True)

# 4. EVENTS
class Booking(models.Model):
    STATUS_CHOICES = (('Confirmed', 'Confirmed'), ('Checked-In', 'Checked-In'), ('Cancelled', 'Cancelled'))
    booking_id = models.AutoField(primary_key=True)
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    trip = models.ForeignKey(DailyTrip, on_delete=models.CASCADE)
    booking_time = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Confirmed')

class Incident(models.Model):
    STATUS_CHOICES = (('New', 'New'), ('Resolved', 'Resolved'))
    incident_id = models.AutoField(primary_key=True)
    reported_by = models.ForeignKey(User, on_delete=models.CASCADE)
    trip = models.ForeignKey(DailyTrip, on_delete=models.SET_NULL, null=True, blank=True)
    stop = models.ForeignKey(Stop, on_delete=models.SET_NULL, null=True, blank=True)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='New')
    reported_at = models.DateTimeField(auto_now_add=True)

class Notification(models.Model):
    notif_id = models.AutoField(primary_key=True)
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    sent_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='sent_notifications')
    title = models.CharField(max_length=100)
    message = models.TextField()
    sent_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)