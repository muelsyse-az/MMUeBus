from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from .models import User, Route, Stop, Schedule, RouteStop, Vehicle, Driver, Incident, DailyTrip, Notification

User = get_user_model()

class StudentRegistrationForm(UserCreationForm):
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
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'phone']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
        }

# 1. ROUTE FORM (Just the name/description)
class RouteForm(forms.ModelForm):
    class Meta:
        model = Route
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

# 2. STOP FORM (The physical location)
class StopForm(forms.ModelForm):
    class Meta:
        model = Stop
        fields = ['name', 'latitude', 'longitude']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'latitude': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.000001'}),
            'longitude': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.000001'}),
        }

# 3. ROUTE-STOP LINK FORM (Adding a stop to a route)
class RouteStopForm(forms.ModelForm):
    class Meta:
        model = RouteStop
        fields = ['stop', 'sequence_no', 'est_minutes']
        widgets = {
            'stop': forms.Select(attrs={'class': 'form-select'}),
            'sequence_no': forms.NumberInput(attrs={'class': 'form-control'}),
            'est_minutes': forms.NumberInput(attrs={'class': 'form-control'}),
        }

# 4. SCHEDULE FORM
# Replace BOTH ScheduleForm classes with this single merged version:

class ScheduleForm(forms.ModelForm):
    """Allows creating a schedule with dates, assigning Drivers and Vehicles."""
    
    # Custom fields for better display
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
        # COMBINE ALL FIELDS HERE
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

# 1. STUDENT FORM (Can pick a Stop or just describe the issue)
class StudentIncidentForm(forms.ModelForm):
    class Meta:
        model = Incident
        fields = ['stop', 'description']
        widgets = {
            'stop': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Describe the issue (e.g. Bus late, unsafe driving, lost item)...'}),
        }

# 2. DRIVER FORM (Focuses on the Trip/Delay)
class DriverIncidentForm(forms.ModelForm):
    # Driver can optionally mark the trip as "Delayed" immediately
    mark_delayed = forms.BooleanField(required=False, label="Mark Trip as Delayed?", widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))

    class Meta:
        model = Incident
        fields = ['description']
        widgets = {
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Describe the incident (e.g. Flat tire, heavy traffic, breakdown)...'}),
        }

class NotificationForm(forms.Form):
    # Custom choices for targeting
    RECIPIENT_CHOICES = (
        ('specific', 'Specific User'),
        ('student', 'All Students'),
        ('driver', 'All Drivers'),
        ('coordinator', 'All Coordinators'),
    )

    title = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'class': 'form-control'}))
    message = forms.CharField(widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}))
    
    target_type = forms.ChoiceField(choices=RECIPIENT_CHOICES, widget=forms.Select(attrs={'class': 'form-select', 'onchange': 'toggleUserField()'}))
    
    # Optional field: Only used if target_type is 'specific'
    specific_user = forms.ModelChoiceField(
        queryset=User.objects.filter(is_active=True).exclude(username='admin'),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

class ManualBookingForm(forms.Form):
    """Allows adding a student by username manually."""
    student_username = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter Student ID/Username'}),
        label="Student Username"
    )

class VehicleForm(forms.ModelForm):
    class Meta:
        model = Vehicle
        fields = ['plate_no', 'type', 'capacity']
        widgets = {
            'plate_no': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. ABC-1234'}),
            'type': forms.Select(attrs={'class': 'form-select'}),
            'capacity': forms.NumberInput(attrs={'class': 'form-control'}),
        }

class VehicleCapacityForm(forms.ModelForm):
    """Quick edit for bus capacity."""
    class Meta:
        model = Vehicle
        fields = ['capacity']
        widgets = {
            'capacity': forms.NumberInput(attrs={'class': 'form-control'})
        }

class UserManagementForm(forms.ModelForm):
    """Admin form to edit any user's details and role."""
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

# 1. ADMIN USER CREATION FORM
class AdminUserCreationForm(forms.ModelForm):
    """Allows Admins to create new users with a password and role."""
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