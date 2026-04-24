from django import forms
from django.utils.translation import gettext_lazy as _
from properties.models import Service
from .models import Condo

class ServiceCategoryForm(forms.ModelForm):
    class Meta:
        model = Service
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Ex: Limpeza, Elétrica, Hidráulica...')
            }),
        }

class CondoForm(forms.ModelForm):
    class Meta:
        model = Condo
        fields = [
            'name', 'address_street', 'address_number', 'address_neighborhood',
            'address_city', 'address_state', 'requires_authorization', 'authorization_template'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('Ex: Condomínio Solar das Águas')}),
            'address_street': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('Rua...')}),
            'address_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('123')}),
            'address_neighborhood': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('Bairro...')}),
            'address_city': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('Cidade...')}),
            'address_state': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('UF'), 'maxlength': '2'}),
            'requires_authorization': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'authorization_template': forms.Textarea(attrs={'id': 'editor'}),
        }
