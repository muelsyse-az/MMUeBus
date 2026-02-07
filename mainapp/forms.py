from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from .models import User, Route, Stop, Schedule, RouteStop, Vehicle, Driver, Incident, DailyTrip, Notification, DriverAssignment
from datetime import datetime, timedelta, date
from django.utils import timezone
from .services import get_trip_duration, check_resource_availability

User = get_user_model()

# ==========================================
# 1. AUTHENTICATION & PROFILES
# ==========================================

class StudentRegistrationForm(UserCreationForm):
    """
    Handles the self-registration process for new students.
    
    It extends the standard UserCreationForm to include essential profile fields 
    (name, email, phone) and automatically enforces the 'student' role upon saving, 
    ensuring new sign-ups do not accidentally gain elevated privileges.
    """
    first_name = forms.CharField(required=True)
    last_name = forms.CharField(required=True)
    email = forms.EmailField(required=True)
    phone = forms.CharField(required=True, max_length=15)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = UserCreationForm.Meta.fields + ('first_name', 'last_name', 'email', 'phone')
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = 'student'  # Force role to Student
        if commit:
            user.save()
        return user

class UserProfileForm(forms.ModelForm):
    """
    Allows any authenticated user to update their personal contact details.
    
    It provides a restricted view of the User model, permitting changes only to 
    identifiable information like names and contact methods, while excluding 
    sensitive fields like role or username.
    """
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'phone']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
        }


# ==========================================
# 2. CORE INFRASTRUCTURE (Routes & Stops)
# ==========================================

class RouteForm(forms.ModelForm):
    """
    Used by coordinators to define a new transport route.
    
    It captures the route's name and a descriptive summary, serving as the 
    parent object to which stops and schedules will later be attached.
    """
    class Meta:
        model = Route
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

class StopForm(forms.ModelForm):
    """
    Used to create a physical bus stop location.
    
    It captures the geographic coordinates (latitude/longitude) and a recognizable name, 
    allowing the system to plot the stop on a map independent of any specific route.
    """
    class Meta:
        model = Stop
        fields = ['name', 'latitude', 'longitude']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'latitude': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.000001'}),
            'longitude': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.000001'}),
        }

class RouteStopForm(forms.ModelForm):
    """
    Links a physical Stop to a Route with a specific sequence order.
    
    This form allows coordinators to build the path of a route by specifying which 
    stop comes next in the sequence and the estimated travel time to reach it.
    """
    class Meta:
        model = RouteStop
        fields = ['stop', 'sequence_no', 'est_minutes']
        widgets = {
            'stop': forms.Select(attrs={'class': 'form-select'}),
            'sequence_no': forms.NumberInput(attrs={'class': 'form-control'}),
            'est_minutes': forms.NumberInput(attrs={'class': 'form-control'}),
        }


# ==========================================
# 3. OPERATIONS & SCHEDULING
# ==========================================

