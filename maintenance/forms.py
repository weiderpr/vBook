from django import forms
from .models import Budget, Maintenance
from django.utils.translation import gettext_lazy as _

class MaintenanceForm(forms.ModelForm):
    class Meta:
        model = Maintenance
        fields = ['title', 'description', 'specification', 'start_date', 'end_date', 'services']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'end_date': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'description': forms.Textarea(attrs={'rows': 3, 'style': 'font-size: 0.9rem;'}),
            'services': forms.CheckboxSelectMultiple(),
        }

    def __init__(self, *args, **kwargs):
        property_obj = kwargs.pop('property', None)
        super().__init__(*args, **kwargs)
        
        if property_obj:
            from properties.models import PropertySpecification
            self.fields['specification'].queryset = PropertySpecification.objects.filter(property=property_obj)
            self.fields['specification'].empty_label = _("Sem especificação / Equipamento geral")
            self.fields['specification'].required = False
            self.fields['specification'].widget.attrs.update({'class': 'form-select'})
        else:
            from properties.models import PropertySpecification
            self.fields['specification'].queryset = PropertySpecification.objects.none()
            self.fields['specification'].empty_label = _("Sem especificação / Equipamento geral")
            self.fields['specification'].required = False

class BudgetForm(forms.ModelForm):
    class Meta:
        model = Budget
        fields = ['provider_name', 'phone', 'value', 'start_date', 'end_date', 'observations']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
            'observations': forms.Textarea(attrs={'rows': 3}),
        }
