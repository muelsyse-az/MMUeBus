from django.db import models
from django.conf import settings # To reference our custom User

# --- ASSETS ---

class Vehicle(models.Model):
    plate_number = models.CharField(max_length=20, unique=True)
    capacity = models.IntegerField(default=30)
    # Status (Active, Maintenance, etc.)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"Bus {self.plate_number}"

class Stop(models.Model):
    name = models.CharField(max_length=100)
    # GPS Coordinates
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)

    def __str__(self):
        return self.name

# --- ROUTES & SCHEDULES ---

class Route(models.Model):
    name = models.CharField(max_length=100) # e.g., "Red Line (North Campus)"
    description = models.TextField(blank=True)
    stops = models.ManyToManyField(Stop, through='RouteStop')

    def __str__(self):
        return self.name

class RouteStop(models.Model):
    """Links a Route to a Stop with an order (1st stop, 2nd stop...)"""
    route = models.ForeignKey(Route, on_delete=models.CASCADE)
    stop = models.ForeignKey(Stop, on_delete=models.CASCADE)
    order = models.PositiveIntegerField()
    estimated_time_from_start = models.PositiveIntegerField(help_text="Minutes from route start")

    class Meta:
        ordering = ['order']

class Schedule(models.Model):
    """Defines the template: e.g., Red Line runs at 08:00 AM on Mondays"""
    route = models.ForeignKey(Route, on_delete=models.CASCADE)
    departure_time = models.TimeField()
    # Simplified: Assume daily for prototype, or add Day of Week field here
    
    def __str__(self):
        return f"{self.route.name} at {self.departure_time}"

# --- OPERATIONS (Real-time & Daily) ---

class Trip(models.Model):
    """A specific instance of a route happening on a specific day"""
    class Status(models.TextChoices):
        SCHEDULED = 'SCHEDULED', 'Scheduled'
        ONGOING = 'ONGOING', 'Ongoing'
        COMPLETED = 'COMPLETED', 'Completed'
        DELAYED = 'DELAYED', 'Delayed'
        CANCELLED = 'CANCELLED', 'Cancelled'

    schedule = models.ForeignKey(Schedule, on_delete=models.CASCADE)
    driver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, limit_choices_to={'role': 'DRIVER'})
    vehicle = models.ForeignKey(Vehicle, on_delete=models.SET_NULL, null=True)
    date = models.DateField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SCHEDULED)
    
    # Real-time tracking foundation
    current_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    current_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    def __str__(self):
        return f"{self.schedule.route.name} - {self.date}"

    @property
    def available_seats(self):
        reserved = self.booking_set.filter(status='CONFIRMED').count()
        if self.vehicle:
            return self.vehicle.capacity - reserved
        return 0

# --- USER INTERACTION ---

class Booking(models.Model):
    class Status(models.TextChoices):
        CONFIRMED = 'CONFIRMED', 'Confirmed'
        CANCELLED = 'CANCELLED', 'Cancelled'

    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, limit_choices_to={'role': 'STUDENT'})
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE)
    booking_time = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.CONFIRMED)

    def __str__(self):
        return f"{self.student.username} - {self.trip}"

class Incident(models.Model):
    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    trip = models.ForeignKey(Trip, on_delete=models.SET_NULL, null=True, blank=True)
    description = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    is_resolved = models.BooleanField(default=False)

    def __str__(self):
        return f"Incident by {self.reporter.username} on {self.timestamp.date()}"

class Notification(models.Model):
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)