from datetime import datetime, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from mainapp.decorators import staff_required, coordinator_required, admin_required
from mainapp.models import Route, Stop, Schedule, RouteStop, DailyTrip, Incident, Notification, User, Booking, Student, Vehicle, Driver, TransportCoordinator
from mainapp.forms import RouteForm, StopForm, ScheduleForm, RouteStopForm, NotificationForm, ManualBookingForm, VehicleCapacityForm, UserManagementForm, AdminUserCreationForm
from django.utils import timezone
from django.db.models import Q

@login_required
@user_passes_test(staff_required)
def coordinator_dashboard(request):
    """
    The main landing page for Transport Coordinators.
    Shows quick stats and links to management tools.
    """
    # Optional: Gather some quick stats for the dashboard
    total_routes = Route.objects.count()
    active_trips = DailyTrip.objects.filter(status='In-Progress').count()
    pending_incidents = Incident.objects.filter(status='New').count()

    context = {
        'total_routes': total_routes,
        'active_trips': active_trips,
        'pending_incidents': pending_incidents
    }
    return render(request, 'mainapp/coordinator/dashboard.html', context)

# ==========================================
# 1. ROUTE MANAGEMENT
# ==========================================

@login_required
@user_passes_test(staff_required)
def manage_routes(request):
    """List all routes"""
    routes = Route.objects.all()
    return render(request, 'mainapp/coordinator/manage_routes.html', {'routes': routes})

@login_required
@user_passes_test(staff_required)
def add_route(request):
    """Create a new route container"""
    if request.method == 'POST':
        form = RouteForm(request.POST)
        if form.is_valid():
            route = form.save()
            messages.success(request, f"Route '{route.name}' created! Now add stops.")
            return redirect('manage_stops', route_id=route.route_id)
    else:
        form = RouteForm()
    return render(request, 'mainapp/coordinator/route_form.html', {'form': form, 'title': 'Add Route'})

@login_required
@user_passes_test(staff_required)
def delete_route(request, route_id):
    route = get_object_or_404(Route, route_id=route_id)
    route.delete()
    messages.success(request, "Route deleted successfully.")
    return redirect('manage_routes')

# ==========================================
# 2. STOP MANAGEMENT (Linking Stops to Routes)
# ==========================================

@login_required
@user_passes_test(staff_required)
def manage_stops(request, route_id):
    """View to add/remove stops from a specific route"""
    route = get_object_or_404(Route, route_id=route_id)
    current_stops = RouteStop.objects.filter(route=route).order_by('sequence_no')
    
    if request.method == 'POST':
        # This handles adding an EXISTING stop to the route
        form = RouteStopForm(request.POST)
        if form.is_valid():
            route_stop = form.save(commit=False)
            route_stop.route = route
            try:
                route_stop.save()
                messages.success(request, "Stop added to route.")
                return redirect('manage_stops', route_id=route.route_id)
            except:
                messages.error(request, "Error: Check if sequence number implies duplication.")
    else:
        form = RouteStopForm()

    return render(request, 'mainapp/coordinator/manage_stops.html', {
        'route': route, 
        'current_stops': current_stops, 
        'form': form
    })

@login_required
@user_passes_test(staff_required)
def delete_route_stop(request, route_stop_id):
    """Remove a stop from a route (does not delete the Stop itself)"""
    rs = get_object_or_404(RouteStop, id=route_stop_id)
    route_id = rs.route.route_id
    rs.delete()
    messages.success(request, "Stop removed from route.")
    return redirect('manage_stops', route_id=route_id)

@login_required
@user_passes_test(staff_required)
def add_physical_stop(request):
    """Quickly create a new physical Stop location"""
    if request.method == 'POST':
        form = StopForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Physical Stop Location Created.")
            # Redirect back to previous page if possible, else routes
            return redirect(request.META.get('HTTP_REFERER', 'manage_routes'))
    return redirect('manage_routes')

# ==========================================
# 3. SCHEDULE MANAGEMENT
# ==========================================

@login_required
@user_passes_test(staff_required)
def manage_schedules(request):
    schedules = Schedule.objects.all().order_by('route__name')
    return render(request, 'mainapp/coordinator/manage_schedules.html', {'schedules': schedules})

@login_required
@user_passes_test(staff_required)
def add_schedule(request):
    if request.method == 'POST':
        form = ScheduleForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Schedule published successfully.")
            return redirect('manage_schedules')
    else:
        form = ScheduleForm()
    return render(request, 'mainapp/coordinator/schedule_form.html', {'form': form, 'title': 'Add Schedule'})

