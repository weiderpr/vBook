from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import CustomUser

class UserRegistrationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = CustomUser
        fields = ('email', 'full_name')

class UserLoginForm(AuthenticationForm):
    username = forms.EmailField(label="E-mail", widget=forms.EmailInput(attrs={'autofocus': True}))

class UserProfileForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ('full_name', 'profile_picture')
