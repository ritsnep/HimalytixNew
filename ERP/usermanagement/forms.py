# usermanagement/forms.py
from django import forms
from .models import CustomUser, Module, Entity, Permission, Role, UserRole
from django.contrib.auth.forms import UserCreationForm

from django import forms
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
# usermanagement/forms.py
from django.contrib.auth.forms import AuthenticationForm
from django import forms

class DasonLoginForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget = forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your username',
            'id': 'input-username'
        })
        self.fields['password'].widget = forms.PasswordInput(attrs={
            'class': 'form-control pe-5',
            'placeholder': 'Enter your password',
            'id': 'password-input'
        })
        self.fields['otp_token'] = forms.CharField(
            required=False,
            widget=forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'MFA code (if enabled)',
                'id': 'otp-input'
            })
        )

    def clean(self):
        try:
            return super().clean()
        except forms.ValidationError as exc:
            failure_reason = getattr(getattr(self, 'request', None), '_auth_failure_reason', None)
            if failure_reason == 'mfa_required':
                raise forms.ValidationError('Enter the authentication code from your authenticator app.', code='mfa_required')
            if failure_reason == 'mfa_invalid':
                raise forms.ValidationError('Invalid authentication code.', code='mfa_invalid')
            if failure_reason == 'account_locked':
                raise forms.ValidationError('Your account is locked. Please try again later.', code='account_locked')
            raise exc


class LoginForm(forms.Form):
    username = forms.CharField(max_length=255)
    password = forms.CharField(max_length=255, widget=forms.PasswordInput)

    def clean(self):
        username = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')
        user = authenticate(username=username, password=password)
        if not user:
            raise forms.ValidationError('Invalid username or password')
        return self.cleaned_data
class CustomUserCreationForm(UserCreationForm):
    class Meta:
        model = CustomUser
        fields = ('username', 'email', 'full_name', 'role', 'organization')

class ModuleForm(forms.ModelForm):
    class Meta:
        model = Module
        fields = '__all__'

class EntityForm(forms.ModelForm):
    class Meta:
        model = Entity
        fields = '__all__'



class RoleForm(forms.ModelForm):
    class Meta:
        model = Role
        fields = [
            'name',
            'code',
            'description',
            'organization',
            'permissions',
            'is_system',
            'is_active',
        ]


class PermissionForm(forms.ModelForm):
    class Meta:
        model = Permission
        fields = [
            'name',
            'codename',
            'description',
            'module',
            'entity',
            'action',
            'is_active',
        ]


class UserRoleForm(forms.ModelForm):
    class Meta:
        model = UserRole
        fields = [
            'user',
            'role',
            'organization',
            'is_active',
        ]
