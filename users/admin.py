from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User

class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ('Shuttle Role', {'fields': ('role', 'phone_number')}),
    )

admin.site.register(User, CustomUserAdmin)

# Register your models here.
