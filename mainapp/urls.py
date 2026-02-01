from django.urls import path
# We import the views package.
# Note: We must import the specific modules since we split views into a folder.
from mainapp.views import auth_views, student_views, driver_views, api_views, coord_views

urlpatterns = [
# ==============================
    # 0. HOMEPAGE DISPATCHER (NEW)
    # ==============================
    # When user visits "http://127.0.0.1:8000/", run root_route
    path('', auth_views.root_route, name='root'),

    # ==============================
    # 1. AUTHENTICATION (Shared)
    # ==============================
    # Maps to: http://127.0.0.1:8000/login/
    path('login/', auth_views.login_view, name='login'),
    path('logout/', auth_views.logout_view, name='logout'),
    path('register/', auth_views.register_student, name='register_student'),
    path('profile/update/', auth_views.update_profile, name='update_profile'),

    # ==============================
    # 2. STUDENT PAGES
    # ==============================
    # Maps to: http://127.0.0.1:8000/student/dashboard/
    path('student/dashboard/', student_views.student_dashboard, name='student_dashboard'),

    # Maps to: http://127.0.0.1:8000/student/reserve/1/ (where 1 is the trip_id)
    path('student/reserve/<int:trip_id>/', student_views.reserve_seat, name='reserve_seat'),

    # Student Incident
    path('student/report/', student_views.report_incident, name='student_report_incident'),


    # ==============================
    # 3. DRIVER PAGES
    # ==============================
    # Maps to: http://127.0.0.1:8000/driver/dashboard/
    path('driver/dashboard/', driver_views.driver_dashboard, name='driver_dashboard'),

    # Maps to: http://127.0.0.1:8000/driver/start/1/
    path('driver/start/<int:trip_id>/', driver_views.start_trip, name='start_trip'),

    # Driver Incident
    path('driver/report/', driver_views.driver_report_incident, name='driver_report_incident'),
    # ==============================
    # 4. API ENDPOINTS (For Maps)
    # ==============================
    # Maps to: http://127.0.0.1:8000/api/shuttles/
    path('api/shuttles/', api_views.get_shuttle_locations, name='api_shuttle_locations'),
    path('api/update-location/', api_views.update_location, name='api_update_location'),
    path('map/', student_views.global_map_view, name='global_map'),

    path('coordinator/dashboard/', coord_views.coordinator_dashboard, name='coordinator_dashboard'),
    # COORDINATOR - ROUTES
    path('coordinator/routes/', coord_views.manage_routes, name='manage_routes'),
    path('coordinator/routes/add/', coord_views.add_route, name='add_route'),
    path('coordinator/routes/delete/<int:route_id>/', coord_views.delete_route, name='delete_route'),

    # COORDINATOR - STOPS (The Route-Stop Link)
    path('coordinator/routes/<int:route_id>/stops/', coord_views.manage_stops, name='manage_stops'),
    path('coordinator/routes/stops/delete/<int:route_stop_id>/', coord_views.delete_route_stop, name='delete_route_stop'),

    # COORDINATOR - PHYSICAL STOPS (Quick Add)
    path('coordinator/stops/add/', coord_views.add_physical_stop, name='add_physical_stop'),

    # COORDINATOR - SCHEDULES
    path('coordinator/schedules/', coord_views.manage_schedules, name='manage_schedules'),
    path('coordinator/schedules/add/', coord_views.add_schedule, name='add_schedule'),
    path('coordinator/schedules/edit/<int:schedule_id>/', coord_views.edit_schedule, name='edit_schedule'),
    path('coordinator/schedules/delete/<int:schedule_id>/', coord_views.delete_schedule, name='delete_schedule'),

    # COORDINATOR - INCIDENTS
    path('coordinator/incidents/', coord_views.view_incidents, name='view_incidents'),
    path('coordinator/incidents/resolve/<int:incident_id>/', coord_views.resolve_incident, name='resolve_incident'),

    # SHARED VIEWS
    path('routes/view/', student_views.view_routes_schedules, name='view_routes'),
]
