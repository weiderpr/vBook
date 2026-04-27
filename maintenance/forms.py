from django import forms
from .models import Budget
from django.utils.translation import gettext_lazy as _

class BudgetForm(forms.ModelForm):
    class Meta:
        model = Budget
        fields = ['provider_name', 'phone', 'value', 'start_date', 'end_date', 'observations']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
            'observations': forms.Textarea(attrs={'rows': 3}),
        }
