from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.contrib import messages
from mainapp.forms import StudentRegistrationForm, UserProfileForm
from django.contrib.auth.decorators import login_required
from mainapp.models import Notification

def root_route(request):
    """
    This view acts as the central traffic controller for the application's homepage, automatically directing users to their appropriate dashboard based on their authentication status and assigned role.
    
    It checks if the request.user is authenticated; if so, it inspects the 'role' attribute (student, driver, coordinator, or admin) to determine the correct redirect target, otherwise, it sends the visitor to the login page.
    """
    if request.user.is_authenticated:
        user = request.user
        if user.role == 'student':
            return redirect('student_dashboard')
        elif user.role == 'driver':
            return redirect('driver_dashboard')
        elif user.role in ['coordinator', 'admin']:
            return redirect('coordinator_dashboard')
        else:
            return redirect('student_dashboard')
    else:
        return redirect('login')

def login_view(request):
    """
    This view handles the secure authentication process, validating user credentials and establishing a session before redirecting them to their role-specific dashboard.
    
    It processes the standard Django AuthenticationForm via POST, validates the username and password using the authenticate() function, logs the user in if successful, and executes the same role-based routing logic found in the root route.
    """
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)

            if user is not None:
                login(request, user)

                if user.role == 'student':
                    return redirect('student_dashboard')
                elif user.role == 'driver':
                    return redirect('driver_dashboard')
                elif user.role == 'coordinator':
                    return redirect('coordinator_dashboard')
                elif user.role == 'admin':
                    return redirect('coordinator_dashboard')
                else:
                    return redirect('student_dashboard')
            else:
                messages.error(request, "Invalid username or password.")
        else:
            messages.error(request, "Invalid username or password.")

    return render(request, 'mainapp/auth/login.html')

def register_student(request):
    """
    This view manages the onboarding of new students, allowing them to create an account and immediately access the platform without requiring a secondary login step.
    
    It processes the StudentRegistrationForm (which enforces the 'student' role), saves the new user object upon validation, and immediately logs the user in using the login() function before redirecting to the dashboard.
    """
    if request.method == 'POST':
        form = StudentRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Registration successful! Welcome.")
            return redirect('student_dashboard')
        else:
            messages.error(request, "Registration failed. Please correct the errors below.")
    else:
        form = StudentRegistrationForm()
    
    return render(request, 'mainapp/auth/register.html', {'form': form})

def logout_view(request):
    """
    This view handles the termination of a user's session, ensuring they are securely disconnected from the system before being returned to the public login screen.
    
    It calls Django's built-in logout() function to clear session data and adds a 'successfully logged out' message to the request context.
    """
    logout(request)
    messages.info(request, "You have successfully logged out.")
    return redirect('login')

@login_required
def update_profile(request):
    """
    This view allows authenticated users to modify their personal account details, such as their email address or display name.
    
    It initializes the UserProfileForm with the current user instance (pre-filling existing data), validates any POSTed changes, and saves the updated information back to the database.
    """
    if request.method == 'POST':
        form = UserProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Your profile has been updated successfully!")
            return redirect('update_profile')
    else:
        form = UserProfileForm(instance=request.user)

    return render(request, 'mainapp/auth/update_profile.html', {'form': form})

@login_required
def change_password(request):
    """
    This view provides a secure interface for users to reset their passwords while ensuring they remain logged in after the credentials change.
    
    It uses Django's PasswordChangeForm to validate the old and new passwords, saves the change, and critically calls update_session_auth_hash() to prevent the user's current session from being invalidated by the security update.
    """
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, "Your password was successfully updated!")
            return redirect('update_profile')
        else:
            messages.error(request, "Please correct the error below.")
    else:
        form = PasswordChangeForm(request.user)
    
    return render(request, 'mainapp/auth/change_password.html', {'form': form})

@login_required
def notification_inbox(request):
    """
    This view displays a chronological list of system alerts and messages specifically targeted at the currently logged-in user.
    
    It queries the Notification model for records where the 'recipient' field matches the current request.user and sorts them by the 'sent_at' timestamp in descending order.
    """
    notifs = Notification.objects.filter(recipient=request.user).order_by('-sent_at')
    
    return render(request, 'mainapp/common/notifications.html', {'notifications': notifs})

@login_required
def mark_notification_read(request, notif_id):
    """
    This view performs a specific update action on a single notification, marking it as read to help the user manage their unread message count.
    
    It retrieves the specific Notification object using get_object_or_404 (ensuring it belongs to the current user for security), sets the 'is_read' boolean to True, and redirects back to the inbox.
    """
    notif = get_object_or_404(Notification, notif_id=notif_id, recipient=request.user)
    notif.is_read = True
    notif.save()
    return redirect('notification_inbox')