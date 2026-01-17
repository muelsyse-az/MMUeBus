from django.contrib import admin
from .models import Vehicle, Stop, Route, RouteStop, Schedule, Trip, Booking, Incident, Notification
# Register your models here.

# Use Inline to show Stops inside the Route page
class RouteStopInline(admin.TabularInline):
    model = RouteStop
    extra = 1

@admin.register(Route)
class RouteAdmin(admin.ModelAdmin):
    inlines = [RouteStopInline]

@admin.register(Trip)
class TripAdmin(admin.ModelAdmin):
    list_display = ('schedule', 'date', 'driver', 'status', 'available_seats')
    list_filter = ('status', 'date')

@admin.register(Incident)
class IncidentAdmin(admin.ModelAdmin):
    list_display = ('reporter', 'timestamp', 'is_resolved')
    list_filter = ('is_resolved',)

# Register the rest simply
admin.site.register(Vehicle)
admin.site.register(Stop)
admin.site.register(Schedule)
admin.site.register(Booking)
admin.site.register(Notification)