@login_required
@user_passes_test(coordinator_required)
def edit_schedule(request, schedule_id=None):
    """
    Handles creating and editing schedules.
    BUG FIX 5: If the schedule changes, delete future 'Scheduled' trips 
    to prevent "Ghost Trips" (desync between schedule and active trips).
    """
    if schedule_id:
        schedule = get_object_or_404(Schedule, schedule_id=schedule_id)
        heading = "Edit Schedule"
    else:
        schedule = None
        heading = "Create New Schedule"
    
    if request.method == 'POST':
        form = ScheduleForm(request.POST, instance=schedule)
        if form.is_valid():
            # --- BUG 5 FIX START ---
            # Check if this is an EDIT (not a new create) and if data changed
            if schedule_id and form.has_changed():
                # Fields that invalidates existing trips if changed
                critical_fields = ['start_time', 'end_time', 'days_of_week', 'route']
                
                if any(field in form.changed_data for field in critical_fields):
                    # Find and delete future trips that are just 'Scheduled'
                    # (We don't touch 'In-Progress' or history)
                    future_trips = DailyTrip.objects.filter(
                        schedule=schedule,
                        status='Scheduled',
                        trip_date__gte=timezone.now().date()
                    )
                    count = future_trips.count()
                    future_trips.delete()
                    
                    if count > 0:
                        messages.warning(request, f"Schedule changed: {count} future trips were removed to prevent errors. Please use 'Generate Trips' to rebuild them.")
            # --- BUG 5 FIX END ---

            form.save()
            
            if schedule_id:
                messages.success(request, "Schedule updated successfully.")
            else:
                messages.success(request, "New schedule created successfully.")
            return redirect('manage_schedules')
    else:
        form = ScheduleForm(instance=schedule)
        
    return render(request, 'mainapp/coordinator/schedule_form.html', {
        'form': form, 
        'schedule': schedule,
        'heading': heading
    })

@login_required
@user_passes_test(staff_required)
def delete_schedule(request, schedule_id):
    schedule = get_object_or_404(Schedule, schedule_id=schedule_id)
    schedule.delete()
    messages.success(request, "Schedule deleted.")
    return redirect('manage_schedules')

@login_required
@user_passes_test(staff_required)
def view_incidents(request):
    """
    Displays a list of all incidents, sorted by newest first.
    """
    # Order by 'status' (New first) then by 'reported_at' (Newest first)
    incidents = Incident.objects.all().order_by('status', '-reported_at')
    
    return render(request, 'mainapp/coordinator/view_incidents.html', {'incidents': incidents})

@login_required
@user_passes_test(staff_required)
def resolve_incident(request, incident_id):
    """
    Marks an incident as 'Resolved'.
    """
    incident = get_object_or_404(Incident, incident_id=incident_id)
    
    if incident.status != 'Resolved':
        incident.status = 'Resolved'
        incident.save()
        messages.success(request, f"Incident #{incident.incident_id} has been marked as Resolved.")
    
    # Redirect back to the list
    return redirect('view_incidents')

@login_required
@user_passes_test(staff_required)
def send_notification(request):
    if request.method == 'POST':
        form = NotificationForm(request.POST)
        if form.is_valid():
            title = form.cleaned_data['title']
            message = form.cleaned_data['message']
            target_type = form.cleaned_data['target_type']
            specific_user = form.cleaned_data['specific_user']
            
            recipients = []

            # 1. Determine who gets the message
            if target_type == 'specific':
                if specific_user:
                    recipients = [specific_user]
                else:
                    messages.error(request, "Please select a user.")
                    return render(request, 'mainapp/coordinator/send_notification.html', {'form': form})
            else:
                # Filter by role (student, driver, coordinator)
                recipients = User.objects.filter(role=target_type, is_active=True)

            # 2. Bulk Create Notifications
            # (We loop to create a unique record for each user so they can track read/unread status individually)
            count = 0
            for user in recipients:
                Notification.objects.create(
                    recipient=user,
                    sent_by=request.user,
                    title=title,
                    message=message
                )
                count += 1
            
            messages.success(request, f"Notification sent to {count} users.")
            return redirect('coordinator_dashboard')
    else:
        form = NotificationForm()

    return render(request, 'mainapp/coordinator/send_notification.html', {'form': form})

