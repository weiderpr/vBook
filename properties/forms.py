from django import forms
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from .models import Property, PropertyCost

class CustomClearableFileInput(forms.ClearableFileInput):
    template_name = 'properties/widgets/clearable_file_input.html'

class PropertyForm(forms.ModelForm):
    acquisition_value = forms.CharField(label=_("Valor da aquisição"))

    class Meta:
        model = Property
        fields = [
            'name', 'description', 'image', 'signature', 'address_street', 'address_number',
            'address_complement', 'address_city', 'address_state',
            'acquisition_date', 'acquisition_value', 'condo_phone', 'share_client_phone'
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
        self.fields['acquisition_value'].widget.attrs.update({'placeholder': '0,00', 'class': 'money-mask'})
        
        if self.instance and self.instance.pk and self.instance.acquisition_value:
            self.initial['acquisition_value'] = f"{self.instance.acquisition_value:.2f}".replace('.', ',')

    def clean_acquisition_value(self):
        value = self.cleaned_data.get('acquisition_value')
        
        if not value:
            return 0
            
        if isinstance(value, str):
            # Remove currency symbols and other non-numeric characters except separators
            import re
            clean_value = re.sub(r'[^\d.,]', '', value)
            
            if ',' in clean_value:
                # PT-BR format (e.g. 1.234,56)
                clean_value = clean_value.replace('.', '').replace(',', '.')
            # If no comma, we assume it's already in decimal format (e.g. 1234.56)
            
            try:
                from decimal import Decimal
                return Decimal(clean_value)
            except (ValueError, ArithmeticError):
                raise forms.ValidationError(_("Valor inválido."))
        return value

class PropertyCostForm(forms.ModelForm):
    amount = forms.CharField(label=_("Valor"))

    class Meta:
        model = PropertyCost
        fields = ['name', 'amount', 'amount_type', 'frequency', 'month', 'year', 'recipient', 'provider', 'description']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 2, 'placeholder': _("Opcional: Detalhes sobre este custo")}),
            'name': forms.TextInput(attrs={'placeholder': _("Ex: Condomínio, IPTU, Limpeza")}),
            'provider': forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['amount'].widget.attrs.update({'placeholder': '0,00'})
        
        # Set defaults for month and year
        today = timezone.now()
        self.fields['month'].initial = today.month
        self.fields['year'].initial = today.year
        self.fields['year'].widget.attrs.update({'placeholder': today.year})

    def clean_amount(self):
        value = self.cleaned_data.get('amount')
        
        if not value:
            return 0
            
        if isinstance(value, str):
            # Remove currency symbols and other non-numeric characters except separators
            import re
            clean_value = re.sub(r'[^\d.,]', '', value)
            
            if ',' in clean_value:
                # PT-BR format (e.g. 1.234,56)
                clean_value = clean_value.replace('.', '').replace(',', '.')
            # If no comma, we assume it's already in decimal format (e.g. 1234.56)
            
            try:
                from decimal import Decimal
                return Decimal(clean_value)
            except (ValueError, ArithmeticError):
                raise forms.ValidationError(_("Valor inválido."))
        return value

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

class PropertyInstructionsForm(forms.ModelForm):
    class Meta:
        model = Property
        fields = ['reservation_instructions']
        widgets = {
            'reservation_instructions': forms.HiddenInput(),
        }

class PropertyAuthorizationForm(forms.ModelForm):
    class Meta:
        model = Property
        fields = ['authorization_template']
        widgets = {
            'authorization_template': forms.HiddenInput(),
        }

from .models import Service, ServiceProvider

class ServiceForm(forms.ModelForm):
    class Meta:
        model = Service
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': _("Ex: Limpeza, Piscineiro, Elétrica"), 'class': 'form-control'})
        }

class ServiceProviderForm(forms.ModelForm):
    class Meta:
        model = ServiceProvider
        fields = ['name', 'cpf', 'phone', 'services', 'photo', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': _("Nome completo do prestador"), 'class': 'form-control'}),
            'cpf': forms.TextInput(attrs={'placeholder': _("000.000.000-00"), 'class': 'cpf-mask form-control'}),
            'phone': forms.TextInput(attrs={'placeholder': _("(00) 00000-0000"), 'class': 'phone-mask form-control'}),
            'services': forms.CheckboxSelectMultiple(attrs={'class': 'services-checkbox-list'}),
            'photo': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['services'].queryset = Service.objects.filter(user=user)
