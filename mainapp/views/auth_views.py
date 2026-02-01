from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages
from mainapp.forms import StudentRegistrationForm, UserProfileForm
from django.contrib.auth.decorators import login_required

def root_route(request):
    """
    This view handles the Homepage (http://127.0.0.1:8000/).
    - Authenticated Users -> Redirect to their Dashboard.
    - Visitors -> Redirect to Login Page.
    """
    if request.user.is_authenticated:
        user = request.user
        if user.role == 'student':
            return redirect('student_dashboard')
        elif user.role == 'driver':
            return redirect('driver_dashboard')
        elif user.role in ['coordinator', 'admin']:
            # Currently sending staff to Admin panel
            return redirect('/admin/')
        else:
            # Fallback for weird cases
            return redirect('student_dashboard')
    else:
        # User is not logged in, send them to login
        return redirect('login')

def login_view(request):
    if request.method == 'POST':
        # Django's built-in form handles validation securely
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)

            if user is not None:
                login(request, user)

                # ROUTING LOGIC: Redirect based on Role
                if user.role == 'student':
                    return redirect('student_dashboard')
                elif user.role == 'driver':
                    return redirect('driver_dashboard')
                elif user.role in ['coordinator', 'admin']:
                    # For now, send staff to the Django Admin panel
                    return redirect('/admin/')
                else:
                    return redirect('student_dashboard') # Fallback
            else:
                messages.error(request, "Invalid username or password.")
        else:
            messages.error(request, "Invalid username or password.")

    # If GET request, show the login page
    return render(request, 'mainapp/auth/login.html')

def logout_view(request):
    logout(request)
    messages.info(request, "You have successfully logged out.")
    return redirect('login')

def register_student(request):
    if request.method == 'POST':
        form = StudentRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save() # The form forces role='student'
            login(request, user) # Log them in immediately
            messages.success(request, "Registration successful! Welcome.")
            return redirect('student_dashboard')
        else:
            messages.error(request, "Registration failed. Please correct the errors below.")
    else:
        form = StudentRegistrationForm()
    
    return render(request, 'mainapp/auth/register.html', {'form': form})

@login_required
def update_profile(request):
    if request.method == 'POST':
        form = UserProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Your profile has been updated successfully!")
            return redirect('update_profile') # Reload the page to show success
    else:
        # Pre-fill the form with the current user's data
        form = UserProfileForm(instance=request.user)

    return render(request, 'mainapp/auth/update_profile.html', {'form': form})