@login_required
def manage_trip_passengers(request, trip_id):
    trip = get_object_or_404(DailyTrip, trip_id=trip_id)
    
    # PERMISSION CHECK
    is_coordinator = request.user.role == 'coordinator' or request.user.role == 'admin'
    is_assigned_driver = False
    
    if request.user.role == 'driver':
        # Check if this trip belongs to this driver
        assignment = trip.driverassignment_set.first()
        if assignment and assignment.driver.user == request.user:
            is_assigned_driver = True
    
    # If neither, kick them out
    if not (is_coordinator or is_assigned_driver):
        messages.error(request, "Access Denied. You cannot manage this trip.")
        return redirect('root')

    # HANDLE ACTIONS
    if request.method == 'POST':
        
        # 1. DELETE BOOKING
        if 'delete_booking' in request.POST:
            booking_id = request.POST.get('booking_id')
            Booking.objects.filter(booking_id=booking_id).delete()
            messages.success(request, "Passenger removed from manifest.")
            return redirect('manage_trip_passengers', trip_id=trip.trip_id)

        # 2. ADD BOOKING MANUALLY
        elif 'add_passenger' in request.POST:
            form = ManualBookingForm(request.POST)
            if form.is_valid():
                username = form.cleaned_data['student_username']
                try:
                    user = User.objects.get(username=username, role='student')
                    # Check if already booked
                    if Booking.objects.filter(trip=trip, student=user.student_profile).exists():
                        messages.warning(request, "Student is already on the list.")
                    else:
                        Booking.objects.create(trip=trip, student=user.student_profile, status='Confirmed')
                        messages.success(request, f"Added {username} to trip.")
                        return redirect('manage_trip_passengers', trip_id=trip.trip_id)
                except User.DoesNotExist:
                    messages.error(request, "Student username not found.")

        # 3. UPDATE VEHICLE CAPACITY
        elif 'update_capacity' in request.POST:
            # We need to find the vehicle assigned to this trip
            assignment = trip.driverassignment_set.first()
            if assignment:
                vehicle = assignment.vehicle
                cap_form = VehicleCapacityForm(request.POST, instance=vehicle)
                if cap_form.is_valid():
                    cap_form.save()
                    messages.success(request, f"Vehicle capacity updated to {vehicle.capacity}.")
                    return redirect('manage_trip_passengers', trip_id=trip.trip_id)
            else:
                messages.error(request, "No vehicle assigned to this trip yet.")

    # PREPARE DATA FOR TEMPLATE
    bookings = Booking.objects.filter(trip=trip).select_related('student__user')
    assignment = trip.driverassignment_set.first()
    current_vehicle = assignment.vehicle if assignment else None
    
    # Calculate Seats
    capacity = current_vehicle.capacity if current_vehicle else 0
    booked_count = bookings.count()
    available_seats = capacity - booked_count

    context = {
        'trip': trip,
        'bookings': bookings,
        'vehicle': current_vehicle,
        'capacity': capacity,
        'booked_count': booked_count,
        'available_seats': available_seats,
        'booking_form': ManualBookingForm(),
        'capacity_form': VehicleCapacityForm(instance=current_vehicle) if current_vehicle else None
    }
    
    return render(request, 'mainapp/coordinator/manage_passengers.html', context)

@login_required
@user_passes_test(coordinator_required)
def view_all_trips(request):
    """
    Shows a master list of trips for a specific date (default: today).
    Allows the Coordinator to pick a trip to manage.
    """
    # 1. Get Date Filter (Default to Today)
    date_str = request.GET.get('date')
    if date_str:
        selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    else:
        selected_date = timezone.now().date()

    # 2. Fetch Trips
    trips = DailyTrip.objects.filter(trip_date=selected_date).order_by('planned_departure')
    
    context = {
        'trips': trips,
        'selected_date': selected_date,
        'today': timezone.now().date()
    }
    return render(request, 'mainapp/coordinator/trip_list.html', context)

