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

from .models import Plan, SystemSetting

class SystemSettingForm(forms.ModelForm):
    class Meta:
        model = SystemSetting
        fields = [
            'pix_gateway', 'card_gateway',
            'mercadopago_public_key', 'mercadopago_access_token', 'mercadopago_webhook_secret',
            'stripe_public_key', 'stripe_secret_key', 'stripe_webhook_secret'
        ]
        widgets = {
            'pix_gateway': forms.Select(attrs={'class': 'form-control'}),
            'card_gateway': forms.Select(attrs={'class': 'form-control'}),
            'mercadopago_public_key': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'APP_USR-...'}),
            'mercadopago_access_token': forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'APP_USR-...', 'render_value': True}),
            'mercadopago_webhook_secret': forms.PasswordInput(attrs={'class': 'form-control', 'render_value': True}),
            'stripe_public_key': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'pk_live_...'}),
            'stripe_secret_key': forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'sk_live_...', 'render_value': True}),
            'stripe_webhook_secret': forms.PasswordInput(attrs={'class': 'form-control', 'render_value': True}),
        }

class PlanForm(forms.ModelForm):
    base_value = forms.CharField(
        label=_("Valor base"),
        widget=forms.TextInput(attrs={'placeholder': '0,00', 'class': 'money-mask'})
    )

    class Meta:
        model = Plan
        fields = ['description', 'periodicity', 'base_value', 'duration_days', 'is_active', 'requires_payment']
        widgets = {
            'periodicity': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            if field not in ['is_active', 'requires_payment']:
                current_classes = self.fields[field].widget.attrs.get('class', '')
                self.fields[field].widget.attrs['class'] = f"{current_classes} form-control".strip()
        
        if self.instance and self.instance.pk:
            self.initial['base_value'] = f"{self.instance.base_value:.2f}".replace('.', ',')

    def clean_base_value(self):
        value = self.cleaned_data.get('base_value')
        if not value: return 0
        if isinstance(value, str):
            import re
            clean_value = re.sub(r'[^\d.,]', '', value)
            if ',' in clean_value:
                clean_value = clean_value.replace('.', '').replace(',', '.')
            try:
                from decimal import Decimal
                return Decimal(clean_value)
            except:
                raise forms.ValidationError(_("Valor inválido."))
        return value
