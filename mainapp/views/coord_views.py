# mainapp/views/coord_views.py

from datetime import datetime, timedelta, date
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from mainapp.decorators import staff_required, coordinator_required, admin_required
from mainapp.models import Route, Stop, Schedule, RouteStop, DailyTrip, Incident, Notification, User, Booking, DriverAssignment, Vehicle
from mainapp.forms import RouteForm, StopForm, ScheduleForm, RouteStopForm, NotificationForm, ManualBookingForm, VehicleCapacityForm, UserManagementForm, AdminUserCreationForm, VehicleForm, DriverAssignmentForm
from django.utils import timezone
from django.db.models import Q

# ==========================================
# HELPER: TRIP GENERATION
# ==========================================
def _generate_trips_for_schedule(schedule, days_ahead=30):
    """
    Private helper to generate DailyTrip records for a specific schedule
    for the next 'days_ahead' days.
    """
    today = timezone.now().date()
    weekday_map = {0: 'Mon', 1: 'Tue', 2: 'Wed', 3: 'Thu', 4: 'Fri', 5: 'Sat', 6: 'Sun'}
    trips_created_count = 0

    for i in range(days_ahead):
        target_date = today + timedelta(days=i)
        day_str = weekday_map[target_date.weekday()] # e.g., "Mon"

        # 1. Check if Schedule runs on this day
        if day_str in schedule.days_of_week:
            
            # 2. Check Valid Date Range
            if schedule.valid_from <= target_date <= schedule.valid_to:
                
                # 3. Calculate Time Slots
                current_time = datetime.combine(target_date, schedule.start_time)
                end_datetime = datetime.combine(target_date, schedule.end_time)
                
                # Handle overnight schedules
                if schedule.end_time < schedule.start_time:
                    end_datetime += timedelta(days=1)

                while current_time < end_datetime:
                    # 4. Create Trip (if not exists)
                    trip, created = DailyTrip.objects.get_or_create(
                        schedule=schedule,
                        trip_date=current_time.date(),
                        planned_departure=timezone.make_aware(current_time),
                        defaults={'status': 'Scheduled'}
                    )

                    # 5. Assign Driver & Vehicle
                    if created:
                        trips_created_count += 1
                        if schedule.default_driver and schedule.default_vehicle:
                            DriverAssignment.objects.get_or_create(
                                trip=trip,
                                driver=schedule.default_driver,
                                vehicle=schedule.default_vehicle
                            )

                    # Increment time for next slot
                    current_time += timedelta(minutes=schedule.frequency_min)
    
    return trips_created_count

# ==========================================
# DASHBOARD
# ==========================================

@login_required
@user_passes_test(staff_required)
def coordinator_dashboard(request):
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
    routes = Route.objects.all()
    stop_form = StopForm()
    return render(request, 'mainapp/coordinator/manage_routes.html', {'routes': routes, 'stop_form': stop_form})

@login_required
@user_passes_test(staff_required)
def add_route(request):
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
# 2. STOP MANAGEMENT
# ==========================================

@login_required
@user_passes_test(staff_required)
def manage_stops(request, route_id):
    route = get_object_or_404(Route, route_id=route_id)
    current_stops = RouteStop.objects.filter(route=route).order_by('sequence_no')
    
    if request.method == 'POST':
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
    rs = get_object_or_404(RouteStop, id=route_stop_id)
    route_id = rs.route.route_id
    rs.delete()
    messages.success(request, "Stop removed from route.")
    return redirect('manage_stops', route_id=route_id)

@login_required
@user_passes_test(staff_required)
def add_physical_stop(request):
    if request.method == 'POST':
        form = StopForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Physical Stop Location Created.")
            return redirect(request.META.get('HTTP_REFERER', 'manage_routes'))
    return redirect('manage_routes')

# ==========================================
# 3. SCHEDULE MANAGEMENT (Auto-Generates Trips)
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
            schedule = form.save()
            # AUTO-GENERATE TRIPS IMMEDIATELY
            count = _generate_trips_for_schedule(schedule)
            messages.success(request, f"Schedule published. {count} upcoming trips generated automatically.")
            return redirect('manage_schedules')
    else:
        form = ScheduleForm()
    return render(request, 'mainapp/coordinator/schedule_form.html', {'form': form, 'title': 'Add Schedule'})

