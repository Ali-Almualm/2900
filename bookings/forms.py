# bookings/forms.py
from django import forms
from .models import Booking, MatchAvailability, Competition, CompetitionMatch, MatchParticipant
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.utils import timezone # Import timezone
import datetime # Import datetime

class BookingForm(forms.ModelForm):
    class Meta:
        model = Booking
        # omit start_time and end_time if you don’t want the user to type them
        fields = ['user_id', 'name', 'booking_type']


class registrationform(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']
class loginform(AuthenticationForm):
    class Meta:
        model = User
        fields = ['username', 'password']

class MatchAvailabilityForm(forms.ModelForm):
    class Meta:
        # Use renamed model
        model = MatchAvailability
        fields = ['booking_type', 'start_time', 'end_time', 'is_available']
        widgets = {
            'start_time': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'end_time': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }

class CompetitionForm(forms.ModelForm):
    class Meta:
        model = Competition
        fields = ['activity_type', 'start_time', 'end_time', 'max_joiners']
        widgets = {
            'start_time': forms.DateTimeInput(
                attrs={
                    'type': 'datetime-local',
                    'step': 900  # 15 minutes * 60 seconds
                },
                format='%Y-%m-%dT%H:%M'
            ),
            'end_time': forms.DateTimeInput(
                attrs={
                    'type': 'datetime-local',
                    'step': 900  # 15 minutes * 60 seconds
                },
                format='%Y-%m-%dT%H:%M'
            ),
            'activity_type': forms.Select(), # Choices are set by the model field
        }
        help_texts = {
            'start_time': 'Select a time on a 15-minute interval (e.g., 10:00, 10:15, 10:30).',
            'end_time': 'Select a time on a 15-minute interval.',
        }

    def clean_start_time(self):
        start_time = self.cleaned_data.get("start_time")
        if start_time:
            if start_time.minute % 15 != 0:
                raise forms.ValidationError("Start time must be in 15-minute intervals (e.g., HH:00, HH:15, HH:30, HH:45).")
            # Optional: Prevent past times if not already handled by browser/widget
            if start_time < timezone.now():
                 raise forms.ValidationError("Start time cannot be in the past.")
        return start_time

    def clean_end_time(self):
        end_time = self.cleaned_data.get("end_time")
        if end_time:
            if end_time.minute % 15 != 0:
                raise forms.ValidationError("End time must be in 15-minute intervals (e.g., HH:00, HH:15, HH:30, HH:45).")
        return end_time

    def clean(self):
        cleaned_data = super().clean()
        start_time = cleaned_data.get("start_time")
        end_time = cleaned_data.get("end_time")
        activity_type = cleaned_data.get("activity_type")

        if start_time and end_time:
            if end_time <= start_time:
                raise forms.ValidationError("End time must be after start time.")
            
            # Competition duration validation (e.g., min 30 mins, max 4 hours)
            duration = end_time - start_time
            if duration < datetime.timedelta(minutes=30):
                raise forms.ValidationError("Competition duration must be at least 30 minutes.")
            if duration > datetime.timedelta(hours=4): # Example max duration
                raise forms.ValidationError("Competition duration cannot exceed 4 hours.")


            # Check for conflicts with existing bookings
            conflicting_bookings = Booking.objects.filter(
                booking_type=activity_type,
                start_time__lt=end_time,
                end_time__gt=start_time
            )
            if conflicting_bookings.exists():
                # Check if we are updating an existing competition
                instance_id = self.instance.pk if self.instance else None
                # Exclude self if updating (this logic is more for a Competition model's clean method)
                # For a create form, any conflict is usually an error.
                raise forms.ValidationError(
                    f"This time slot conflicts with an existing booking for {activity_type}."
                )

            # Check for conflicts with existing competitions
            conflicting_competitions = Competition.objects.filter(
                activity_type=activity_type,
                start_time__lt=end_time,
                end_time__gt=start_time
            )
            # Exclude self if updating an existing competition
            if self.instance and self.instance.pk:
                conflicting_competitions = conflicting_competitions.exclude(pk=self.instance.pk)

            if conflicting_competitions.exists():
                 raise forms.ValidationError(
                    f"This time slot conflicts with an existing competition for {activity_type}."
                )
        return cleaned_data
    

class CompetitionMatchForm(forms.ModelForm):
    class Meta:
        model = CompetitionMatch
        # Specify fields the creator should set when creating a match shell
        fields = ['match_type', 'round_number', 'match_datetime']
        widgets = {
            # Use a standard select dropdown for match_type
            'match_type': forms.Select(), # Uses choices from the model field
            # Use HTML5 datetime-local input for easier picking
            'match_datetime': forms.DateTimeInput(
                attrs={'type': 'datetime-local'},
                format='%Y-%m-%dT%H:%M' # Ensure format matches HTML5 input
            ),
            # round_number is a simple number input
            'round_number': forms.NumberInput(attrs={'min': '1'}),
        }
        labels = {
            'match_type': 'Match Format',
            'round_number': 'Round (Optional)',
            'match_datetime': 'Specific Time (Optional)',
        }
        help_texts = {
            'match_datetime': 'Leave blank if the match can happen anytime during the competition window.',
            'round_number': 'Useful for tournament brackets.',
        }

    def __init__(self, *args, **kwargs):
        # Allow passing competition object for validation later if needed
        self.competition = kwargs.pop('competition', None)
        super().__init__(*args, **kwargs)
        # Make fields not strictly required if they are optional in the model
        # (null=True, blank=True)
        self.fields['round_number'].required = False
        self.fields['match_datetime'].required = False

    def clean_match_datetime(self):
        # Optional Validation: Ensure match time is within competition time
        match_time = self.cleaned_data.get('match_datetime')
        if match_time and self.competition:
            # Make timezone-aware if necessary based on your settings
            if match_time < self.competition.start_time or match_time > self.competition.end_time:
                raise forms.ValidationError(
                    "Match time must be within the competition's start and end time."
                )
        return match_time
class MatchParticipantForm(forms.ModelForm):
    # We'll customize the 'user' field's choices in the view/formset factory
    class Meta:
        model = MatchParticipant
        fields = ['user', 'team'] # Only include fields to be set in this form

    def __init__(self, *args, **kwargs):
        # Get eligible users passed from the view
        eligible_users_queryset = kwargs.pop('eligible_users', None)
        match_type = kwargs.pop('match_type', None)
        super().__init__(*args, **kwargs)

        if eligible_users_queryset is not None:
            self.fields['user'].queryset = eligible_users_queryset
            self.fields['user'].label = "Participant"

        # Customize 'team' field based on match_type
        if match_type == '2v2':
            self.fields['team'].required = True
            self.fields['team'].label = "Team (e.g., A or B)"
            self.fields['team'].widget = forms.TextInput(attrs={'placeholder': 'A or B'})
        else:
            # Hide or disable team field if not 2v2 (optional, can also be done in template)
            self.fields['team'].required = False
            self.fields['team'].widget = forms.HiddenInput() # Hide it completely
            # Or disable it:
            # self.fields['team'].disabled = True
            # self.fields['team'].widget.attrs['placeholder'] = 'N/A for this match type'


class MatchResultForm(forms.ModelForm):
    # Define choices for simplified 1v1/2v2 result entry
    RESULT_CHOICES_SIMPLE = [
        # Ensure 'pending' is a valid choice if used as default
        ('', '---------'), # Add blank choice
        ('pending', 'Pending'),
        ('win', 'Win'),
        ('loss', 'Loss'),
        ('draw', 'Draw'),
    ]
    result_simple = forms.ChoiceField(
        choices=RESULT_CHOICES_SIMPLE,
        required=False, # Validation happens in the view based on match type
        label="Result (Win/Loss/Draw)"
    )
    # Rank/Score field for FFA
    result_rank_score = forms.IntegerField(
        required=False, # Validation happens in the view
        label="Rank/Score",
        widget=forms.NumberInput(attrs={'min': '1'}) # Basic HTML5 validation
    )

    class Meta:
        model = MatchParticipant
        # Include fields needed for display + the custom fields
        # We don't actually save directly from these custom fields in the view,
        # but defining them helps structure the form.
        # We only *really* need the fields we render or use in __init__.
        # Let's just list fields needed for __init__ checks or direct rendering.
        fields = ['user', 'team'] # Keep base fields needed to disable them

    def __init__(self, *args, **kwargs):
        match_type = kwargs.pop('match_type', None)
        # Pop instance if passed by formset, needed for initial values
        instance = kwargs.get('instance')
        super().__init__(*args, **kwargs)

        # Make user and team read-only / disabled in the form
        if 'user' in self.fields:
            self.fields['user'].disabled = True
        if 'team' in self.fields:
            self.fields['team'].disabled = True
            self.fields['team'].required = False # Ensure not required even if disabled


        # Add the custom fields explicitly if not inherited via Meta fields
        if 'result_simple' not in self.fields:
             self.fields['result_simple'] = forms.ChoiceField(
                choices=self.RESULT_CHOICES_SIMPLE, required=False, label="Result (Win/Loss/Draw)")
        if 'result_rank_score' not in self.fields:
             self.fields['result_rank_score'] = forms.IntegerField(
                required=False, label="Rank/Score", widget=forms.NumberInput(attrs={'min': '1'}))


        # Configure visibility/requirement based on match type
        if match_type == 'ffa':
            self.fields['result_simple'].widget = forms.HiddenInput()
            self.fields['result_simple'].required = False
            self.fields['result_rank_score'].required = True # Make required for FFA
            self.fields['result_rank_score'].label = "Rank (e.g., 1, 2, 3)" # Or Score
            # Set initial value for rank/score if instance exists
            if instance and instance.pk and instance.result_type in ['rank', 'score']:
                 self.initial['result_rank_score'] = instance.result_value

        elif match_type in ['1v1', '2v2']:
            self.fields['result_rank_score'].widget = forms.HiddenInput()
            self.fields['result_rank_score'].required = False
            self.fields['result_simple'].required = True # Make required for 1v1/2v2
            # Pre-select based on existing result_type if available
            if instance and instance.pk:
                 # Map saved result_type back to the simple choice field
                 if instance.result_type in ['win', 'loss', 'draw']:
                      self.initial['result_simple'] = instance.result_type
                 else:
                      # Default to blank or pending if existing result isn't valid simple choice
                      self.initial['result_simple'] = '' # Or 'pending' if that's a valid choice value
        else: # Should not happen, but hide both if type is unknown
            self.fields['result_simple'].widget = forms.HiddenInput()
            self.fields['result_simple'].required = False
            self.fields['result_rank_score'].widget = forms.HiddenInput()
            self.fields['result_rank_score'].required = False

