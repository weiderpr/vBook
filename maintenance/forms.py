from django import forms
from .models import Budget, Maintenance
from django.utils.translation import gettext_lazy as _

class MaintenanceForm(forms.ModelForm):
    class Meta:
        model = Maintenance
        fields = ['title', 'description', 'start_date', 'end_date']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'end_date': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'description': forms.Textarea(attrs={'rows': 3, 'style': 'font-size: 0.9rem;'}),
        }

class BudgetForm(forms.ModelForm):
    class Meta:
        model = Budget
        fields = ['provider_name', 'phone', 'value', 'start_date', 'end_date', 'observations']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
            'observations': forms.Textarea(attrs={'rows': 3}),
        }
