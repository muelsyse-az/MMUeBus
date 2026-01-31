from django.contrib.auth.decorators import user_passes_test

def student_required(user):
    return user.is_authenticated and user.role == 'student'

def driver_required(user):
    return user.is_authenticated and user.role == 'driver'

def staff_required(user):
    # Shared by Coordinator and Admin
    return user.is_authenticated and user.role in ['coordinator', 'admin']