@login_required
def manage_trip_passengers(request, trip_id):
    """
    Unified view for Drivers OR Coordinators to manage a trip's manifest.
    """
    trip = get_object_or_404(DailyTrip, trip_id=trip_id)
    
    # PERMISSION CHECK
    is_coordinator = request.user.role in ['coordinator', 'admin']
    is_assigned_driver = False
    
    if request.user.role == 'driver':
        assignment = trip.driverassignment_set.first()
        if assignment and assignment.driver.user == request.user:
            is_assigned_driver = True
            
    if not (is_coordinator or is_assigned_driver):
        messages.error(request, "Access Denied.")
        return redirect('root')

    # --- LOGIC: Handle Add/Remove/Capacity ---
    if request.method == 'POST':
        # 1. DELETE BOOKING
        if 'delete_booking' in request.POST:
            booking_id = request.POST.get('booking_id')
            Booking.objects.filter(booking_id=booking_id).delete()
            messages.success(request, "Passenger removed.")
            return redirect('manage_trip_passengers', trip_id=trip.trip_id)

        # 2. ADD MANUAL PASSENGER
        elif 'add_passenger' in request.POST:
            form = ManualBookingForm(request.POST)
            if form.is_valid():
                username = form.cleaned_data['student_username']
                try:
                    user = User.objects.get(username=username, role='student')
                    if Booking.objects.filter(trip=trip, student=user.student_profile).exists():
                        messages.warning(request, "Student already on manifest.")
                    else:
                        Booking.objects.create(trip=trip, student=user.student_profile, status='Confirmed')
                        messages.success(request, f"Added {username}.")
                        return redirect('manage_trip_passengers', trip_id=trip.trip_id)
                except User.DoesNotExist:
                    messages.error(request, "Student username not found.")

        # 3. UPDATE CAPACITY
        elif 'update_capacity' in request.POST:
            assignment = trip.driverassignment_set.first()
            if assignment:
                v_form = VehicleCapacityForm(request.POST, instance=assignment.vehicle)
                if v_form.is_valid():
                    v_form.save()
                    messages.success(request, "Vehicle capacity updated.")
                    return redirect('manage_trip_passengers', trip_id=trip.trip_id)

    # PREPARE CONTEXT
    bookings = Booking.objects.filter(trip=trip).select_related('student__user')
    assignment = trip.driverassignment_set.first()
    vehicle = assignment.vehicle if assignment else None
    
    context = {
        'trip': trip,
        'bookings': bookings,
        'vehicle': vehicle,
        'booked_count': bookings.count(),
        'booking_form': ManualBookingForm(),
        'capacity_form': VehicleCapacityForm(instance=vehicle) if vehicle else None
    }
    return render(request, 'mainapp/coordinator/manage_passengers.html', context)

@login_required
@user_passes_test(admin_required)
def manage_users_list(request):
    """
    Combined View: Lists users AND handles new user creation.
    Uses get_or_create to prevent UniqueConstraint errors.
    """
    # --- 1. HANDLE USER CREATION (POST) ---
    if request.method == 'POST' and 'create_user' in request.POST:
        creation_form = AdminUserCreationForm(request.POST)
        if creation_form.is_valid():
            # Create User
            user = creation_form.save(commit=False)
            user.set_password(creation_form.cleaned_data['password'])
            user.save()
            messages.success(request, f"User {user.username} created successfully.")
            return redirect('manage_users_list')
        else:
            messages.error(request, "Error creating user. Please check the form.")
    else:
        creation_form = AdminUserCreationForm()

    # --- 2. HANDLE LIST & SEARCH (GET) ---
    query = request.GET.get('q', '')
    if query:
        users = User.objects.filter(
            Q(username__icontains=query) | 
            Q(email__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query)
        ).order_by('role', 'username')
    else:
        users = User.objects.all().order_by('role', 'username')

    context = {
        'users': users,
        'query': query,
        'creation_form': creation_form
    }
    return render(request, 'mainapp/coordinator/manage_users.html', context)

@login_required
@user_passes_test(admin_required)
def edit_user(request, user_id):
    """
    Allows Admin to edit a user's role and details.
    """
    user_to_edit = get_object_or_404(User, id=user_id)
    
    if request.method == 'POST':
        form = UserManagementForm(request.POST, instance=user_to_edit)
        if form.is_valid():
            form.save()
            messages.success(request, f"User {user_to_edit.username} updated successfully.")
            return redirect('manage_users_list')
    else:
        form = UserManagementForm(instance=user_to_edit)

    return render(request, 'mainapp/coordinator/edit_user.html', {'form': form, 'target_user': user_to_edit})

@login_required
@user_passes_test(admin_required)
def delete_user(request, user_id):
    """
    Permanently deletes a user.
    """
    user_to_delete = get_object_or_404(User, id=user_id)
    
    # Prevent Admin from deleting themselves
    if user_to_delete == request.user:
        messages.error(request, "You cannot delete your own account!")
        return redirect('manage_users_list')

    username = user_to_delete.username
    user_to_delete.delete()
    messages.success(request, f"User '{username}' has been deleted.")
    return redirect('manage_users_list')

