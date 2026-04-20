from decimal import Decimal
from django import forms
from django.utils.translation import gettext_lazy as _
from .models import Reservation

class ReservationForm(forms.ModelForm):
    total_value = forms.CharField(label=_("Valor total"))
    
    class Meta:
        model = Reservation
        fields = [
            'start_date', 'end_date', 'client_name', 
            'client_phone', 'guests_count', 'total_value', 'notes'
        ]
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'end_date': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')

        if start_date and end_date and end_date < start_date:
            raise forms.ValidationError(
                _("A data final não pode ser anterior à data inicial.")
            )
        return cleaned_data

    def clean_total_value(self):
        value = self.cleaned_data.get('total_value')
        if isinstance(value, str):
            # Remove "R$", dots (delimiter) and replace comma with dot
            clean_value = value.replace('R$', '').replace('.', '').replace(',', '.').strip()
            try:
                return Decimal(clean_value)
            except (ValueError, ArithmeticError):
                raise forms.ValidationError(_("Valor inválido."))
        return value

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['client_name'].widget.attrs.update({'placeholder': _("Nome completo do hóspede")})
        self.fields['client_phone'].widget.attrs.update({'placeholder': _("(00) 00000-0000")})
        self.fields['guests_count'].widget.attrs.update({'placeholder': '1', 'min': '1'})
        self.fields['total_value'].widget.attrs.update({'step': '0.01'})
