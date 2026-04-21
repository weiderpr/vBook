from django import forms
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from .models import Property, PropertyCost

class CustomClearableFileInput(forms.ClearableFileInput):
    template_name = 'properties/widgets/clearable_file_input.html'

class PropertyForm(forms.ModelForm):
    class Meta:
        model = Property
        fields = [
            'name', 'description', 'image', 'signature', 'address_street', 'address_number',
            'address_complement', 'address_city', 'address_state',
            'acquisition_date', 'acquisition_value', 'condo_phone'
        ]
        widgets = {
            'acquisition_date': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'description': forms.Textarea(attrs={'rows': 4}),
            'image': CustomClearableFileInput(),
            'signature': CustomClearableFileInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Adding placeholders for better UX
        self.fields['name'].widget.attrs.update({'placeholder': _("Ex: Apartamento em Ipanema")})
        self.fields['address_street'].widget.attrs.update({'placeholder': _("Rua, Avenida, etc.")})
        self.fields['address_city'].widget.attrs.update({'placeholder': _("Sua cidade")})
        self.fields['address_state'].widget.attrs.update({'placeholder': _("Seu estado")})
        self.fields['condo_phone'].widget.attrs.update({'placeholder': _("(00) 00000-0000"), 'class': 'phone-mask'})
        self.fields['acquisition_value'].widget.attrs.update({'step': '0.01'})

class PropertyCostForm(forms.ModelForm):
    class Meta:
        model = PropertyCost
        fields = ['name', 'amount', 'amount_type', 'frequency', 'month', 'year', 'recipient', 'description']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 2, 'placeholder': _("Opcional: Detalhes sobre este custo")}),
            'name': forms.TextInput(attrs={'placeholder': _("Ex: Condomínio, IPTU, Limpeza")}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['amount'].widget.attrs.update({'step': '0.01', 'placeholder': '0,00'})
        
        # Set defaults for month and year
        today = timezone.now()
        self.fields['month'].initial = today.month
        self.fields['year'].initial = today.year
        self.fields['year'].widget.attrs.update({'placeholder': today.year})

    def clean(self):
        cleaned_data = super().clean()
        frequency = cleaned_data.get('frequency')
        
        if frequency == 'per_booking':
            # For per-booking costs, we don't need month or year
            cleaned_data['month'] = None
            cleaned_data['year'] = None
        elif frequency == 'yearly':
            # For yearly costs, we only need year
            cleaned_data['month'] = None
            if not cleaned_data.get('year'):
                self.add_error('year', _("O ano é obrigatório para custos anuais."))
        elif frequency == 'monthly':
            # For monthly costs, both are needed
            if not cleaned_data.get('month'):
                self.add_error('month', _("O mês é obrigatório para custos mensais."))
            if not cleaned_data.get('year'):
                self.add_error('year', _("O ano é obrigatório para custos mensais."))
        
        return cleaned_data