class ScheduleForm(forms.ModelForm):
    """
    A comprehensive form for defining operating schedules and defaults.
    
    It captures the validity period (dates), timing (start/end/frequency), and 
    optional default resources (driver/vehicle). This acts as the blueprint 
    from which daily trips are automatically generated.
    """
    def clean_frequency_min(self):
        freq = self.cleaned_data['frequency_min']
        if freq < 1:
            raise forms.ValidationError("Frequency must be at least 1 minute.")
        return freq

    default_driver = forms.ModelChoiceField(
        queryset=Driver.objects.all(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Assign Driver"
    )
    default_vehicle = forms.ModelChoiceField(
        queryset=Vehicle.objects.all(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Assign Vehicle"
    )

    class Meta:
        model = Schedule
        fields = ['route', 'days_of_week', 'start_time', 'end_time', 
                 'frequency_min', 'valid_from', 'valid_to', 
                 'default_driver', 'default_vehicle']
        
        widgets = {
            'route': forms.Select(attrs={'class': 'form-select'}),
            'days_of_week': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Mon,Tue,Wed'}),
            'start_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'frequency_min': forms.NumberInput(attrs={'class': 'form-control'}),
            'valid_from': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'valid_to': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super(ScheduleForm, self).__init__(*args, **kwargs)
        self.fields['default_driver'].label_from_instance = lambda obj: f"{obj.user.first_name} ({obj.user.username})"
    
    def clean(self):
        cleaned_data = super().clean()
        
        # 1. Get Form Data
        driver = cleaned_data.get('default_driver')
        vehicle = cleaned_data.get('default_vehicle')
        route = cleaned_data.get('route')
        days_of_week = cleaned_data.get('days_of_week')
        start_time = cleaned_data.get('start_time')
        end_time = cleaned_data.get('end_time')
        freq = cleaned_data.get('frequency_min')
        valid_from = cleaned_data.get('valid_from')
        valid_to = cleaned_data.get('valid_to')

        # Only validate if we have the necessary data and a resource to check
        if route and valid_from and valid_to and days_of_week and start_time and (driver or vehicle):
            
            duration = get_trip_duration(route)
            weekday_map = {0: 'Mon', 1: 'Tue', 2: 'Wed', 3: 'Thu', 4: 'Fri', 5: 'Sat', 6: 'Sun'}
            
            # 2. Check a sample range (e.g., first 30 days) to catch recurring conflicts
            # We don't need to check 2 years into the future; 1 month covers the weekly pattern.
            check_limit_days = 30
            current_check_date = valid_from
            end_check_date = min(valid_to, valid_from + timedelta(days=check_limit_days))
            
            exclude_sched_id = self.instance.pk if self.instance.pk else None

            while current_check_date <= end_check_date:
                day_str = weekday_map[current_check_date.weekday()]
                
                if day_str in days_of_week:
                    # Simulate trip times for this day
                    current_trip_time = datetime.combine(current_check_date, start_time)
                    trip_end_limit = datetime.combine(current_check_date, end_time)
                    
                    if end_time < start_time:
                        trip_end_limit += timedelta(days=1)

                    while current_trip_time < trip_end_limit:
                        # 3. Check Availability for this specific slot
                        # Convert naive datetime to aware if your project uses timezone support
                        aware_start = timezone.make_aware(current_trip_time) if timezone.is_aware(timezone.now()) else current_trip_time
                        
                        is_available, error_msg = check_resource_availability(
                            driver=driver,
                            vehicle=vehicle,
                            trip_date=current_check_date,
                            start_time=aware_start,
                            duration_minutes=duration,
                            exclude_schedule_id=exclude_sched_id
                        )

                        if not is_available:
                            # Raise error immediately to stop saving
                            raise forms.ValidationError(f"Conflict on {current_check_date} at {start_time}: {error_msg}")

                        # Move to next trip in the sequence
                        if freq and freq > 0:
                            current_trip_time += timedelta(minutes=freq)
                        else:
                            break # Safety break
                
                current_check_date += timedelta(days=1)

        return cleaned_data

class DriverAssignmentForm(forms.ModelForm):
    """
    Used to manually assign a specific Driver and Vehicle to a specific DailyTrip.
    
    It filters the selection to valid drivers and vehicles, overriding any 
    defaults set by the schedule.
    """
    driver = forms.ModelChoiceField(
        queryset=Driver.objects.all(),
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Select Driver"
    )
    vehicle = forms.ModelChoiceField(
        queryset=Vehicle.objects.all(),
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Select Vehicle"
    )

    class Meta:
        model = DriverAssignment
        fields = ['driver', 'vehicle']
        
    def __init__(self, *args, **kwargs):
        self.trip = kwargs.pop('trip', None)
        super(DriverAssignmentForm, self).__init__(*args, **kwargs)
        self.fields['driver'].label_from_instance = lambda obj: f"{obj.user.first_name} {obj.user.last_name} ({obj.user.username})"
        self.fields['vehicle'].label_from_instance = lambda obj: f"{obj.plate_no} ({obj.type})"

    def clean(self):
            cleaned_data = super().clean()
            driver = cleaned_data.get('driver')
            vehicle = cleaned_data.get('vehicle')
            
            # Validation requires the trip context
            if self.trip and (driver or vehicle):
                duration = get_trip_duration(self.trip.schedule.route)
                
                is_available, error_msg = check_resource_availability(
                    driver=driver,
                    vehicle=vehicle,
                    trip_date=self.trip.trip_date,
                    start_time=self.trip.planned_departure,
                    duration_minutes=duration,
                    current_assignment_id=self.instance.assignment_id if self.instance.pk else None
                )

                if not is_available:
                    raise forms.ValidationError(error_msg)

            return cleaned_data

class ManualBookingForm(forms.Form):
    """
    A simple input form for coordinators to manually add a student to a trip manifest.
    
    It requires the student's username rather than a dropdown selection, which 
    is more efficient for searching large user databases.
    """
    student_username = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter Student ID/Username'}),
        label="Student Username"
    )

class VehicleForm(forms.ModelForm):
    """
    Used to register a new vehicle into the fleet.
    
    It captures the vehicle's plate number, type (e.g., Bus, Van), and total passenger capacity.
    """
    class Meta:
        model = Vehicle
        fields = ['plate_no', 'type', 'capacity']
        widgets = {
            'plate_no': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. ABC-1234'}),
            'type': forms.Select(attrs={'class': 'form-select'}),
            'capacity': forms.NumberInput(attrs={'class': 'form-control'}),
        }

class VehicleCapacityForm(forms.ModelForm):
    """
    A specialized form for quickly updating just the capacity of a vehicle.
    
    This is typically used in the trip management view to adjust seat availability on the fly.
    """
    class Meta:
        model = Vehicle
        fields = ['capacity']
        widgets = {
            'capacity': forms.NumberInput(attrs={'class': 'form-control'})
        }


# ==========================================
# 4. INCIDENTS & COMMUNICATION
# ==========================================

class StudentIncidentForm(forms.ModelForm):
    """
    Allows students to report issues related to a specific stop or general service.
    
    It limits the fields to the location (Stop) and a text description, ensuring 
    students provide concise feedback.
    """
    class Meta:
        model = Incident
        fields = ['stop', 'description']
        widgets = {
            'stop': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Describe the issue (e.g. Bus late, unsafe driving, lost item)...'}),
        }

class DriverIncidentForm(forms.ModelForm):
    """
    Allows drivers to report operational issues (traffic, breakdowns) during a trip.
    
    It includes a special boolean field 'mark_delayed' which triggers automatic 
    status updates for the active trip when the form is saved.
    """
    mark_delayed = forms.BooleanField(required=False, label="Mark Trip as Delayed?", widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))

    class Meta:
        model = Incident
        fields = ['description']
        widgets = {
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Describe the incident (e.g. Flat tire, heavy traffic, breakdown)...'}),
        }

class NotificationForm(forms.Form):
    """
    A flexible form for sending system-wide or targeted alerts.
    
    It allows the sender to choose between broadcasting to a role group (e.g., 'All Drivers') 
    or targeting a specific individual user.
    """
    RECIPIENT_CHOICES = (
        ('specific', 'Specific User'),
        ('student', 'All Students'),
        ('driver', 'All Drivers'),
        ('coordinator', 'All Coordinators'),
    )

    title = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'class': 'form-control'}))
    message = forms.CharField(widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}))
    
    target_type = forms.ChoiceField(choices=RECIPIENT_CHOICES, widget=forms.Select(attrs={'class': 'form-select', 'onchange': 'toggleUserField()'}))
    
    specific_user = forms.ModelChoiceField(
        queryset=User.objects.filter(is_active=True).exclude(username='admin'),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )


# ==========================================
# 5. ADMIN TOOLS
# ==========================================

class AdminUserCreationForm(forms.ModelForm):
    """
    Enables administrators to create new accounts with specific roles manually.
    
    It includes password validation fields and overrides the standard save method 
    to handle password hashing correctly.
    """
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}))
    confirm_password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}))

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'role']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'role': forms.Select(attrs={'class': 'form-select'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")

        if password != confirm_password:
            raise forms.ValidationError("Passwords do not match")
        return cleaned_data

class UserManagementForm(forms.ModelForm):
    """
    Allows administrators to modify the details and roles of existing users.
    
    This is used for correcting data entry errors or promoting/demoting user 
    privileges (e.g., changing a user from 'student' to 'coordinator').
    """
    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'role']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'role': forms.Select(attrs={'class': 'form-select'}),
        }