@login_required
@user_passes_test(coordinator_required)
def edit_schedule(request, schedule_id=None):
    if schedule_id:
        schedule = get_object_or_404(Schedule, schedule_id=schedule_id)
        heading = "Edit Schedule"
    else:
        schedule = None
        heading = "Create New Schedule"
    
    if request.method == 'POST':
        form = ScheduleForm(request.POST, instance=schedule)
        if form.is_valid():
            # Handle Cleanup of Old Trips if Schedule Changed
            if schedule_id and form.has_changed():
                critical_fields = ['start_time', 'end_time', 'days_of_week', 'route']
                if any(field in form.changed_data for field in critical_fields):
                    # Delete future 'Scheduled' trips to prevent ghosts
                    DailyTrip.objects.filter(
                        schedule=schedule,
                        status='Scheduled',
                        trip_date__gte=timezone.now().date()
                    ).delete()
                    messages.info(request, "Schedule changed: Old future trips were removed.")

            # Save the Schedule
            schedule = form.save()
            
            # REGENERATE TRIPS IMMEDIATELY
            count = _generate_trips_for_schedule(schedule)
            
            if schedule_id:
                messages.success(request, f"Schedule updated. {count} trips regenerated.")
            else:
                messages.success(request, f"New schedule created. {count} trips generated.")
                
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

# ==========================================
# 4. INCIDENTS & NOTIFICATIONS
# ==========================================

@login_required
@user_passes_test(staff_required)
def view_incidents(request):
    incidents = Incident.objects.all().order_by('status', '-reported_at')
    return render(request, 'mainapp/coordinator/view_incidents.html', {'incidents': incidents})

@login_required
@user_passes_test(staff_required)
def resolve_incident(request, incident_id):
    incident = get_object_or_404(Incident, incident_id=incident_id)
    if incident.status != 'Resolved':
        incident.status = 'Resolved'
        incident.save()
        messages.success(request, f"Incident #{incident.incident_id} marked as Resolved.")
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
            if target_type == 'specific':
                if specific_user:
                    recipients = [specific_user]
                else:
                    messages.error(request, "Please select a user.")
                    return render(request, 'mainapp/coordinator/send_notification.html', {'form': form})
            else:
                recipients = User.objects.filter(role=target_type, is_active=True)

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

# ==========================================
# 5. TRIP MANAGEMENT & USERS
# ==========================================

@login_required
@user_passes_test(coordinator_required)
def view_all_trips(request):
    date_str = request.GET.get('date')
    if date_str:
        selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    else:
        selected_date = timezone.now().date()

    trips = DailyTrip.objects.filter(trip_date=selected_date).order_by('planned_departure')
    
    context = {
        'trips': trips,
        'selected_date': selected_date,
        'today': timezone.now().date()
    }
    return render(request, 'mainapp/coordinator/trip_list.html', context)

@login_required
def manage_trip_passengers(request, trip_id):
    trip = get_object_or_404(DailyTrip, trip_id=trip_id)
    
    # Permission Check
    is_allowed = request.user.role in ['coordinator', 'admin']
    if request.user.role == 'driver':
        assignment = trip.driverassignment_set.first()
        if assignment and assignment.driver.user == request.user:
            is_allowed = True
            
    if not is_allowed:
        messages.error(request, "Access Denied.")
        return redirect('root')

    # Actions
    if request.method == 'POST':
        if 'delete_booking' in request.POST:
            Booking.objects.filter(booking_id=request.POST.get('booking_id')).delete()
            messages.success(request, "Passenger removed.")
            return redirect('manage_trip_passengers', trip_id=trip.trip_id)

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

        elif 'update_capacity' in request.POST:
            assignment = trip.driverassignment_set.first()
            if assignment:
                v_form = VehicleCapacityForm(request.POST, instance=assignment.vehicle)
                if v_form.is_valid():
                    v_form.save()
                    messages.success(request, "Vehicle capacity updated.")
                    return redirect('manage_trip_passengers', trip_id=trip.trip_id)

    # Render
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
    if request.method == 'POST' and 'create_user' in request.POST:
        creation_form = AdminUserCreationForm(request.POST)
        if creation_form.is_valid():
            user = creation_form.save(commit=False)
            user.set_password(creation_form.cleaned_data['password'])
            user.save() # Signals create the profile
            messages.success(request, f"User {user.username} created successfully.")
            return redirect('manage_users_list')
        else:
            messages.error(request, "Error creating user.")
    else:
        creation_form = AdminUserCreationForm()

    query = request.GET.get('q', '')
    if query:
        users = User.objects.filter(
            Q(username__icontains=query) | 
            Q(email__icontains=query) |
            Q(first_name__icontains=query)
        ).order_by('role', 'username')
    else:
        users = User.objects.all().order_by('role', 'username')

    return render(request, 'mainapp/coordinator/manage_users.html', {'users': users, 'creation_form': creation_form, 'query': query})

