from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from mainapp.decorators import staff_required
from mainapp.models import Route, Stop, Schedule, RouteStop, DailyTrip, Incident
from mainapp.forms import RouteForm, StopForm, ScheduleForm, RouteStopForm

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
@user_passes_test(staff_required)
def edit_schedule(request, schedule_id):
    schedule = get_object_or_404(Schedule, schedule_id=schedule_id)
    if request.method == 'POST':
        form = ScheduleForm(request.POST, instance=schedule)
        if form.is_valid():
            form.save()
            messages.success(request, "Schedule updated.")
            return redirect('manage_schedules')
    else:
        form = ScheduleForm(instance=schedule)
    return render(request, 'mainapp/coordinator/schedule_form.html', {'form': form, 'title': 'Edit Schedule'})

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

# Map View
def global_map_view(request):
    return render(request, 'mainapp/common/map_view.html')