from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User, Route, Stop, Schedule, RouteStop, Vehicle, Driver, Incident, DailyTrip, Notification

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
class ScheduleForm(forms.ModelForm):
    class Meta:
        model = Schedule
        fields = ['route', 'days_of_week', 'start_time', 'end_time', 'frequency_min', 'valid_from', 'valid_to', 'default_driver', 'default_vehicle']
        widgets = {
            'route': forms.Select(attrs={'class': 'form-select'}),
            'days_of_week': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Mon,Tue,Wed'}),
            'start_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'frequency_min': forms.NumberInput(attrs={'class': 'form-control'}),
            'valid_from': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'valid_to': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'default_driver': forms.Select(attrs={'class': 'form-select'}),
            'default_vehicle': forms.Select(attrs={'class': 'form-select'}),
        }

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