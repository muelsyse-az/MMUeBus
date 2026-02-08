from datetime import datetime, timedelta, date
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from mainapp.decorators import staff_required, coordinator_required, admin_required
from mainapp.models import Route, Stop, Schedule, RouteStop, DailyTrip, Incident, Notification, User, Booking, DriverAssignment, Vehicle
from mainapp.forms import RouteForm, StopForm, ScheduleForm, RouteStopForm, NotificationForm, ManualBookingForm, VehicleCapacityForm, UserManagementForm, AdminUserCreationForm, VehicleForm, DriverAssignmentForm
from django.utils import timezone
from django.db.models import Q
from mainapp.services import get_trip_duration, check_resource_availability
from django.db import transaction

def _generate_trips_for_schedule(schedule, days_ahead=30):
    """
    This private utility function automatically generates DailyTrip records for a specific schedule over a defined future period, ensuring the operational calendar is populated.
    
    It iterates through the specified number of days, checks if the schedule is active for that specific day of the week and date range, and uses `get_or_create` to instantiate trip records while automatically assigning default drivers and vehicles if they are configured.
    """
    today = timezone.now().date()
    weekday_map = {0: 'Mon', 1: 'Tue', 2: 'Wed', 3: 'Thu', 4: 'Fri', 5: 'Sat', 6: 'Sun'}
    trips_created_count = 0

    for i in range(days_ahead):
        target_date = today + timedelta(days=i)
        day_str = weekday_map[target_date.weekday()]

        if day_str in schedule.days_of_week:
            
            if schedule.valid_from <= target_date <= schedule.valid_to:
                
                current_time = datetime.combine(target_date, schedule.start_time)
                end_datetime = datetime.combine(target_date, schedule.end_time)
                
                if schedule.end_time < schedule.start_time:
                    end_datetime += timedelta(days=1)

                while current_time < end_datetime:
                    trip, created = DailyTrip.objects.get_or_create(
                        schedule=schedule,
                        trip_date=current_time.date(),
                        planned_departure=timezone.make_aware(current_time),
                        defaults={'status': 'Scheduled'}
                    )

                    if created:
                        trips_created_count += 1
                        if schedule.default_driver and schedule.default_vehicle:
                            # FIX: Check availability before assigning default resources
                            duration = get_trip_duration(schedule.route)
                            is_free, _ = check_resource_availability(
                                driver=schedule.default_driver,
                                vehicle=schedule.default_vehicle,
                                trip_date=trip.trip_date,
                                start_time=trip.planned_departure,
                                duration_minutes=duration
                            )

                            if is_free:
                                DriverAssignment.objects.get_or_create(
                                    trip=trip,
                                    driver=schedule.default_driver,
                                    vehicle=schedule.default_vehicle
                                )
                            # Note: If not free, we leave it unassigned (user can fix manually)

                    current_time += timedelta(minutes=schedule.frequency_min)
    
    return trips_created_count

@login_required
@user_passes_test(staff_required)
def coordinator_dashboard(request):
    """
    Fixed: Packs data into 'stats' dictionary to match the AdminLTE template.
    """
    total_routes = Route.objects.count()
    active_trips = DailyTrip.objects.filter(status='In-Progress').count()
    
    # Calculate Passengers (Confirmed + Checked-In)
    total_passengers = Booking.objects.filter(
        trip__trip_date=timezone.now().date(),
        status__in=['Confirmed', 'Checked-In']
    ).count()

    recent_incidents = Incident.objects.filter(status='New').order_by('-reported_at')[:5]
    pending_incidents_count = Incident.objects.filter(status='New').count()

    context = {
        # FIX: Wrap these in a 'stats' dictionary
        'stats': {
            'active_routes': total_routes,
            'active_buses': active_trips,
            'open_incidents': pending_incidents_count,
            'total_passengers': total_passengers
        },
        'recent_incidents': recent_incidents
    }
    return render(request, 'mainapp/coordinator/dashboard.html', context)

