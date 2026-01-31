from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import User, Student, Driver, TransportCoordinator, Admin

@receiver(post_save, sender=User)
def manage_user_profile(sender, instance, created, **kwargs):
    """
    Check the user's role on EVERY save.
    If they have a role but no profile, create it.
    """
    # 1. Handle STUDENT
    if instance.role == 'student':
        # If the profile doesn't exist yet, create it
        if not hasattr(instance, 'student_profile'):
            Student.objects.create(user=instance)

    # 2. Handle DRIVER
    elif instance.role == 'driver':
        if not hasattr(instance, 'driver_profile'):
            Driver.objects.create(user=instance, license_no="PENDING")

    # 3. Handle COORDINATOR
    elif instance.role == 'coordinator':
        if not hasattr(instance, 'coordinator_profile'):
            TransportCoordinator.objects.create(user=instance)

    # 4. Handle ADMIN
    elif instance.role == 'admin':
        if not hasattr(instance, 'admin_profile'):
            Admin.objects.create(user=instance)
