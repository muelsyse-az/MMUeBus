from django.urls import path
# We import the views package.
# Note: We must import the specific modules since we split views into a folder.
from mainapp.views import auth_views, student_views, driver_views, api_views

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

    # ==============================
    # 3. DRIVER PAGES
    # ==============================
    # Maps to: http://127.0.0.1:8000/driver/dashboard/
    path('driver/dashboard/', driver_views.driver_dashboard, name='driver_dashboard'),

    # Maps to: http://127.0.0.1:8000/driver/start/1/
    path('driver/start/<int:trip_id>/', driver_views.start_trip, name='start_trip'),

    # ==============================
    # 4. API ENDPOINTS (For Maps)
    # ==============================
    # Maps to: http://127.0.0.1:8000/api/shuttles/
    path('api/shuttles/', api_views.get_shuttle_locations, name='api_shuttle_locations'),
    path('api/update-location/', api_views.update_location, name='api_update_location'),
    path('map/', student_views.global_map_view, name='global_map'),
]