# --- 1. ADMIN CREATE USER ---
@login_required
@user_passes_test(admin_required)
def create_user(request):
    if request.method == 'POST':
        form = AdminUserCreationForm(request.POST)
        if form.is_valid():
            # 1. Create User
            user = form.save(commit=False)
            user.set_password(form.cleaned_data['password'])
            user.save()

            messages.success(request, f"User {user.username} created successfully as {role}.")
            return redirect('manage_users_list')
    else:
        form = AdminUserCreationForm()

    return render(request, 'mainapp/coordinator/create_user.html', {'form': form})


# --- 2. EDIT SCHEDULE (Assign Driver) ---
@login_required
@user_passes_test(coordinator_required)
def edit_schedule(request, schedule_id=None):  # <--- Allow ID to be None
    """
    Handles BOTH creating a new schedule and editing an existing one.
    If schedule_id is None, we are in 'Create Mode'.
    """
    if schedule_id:
        # Edit Mode: Get existing object
        schedule = get_object_or_404(Schedule, schedule_id=schedule_id)
        heading = "Edit Schedule"
    else:
        # Create Mode: No object yet
        schedule = None
        heading = "Create New Schedule"
    
    if request.method == 'POST':
        # Pass 'instance=schedule' so Django knows if we are updating or creating
        form = ScheduleForm(request.POST, instance=schedule)
        if form.is_valid():
            form.save()
            if schedule_id:
                messages.success(request, "Schedule updated successfully.")
            else:
                messages.success(request, "New schedule created successfully.")
            return redirect('manage_schedules')
    else:
        form = ScheduleForm(instance=schedule)
        
    return render(request, 'mainapp/coordinator/schedule_form.html', {
        'form': form, 
        'schedule': schedule,
        'heading': heading
    })

@login_required
@user_passes_test(staff_required)
def delete_schedule(request, schedule_id):
    schedule = get_object_or_404(Schedule, schedule_id=schedule_id)
    schedule.delete()
    messages.success(request, "Schedule deleted.")
    return redirect('manage_schedules')

# Map View
def global_map_view(request):
    return render(request, 'mainapp/common/map_view.html')

@login_required
@user_passes_test(coordinator_required)
def generate_future_trips(request):
    """
    BUG 5 FIX: Automatically generates DailyTrip records for the next 30 days
    based on active Schedules.
    """
    schedules = Schedule.objects.all()
    today = timezone.now().date()
    # Look ahead 7 days
    days_to_generate = 7
    
    # Map Python weekday integers (0=Mon) to your DB string format
    weekday_map = {0: 'Mon', 1: 'Tue', 2: 'Wed', 3: 'Thu', 4: 'Fri', 5: 'Sat', 6: 'Sun'}
    
    trips_created = 0
    
    for i in range(days_to_generate):
        target_date = today + timedelta(days=i)
        day_str = weekday_map[target_date.weekday()] # e.g., "Mon"
        
        for sched in schedules:
            # 1. Check if Schedule runs on this day (e.g. "Mon,Tue" contains "Mon")
            if day_str in sched.days_of_week:
                
                # 2. Check Valid Date Range
                if sched.valid_from <= target_date <= sched.valid_to:
                    # START LOOPING FROM START_TIME
                    current_time = datetime.combine(target_date, sched.start_time)
                    end_datetime = datetime.combine(target_date, sched.end_time)
                    
                    if sched.end_time < sched.start_time:
                        end_datetime += timedelta(days=1)

                    while current_time < end_datetime:
                        # Create the trip
                        trip, created = DailyTrip.objects.get_or_create(
                            schedule=sched,
                            trip_date=current_time.date(),
                            planned_departure=current_time, # Use the loop variable
                            defaults={'status': 'Scheduled'}
                        )

                    # 4. Auto-Assign Driver/Vehicle if defaults exist
                    if created:
                        trips_created += 1
                        if sched.default_driver and sched.default_vehicle:
                            DriverAssignment.objects.create(
                                trip=trip,
                                driver=sched.default_driver,
                                vehicle=sched.default_vehicle
                            )

                    current_time += timedelta(minutes=sched.frequency_min)

    messages.success(request, f"Generation Complete: {trips_created} new trips created for the next 30 days.")
    return redirect('coordinator_dashboard')