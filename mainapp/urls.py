from django.urls import path
from mainapp.views import auth_views, student_views, driver_views, api_views, coord_views, analytics_views

urlpatterns = [
    # =========================================================================
    # 1. CORE SYSTEM & AUTHENTICATION
    # =========================================================================
    # Entry point and secure access management.
    path('', auth_views.root_route, name='root'),
    path('login/', auth_views.login_view, name='login'),
    path('logout/', auth_views.logout_view, name='logout'),
    path('register/', auth_views.register_student, name='register_student'),
    
    # Account Management
    path('profile/update/', auth_views.update_profile, name='update_profile'),
    path('profile/password/', auth_views.change_password, name='change_password'),
    
    # User Notifications (Inbox & Actions)
    path('notifications/', auth_views.notification_inbox, name='notification_inbox'),
    path('notifications/read/<int:notif_id>/', auth_views.mark_notification_read, name='mark_read'),

    # =========================================================================
    # 2. API ENDPOINTS & MAP VISUALIZATION
    # =========================================================================
    # AJAX endpoints serving JSON data for map rendering and real-time tracking.
    path('map/', student_views.global_map_view, name='global_map'),
    path('api/shuttles/', api_views.get_shuttle_locations, name='api_shuttles'),
    path('api/update-location/', api_views.update_location, name='api_update_location'),
    path('api/stops/', api_views.get_stops_data, name='api_stops'),
    path('api/routes/', api_views.get_route_paths, name='api_routes'),

    # =========================================================================
    # 3. STUDENT PORTAL
    # =========================================================================
    # Workflows for booking, tracking, and managing student travel.
    path('student/dashboard/', student_views.student_dashboard, name='student_dashboard'),
    path('student/trips/', student_views.student_view_trips, name='student_view_trips'),
    
    # Booking Lifecycle
    path('student/schedule/<int:schedule_id>/trips/', student_views.view_schedule_trips, name='view_schedule_trips'),
    path('student/reserve/<int:trip_id>/', student_views.reserve_seat, name='reserve_seat'),
    path('student/booking/cancel/<int:booking_id>/', student_views.cancel_booking, name='cancel_booking'),
    path('student/checkin/<int:booking_id>/', student_views.check_in_booking, name='check_in_booking'),
    
    # Feedback
    path('student/report/', student_views.report_incident, name='student_report_incident'),

    # =========================================================================
    # 4. DRIVER PORTAL
    # =========================================================================
    # Interface for active trip execution and reporting.
    path('driver/dashboard/', driver_views.driver_dashboard, name='driver_dashboard'),
    
    # Active Trip Workflow
    path('driver/start/<int:trip_id>/', driver_views.start_trip, name='start_trip'),
    path('driver/trip/<int:trip_id>/details/', driver_views.view_trip_details, name='view_trip_details'),
    path('driver/notify_arrival/<int:trip_id>/', driver_views.notify_arrival, name='notify_arrival'),
    path('driver/finish/<int:trip_id>/', driver_views.finish_trip, name='finish_trip'),
    # Reporting
    path('driver/report/', driver_views.driver_report_incident, name='driver_report_incident'),

    # =========================================================================
    # 5. COORDINATOR: DASHBOARDS
    # =========================================================================
    # High-level overview and analytics for operations staff.
    path('coordinator/dashboard/', coord_views.coordinator_dashboard, name='coordinator_dashboard'),
    path('coordinator/performance/', analytics_views.performance_dashboard, name='performance_dashboard'),

    # =========================================================================
    # 6. COORDINATOR: INFRASTRUCTURE (Routes, Stops, Vehicles)
    # =========================================================================
    # Management of physical assets and static route data.
    path('coordinator/routes/', coord_views.manage_routes, name='manage_routes'),
    path('coordinator/routes/add/', coord_views.add_route, name='add_route'),
    path('coordinator/routes/delete/<int:route_id>/', coord_views.delete_route, name='delete_route'),
    
    # Route-Stop Associations
    path('coordinator/routes/<int:route_id>/stops/', coord_views.manage_stops, name='manage_stops'),
    path('coordinator/routes/stops/delete/<int:route_stop_id>/', coord_views.delete_route_stop, name='delete_route_stop'),
    
    # Physical Locations
    path('coordinator/stops/add/', coord_views.add_physical_stop, name='add_physical_stop'),
    
    # Fleet Management
    path('coordinator/vehicles/', coord_views.manage_vehicles, name='manage_vehicles'),
    path('coordinator/vehicles/delete/<int:vehicle_id>/', coord_views.delete_vehicle, name='delete_vehicle'),

    # =========================================================================
    # 7. COORDINATOR: SCHEDULING
    # =========================================================================
    # Creating timetables and generating daily trips.
    path('coordinator/schedules/', coord_views.manage_schedules, name='manage_schedules'),
    path('coordinator/schedules/add/', coord_views.add_schedule, name='add_schedule'),
    path('coordinator/schedule/create/', coord_views.edit_schedule, name='create_schedule'),
    path('coordinator/schedules/edit/<int:schedule_id>/', coord_views.edit_schedule, name='edit_schedule'),
    path('coordinator/schedules/delete/<int:schedule_id>/', coord_views.delete_schedule, name='delete_schedule'),
    
    # Batch Processing
    path('coordinator/trips/generate/', coord_views.generate_future_trips, name='generate_future_trips'),

    # =========================================================================
    # 8. COORDINATOR: DAILY OPERATIONS
    # =========================================================================
    # Real-time management of active trips and passenger manifests.
    path('coordinator/trips/', coord_views.view_all_trips, name='view_all_trips'),
    path('coordinator/trip/<int:trip_id>/assign/', coord_views.assign_driver, name='assign_driver'),
    path('trip/<int:trip_id>/manage/', coord_views.manage_trip_passengers, name='manage_trip_passengers'),

    # =========================================================================
    # 9. COORDINATOR: INCIDENTS & COMMS
    # =========================================================================
    # Handling tickets and broadcasting messages.
    path('coordinator/incidents/', coord_views.view_incidents, name='view_incidents'),
    path('coordinator/incidents/resolve/<int:incident_id>/', coord_views.resolve_incident, name='resolve_incident'),
    path('coordinator/notify/', coord_views.send_notification, name='send_notification'),

    # =========================================================================
    # 10. SYSTEM ADMINISTRATION
    # =========================================================================
    # User account control (CRUD).
    path('sysadmin/users/', coord_views.manage_users_list, name='manage_users_list'),
    path('sysadmin/users/<int:user_id>/edit/', coord_views.edit_user, name='edit_user'),
    path('sysadmin/users/<int:user_id>/delete/', coord_views.delete_user, name='delete_user'),

    # =========================================================================
    # 11. SHARED/COMMON VIEWS
    # =========================================================================
    # Pages accessible by multiple roles (e.g., viewing route maps/lists).
    path('routes/view/', student_views.view_routes_schedules, name='view_routes'),
]