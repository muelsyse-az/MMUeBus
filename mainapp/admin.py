from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Student, Driver, TransportCoordinator, Vehicle, Route, Stop, Schedule, DailyTrip, Booking, DriverAssignment

# Register the Custom User Model
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ('Custom Fields', {'fields': ('role', 'phone', 'status')}),
    )
admin.site.register(User, CustomUserAdmin)

# Register other models so they appear in the Admin Panel
admin.site.register(Student)
admin.site.register(Driver)
admin.site.register(TransportCoordinator)
admin.site.register(Vehicle)
admin.site.register(Route)
admin.site.register(Stop)
admin.site.register(Schedule)
admin.site.register(DailyTrip)
admin.site.register(Booking)
admin.site.register(DriverAssignment)