@login_required
@user_passes_test(staff_required)
def manage_routes(request):
    """
    This view provides an interface for listing all existing transport routes and adding new physical stop locations to the system.
    
    It fetches all Route objects and initializes an empty StopForm, allowing the template to display the list of routes alongside a modal or form for creating new stops.
    """
    routes = Route.objects.all()
    stop_form = StopForm()
    return render(request, 'mainapp/coordinator/manage_routes.html', {'routes': routes, 'stop_form': stop_form})

@login_required
@user_passes_test(staff_required)
def edit_route(request, route_id=None):
    """
    Handles both creating a new route and editing an existing one.
    """
    if route_id:
        route = get_object_or_404(Route, route_id=route_id)
        title = "Edit Route"
    else:
        route = None
        title = "Add Route"

    if request.method == 'POST':
        form = RouteForm(request.POST, instance=route)
        if form.is_valid():
            saved_route = form.save()
            if route_id:
                messages.success(request, f"Route '{saved_route.name}' updated.")
                return redirect('manage_routes')
            else:
                messages.success(request, f"Route '{saved_route.name}' created! Now add stops.")
                return redirect('manage_stops', route_id=saved_route.route_id)
    else:
        form = RouteForm(instance=route)
    return render(request, 'mainapp/coordinator/route_form.html', {'form': form, 'title': title})

@login_required
@user_passes_test(staff_required)
def delete_route(request, route_id):
    """
    This view performs the deletion of a specific route from the system.
    
    It retrieves the Route object by its ID and calls the delete() method, which cascades to remove associated schedules and stops before redirecting back to the route management list.
    """
    route = get_object_or_404(Route, route_id=route_id)
    route.delete()
    messages.success(request, "Route deleted successfully.")
    return redirect('manage_routes')

@login_required
@user_passes_test(staff_required)
def manage_stops(request, route_id):
    """
    This view manages the sequence of stops for a specific route, allowing coordinators to link physical locations to a route path.
    
    It fetches the target Route and its existing RouteStop objects (ordered by sequence), processes the RouteStopForm to link new stops, and handles potential duplication errors using a try-except block.
    """
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
def add_physical_stop(request):
    """
    This view allows for the quick creation of a physical bus stop location (latitude/longitude/name) directly from the route management screen.
    
    It validates the StopForm and saves the new Stop object, redirecting the user back to the previous page (Referer) to maintain their workflow context.
    """
    if request.method == 'POST':
        form = StopForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Physical Stop Location Created.")
            return redirect(request.META.get('HTTP_REFERER', 'manage_routes'))
    return redirect('manage_routes')

@login_required
@user_passes_test(staff_required)
def delete_route_stop(request, route_stop_id):
    """
    This view removes a specific stop from a route's sequence without deleting the physical stop location itself.
    
    It retrieves the RouteStop association, identifies the parent route ID for redirection, and deletes the association record.
    """
    rs = get_object_or_404(RouteStop, id=route_stop_id)
    route_id = rs.route.route_id
    rs.delete()
    messages.success(request, "Stop removed from route.")
    return redirect('manage_stops', route_id=route_id)

@login_required
@user_passes_test(staff_required)
def manage_schedules(request):
    """
    This view lists all defined operating schedules, providing an overview of when different routes are active.
    
    It retrieves all Schedule objects, ordered by the associated route name, and renders them in the management template.
    """
    schedules = Schedule.objects.all().order_by('route__name')
    return render(request, 'mainapp/coordinator/manage_schedules.html', {'schedules': schedules})

@login_required
@user_passes_test(staff_required)
def add_schedule(request):
    """
    Creates a new operating schedule. 
    Atomic transaction ensures that if trip generation fails, the schedule is not saved.
    """
    if request.method == 'POST':
        form = ScheduleForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic(): # <--- NEW SAFETY BLOCK
                    schedule = form.save()
                    
                    # This validation logic will now run safely
                    count = _generate_trips_for_schedule(schedule)
                    
                messages.success(request, f"Schedule published. {count} upcoming trips generated.")
                return redirect('manage_schedules')
                
            except Exception as e:
                # If generation fails (e.g. Driver Busy or Code Error), roll back everything
                messages.error(request, f"Error generating schedule: {str(e)}")
    else:
        form = ScheduleForm()
    return render(request, 'mainapp/coordinator/schedule_form.html', {'form': form, 'title': 'Add Schedule'})

