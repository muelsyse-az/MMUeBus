from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages

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
