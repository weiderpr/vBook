from django import forms
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from .models import Property, PropertyCost

class CustomClearableFileInput(forms.ClearableFileInput):
    template_name = 'properties/widgets/clearable_file_input.html'

class PropertyForm(forms.ModelForm):
    acquisition_value = forms.CharField(
        label=_("Valor da aquisição"),
        widget=forms.TextInput(attrs={'placeholder': '0,00', 'class': 'money-mask'})
    )

    class Meta:
        model = Property
        fields = [
            'name', 'description', 'image', 'signature', 'address_street', 'address_number',
            'address_complement', 'address_city', 'address_state',
            'acquisition_date', 'acquisition_value', 'condo_phone', 'share_client_phone',
            'default_checkin_time', 'default_checkout_time', 'color'
        ]
        widgets = {
            'acquisition_date': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'default_checkin_time': forms.TimeInput(attrs={'type': 'time'}),
            'default_checkout_time': forms.TimeInput(attrs={'type': 'time'}),
            'color': forms.TextInput(attrs={'type': 'color'}),
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
        
        # Ensure classes are preserved if already set
        current_classes = self.fields['acquisition_value'].widget.attrs.get('class', '')
        if 'money-mask' not in current_classes:
            self.fields['acquisition_value'].widget.attrs['class'] = f"{current_classes} money-mask".strip()
        
        self.fields['acquisition_value'].widget.attrs.update({'placeholder': '0,00'})
        
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
    amount = forms.CharField(
        label=_("Valor"),
        widget=forms.TextInput(attrs={'placeholder': '0,00', 'class': 'money-mask'})
    )

    class Meta:
        model = PropertyCost
        fields = ['name', 'amount', 'amount_type', 'frequency', 'payment_date', 'month', 'year', 'recipient', 'provider', 'description']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 2, 'placeholder': _("Opcional: Detalhes sobre este custo")}),
            'name': forms.TextInput(attrs={'placeholder': _("Ex: Condomínio, IPTU, Limpeza")}),
            'provider': forms.HiddenInput(),
            'payment_date': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'amount_type': forms.HiddenInput(),
            'month': forms.HiddenInput(),
            'year': forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Ensure classes are preserved
        current_classes = self.fields['amount'].widget.attrs.get('class', '')
        if 'money-mask' not in current_classes:
            self.fields['amount'].widget.attrs['class'] = f"{current_classes} money-mask".strip()
            
        self.fields['amount'].widget.attrs.update({'placeholder': '0,00'})
        
        # Set default amount_type to fixed
        self.fields['amount_type'].initial = 'fixed'
        
        # Set default payment_date to today if creating new
        if not self.instance.pk:
            self.fields['payment_date'].initial = timezone.now().date()

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
        payment_date = cleaned_data.get('payment_date')
        
        if frequency != 'per_booking':
            if not payment_date:
                self.add_error('payment_date', _("A data do pagamento é obrigatória."))
            else:
                # Sync month and year for backward compatibility and aggregation
                cleaned_data['month'] = payment_date.month
                cleaned_data['year'] = payment_date.year
        else:
            # For per-booking costs, we don't need payment_date
            cleaned_data['month'] = None
            cleaned_data['year'] = None
            cleaned_data['payment_date'] = None
        
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