@login_required
@user_passes_test(staff_required)
def edit_schedule(request, schedule_id=None):
    """
    This view handles the modification of existing schedules, ensuring that future trips are reconciled if critical timing parameters are changed.
    
    If critical fields (start/end time, days, route) are modified, it deletes future 'Scheduled' trips to prevent ghost records, saves the schedule, and then regenerates the trips using the updated parameters.
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
            if schedule_id and form.has_changed():
                critical_fields = ['start_time', 'end_time', 'days_of_week', 'route']
                if any(field in form.changed_data for field in critical_fields):
                    DailyTrip.objects.filter(
                        schedule=schedule,
                        status='Scheduled',
                        trip_date__gte=timezone.now().date()
                    ).delete()
                    messages.info(request, "Schedule changed: Old future trips were removed.")

            schedule = form.save()
            
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
    """
    This view deletes an operating schedule from the system.
    
    It retrieves the Schedule object and deletes it, which typically cascades to remove future scheduled trips depending on database configuration.
    """
    schedule = get_object_or_404(Schedule, schedule_id=schedule_id)
    schedule.delete()
    messages.success(request, "Schedule deleted.")
    return redirect('manage_schedules')

@login_required
@user_passes_test(coordinator_required)
def generate_future_trips(request):
    """
    This view manually triggers the trip generation process for all active schedules, useful for ensuring the calendar is populated for the upcoming week.
    
    It iterates through every Schedule object in the database and calls `_generate_trips_for_schedule` for each, summing the total number of new trips created.
    """
    schedules = Schedule.objects.all()
    total_count = 0
    for sched in schedules:
        total_count += _generate_trips_for_schedule(sched, days_ahead=7)

    messages.success(request, f"Global Generation Complete: {total_count} trips created/verified.")
    return redirect('coordinator_dashboard')

@login_required
@user_passes_test(staff_required)
def view_all_trips(request):
    """
    This view displays a daily manifest of trips, allowing coordinators to filter operations by specific dates.
    
    It accepts a 'date' GET parameter (defaulting to today), filters `DailyTrip` objects by that date, and orders them by departure time for the template.
    """
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
    """
    This view provides granular control over a specific trip's manifest, allowing authorized users to add/remove passengers and update vehicle capacity.
    
    It handles multiple POST actions ('delete_booking', 'add_passenger', 'update_capacity') by validating permissions, modifying the Booking or Vehicle models, and refreshing the page with success or error messages.
    """
    trip = get_object_or_404(DailyTrip, trip_id=trip_id)
    
    is_allowed = request.user.role in ['coordinator', 'admin']
    if request.user.role == 'driver':
        assignment = trip.driverassignment_set.first()
        if assignment and assignment.driver.user == request.user:
            is_allowed = True
            
    if not is_allowed:
        messages.error(request, "Access Denied.")
        return redirect('root')

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
@user_passes_test(staff_required)
def assign_driver(request, trip_id):
    """
    This view enables the manual assignment of a driver and vehicle to a specific trip.
    
    It retrieves the trip and any existing assignment, processes the DriverAssignmentForm to link a driver and vehicle to the trip, and saves the new assignment record.
    """
    trip = get_object_or_404(DailyTrip, trip_id=trip_id)
    assignment = trip.driverassignment_set.first()
    
    if request.method == 'POST':
        form = DriverAssignmentForm(request.POST, instance=assignment, trip=trip)
        if form.is_valid():
            new_assignment = form.save(commit=False)
            new_assignment.trip = trip
            new_assignment.save()
            messages.success(request, f"Driver assigned to Trip #{trip.trip_id}.")
            return redirect('view_all_trips')
    else:
        form = DriverAssignmentForm(instance=assignment, trip=trip)

    return render(request, 'mainapp/coordinator/assign_driver.html', {
        'form': form, 
        'trip': trip
    })

@login_required
@user_passes_test(staff_required)
def manage_vehicles(request):
    """
    This view handles the fleet management, listing all available vehicles and providing a form to register new ones.
    
    It displays all vehicles ordered by type, processes the VehicleForm to add new entries to the fleet, and reloads the page upon success.
    """
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
def edit_vehicle(request, vehicle_id):
    """
    Provides a dedicated page to edit vehicle details.
    """
    vehicle = get_object_or_404(Vehicle, vehicle_id=vehicle_id)
    if request.method == 'POST':
        form = VehicleForm(request.POST, instance=vehicle)
        if form.is_valid():
            form.save()
            messages.success(request, "Vehicle updated successfully.")
            return redirect('manage_vehicles')
    else:
        form = VehicleForm(instance=vehicle)
        
    return render(request, 'mainapp/coordinator/vehicle_form.html', {
        'form': form, 
        'title': f'Edit Vehicle: {vehicle.plate_no}'
    })

@login_required
@user_passes_test(staff_required)
def delete_vehicle(request, vehicle_id):
    """
    This view removes a vehicle from the fleet database.
    
    It retrieves the specific Vehicle object by ID and deletes it, confirming the action with a success message.
    """
    vehicle = get_object_or_404(Vehicle, vehicle_id=vehicle_id)
    vehicle.delete()
    messages.success(request, f"Vehicle {vehicle.plate_no} removed.")
    return redirect('manage_vehicles')

@login_required
@user_passes_test(staff_required)
def view_incidents(request):
    """
    This view displays a list of all reported incidents, prioritizing active issues.
    
    It queries the Incident model and orders the results first by status (keeping open issues at the top) and then by the reporting timestamp.
    """
    incidents = Incident.objects.all().order_by('status', '-reported_at')
    return render(request, 'mainapp/coordinator/view_incidents.html', {'incidents': incidents})

@login_required
@user_passes_test(staff_required)
def resolve_incident(request, incident_id):
    """
    This view marks a specific incident as resolved, closing the ticket in the system.
    
    It fetches the Incident object, updates its status to 'Resolved' if it isn't already, and saves the change before returning to the incident list.
    """
    incident = get_object_or_404(Incident, incident_id=incident_id)
    if incident.status != 'Resolved':
        incident.status = 'Resolved'
        incident.save()
        messages.success(request, f"Incident #{incident.incident_id} marked as Resolved.")
    return redirect('view_incidents')

@login_required
@user_passes_test(staff_required)
def send_notification(request):
    """
    This view allows coordinators to broadcast messages to specific users or entire user roles (e.g., all drivers).
    
    It processes the NotificationForm, determines the recipient list based on the target type selection (single user vs. role group), and creates individual Notification records for every target user.
    """
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

@login_required
@user_passes_test(admin_required)
def manage_users_list(request):
    """
    This view provides the administrative interface for searching, listing, and creating system users.
    
    It handles both the display of users (filtering by a search query if provided) and the processing of the `AdminUserCreationForm` to register new accounts directly from the dashboard.
    """
    if request.method == 'POST' and 'create_user' in request.POST:
        creation_form = AdminUserCreationForm(request.POST)
        if creation_form.is_valid():
            user = creation_form.save(commit=False)
            user.set_password(creation_form.cleaned_data['password'])
            user.save()
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
def create_user(request):
    """
    This dedicated view handles the creation of new user accounts if the action is not performed via the main list view.
    
    It validates the `AdminUserCreationForm`, securely hashes the password using `set_password`, and saves the new user record.
    """
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

@login_required
@user_passes_test(admin_required)
def edit_user(request, user_id):
    """
    This view allows administrators to modify the details of an existing user account.
    
    It retrieves the target User object, populates the `UserManagementForm` with their current data, and saves any changes made by the admin.
    """
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
    """
    This view permanently deletes a user account from the system, with a safeguard to prevent self-deletion.
    
    It checks if the target user ID matches the current request user; if not, it proceeds to delete the record and confirms the action.
    """
    user_to_delete = get_object_or_404(User, id=user_id)
    if user_to_delete == request.user:
        messages.error(request, "You cannot delete yourself.")
    else:
        user_to_delete.delete()
        messages.success(request, "User deleted.")
    return redirect('manage_users_list')

def global_map_view(request):
    """
    This view renders the global map interface, used as a standalone page for visualizing all active shuttles and routes.
    
    It simply returns the map template, which will asynchronously fetch coordinate data via the separate API endpoints.
    """
    return render(request, 'mainapp/common/map_view.html')
