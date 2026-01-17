from django.db import models
from django.contrib.auth.models import AbstractUser

# Create your models here.
class User(AbstractUser):
    class Roles(models.TextChoices):
        STUDENT = 'STUDENT', 'Student'
        DRIVER = 'DRIVER', 'Driver'
        COORDINATOR = 'COORDINATOR', 'Coordinator'
        ADMIN = 'ADMIN', 'Admin'

    # --- FIX: These fields must be at the same indentation level as "class Roles" ---
    role = models.CharField(
        max_length=20,
        choices=Roles.choices,
        default=Roles.STUDENT,
    )
    
    phone_number = models.CharField(
        max_length=15,
        blank=True,
        null=True,
    )

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"