@login_required
@user_passes_test(admin_required)
def edit_user(request, user_id):
    user_to_edit = get_object_or_404(User, id=user_id)
    if request.method == 'POST':
        form = UserManagementForm(request.POST, instance=user_to_edit)
        if form.is_valid():
            form.save()
            messages.success(request, f"User {user_to_edit.username} updated.")
            return redirect('manage_users_list')
    else:
        form = UserManagementForm(instance=user_to_edit)
    return render(request, 'mainapp/coordinator/edit_user.html', {'form': form, 'target_user': user_to_edit})

@login_required
@user_passes_test(admin_required)
def delete_user(request, user_id):
    user_to_delete = get_object_or_404(User, id=user_id)
    if user_to_delete == request.user:
        messages.error(request, "You cannot delete yourself.")
    else:
        user_to_delete.delete()
        messages.success(request, "User deleted.")
    return redirect('manage_users_list')

# 1. ADMIN CREATE USER (Separate View - Optional if integrated in list)
@login_required
@user_passes_test(admin_required)
def create_user(request):
    if request.method == 'POST':
        form = AdminUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data['password'])
            user.save()
            messages.success(request, f"User {user.username} created.")
            return redirect('manage_users_list')
    else:
        form = AdminUserCreationForm()
    return render(request, 'mainapp/coordinator/create_user.html', {'form': form})

# GLOBAL MAP
def global_map_view(request):
    return render(request, 'mainapp/common/map_view.html')

# TRIGGER FOR ALL SCHEDULES
@login_required
@user_passes_test(coordinator_required)
def generate_future_trips(request):
    schedules = Schedule.objects.all()
    total_count = 0
    for sched in schedules:
        total_count += _generate_trips_for_schedule(sched, days_ahead=7)

    messages.success(request, f"Global Generation Complete: {total_count} trips created/verified.")
    return redirect('coordinator_dashboard')

# ==========================================
# 6. VEHICLE MANAGEMENT
# ==========================================

@login_required
@user_passes_test(staff_required)
def manage_vehicles(request):
    vehicles = Vehicle.objects.all().order_by('type', 'plate_no')
    
    if request.method == 'POST':
        form = VehicleForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "New vehicle added to fleet.")
            return redirect('manage_vehicles')
        else:
            messages.error(request, "Error adding vehicle. Please check the form.")
    else:
        form = VehicleForm()
        
    return render(request, 'mainapp/coordinator/manage_vehicles.html', {
        'vehicles': vehicles, 
        'form': form
    })

@login_required
@user_passes_test(staff_required)
def delete_vehicle(request, vehicle_id):
    vehicle = get_object_or_404(Vehicle, vehicle_id=vehicle_id)
    vehicle.delete()
    messages.success(request, f"Vehicle {vehicle.plate_no} removed.")
    return redirect('manage_vehicles')

@login_required
@user_passes_test(staff_required)
def assign_driver(request, trip_id):
    trip = get_object_or_404(DailyTrip, trip_id=trip_id)
    # Check if an assignment already exists for this trip
    assignment = trip.driverassignment_set.first()
    
    if request.method == 'POST':
        form = DriverAssignmentForm(request.POST, instance=assignment)
        if form.is_valid():
            new_assignment = form.save(commit=False)
            new_assignment.trip = trip
            new_assignment.save()
            messages.success(request, f"Driver assigned to Trip #{trip.trip_id}.")
            return redirect('view_all_trips')
    else:
        form = DriverAssignmentForm(instance=assignment)

    return render(request, 'mainapp/coordinator/assign_driver.html', {
        'form': form, 
        'trip': trip
    })