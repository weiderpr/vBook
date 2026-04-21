from django import forms
from django.forms import inlineformset_factory
from django.utils.translation import gettext_lazy as _
from .models import ClientComplement, Companion, Reservation

class ClientComplementForm(forms.ModelForm):
    class Meta:
        model = ClientComplement
        fields = [
            'street', 'number', 'complement', 
            'neighborhood', 'city', 'state', 
            'cpf', 'rg', 'car_model', 'car_plate'
        ]
        widgets = {
            'state': forms.Select(attrs={'class': 'form-select'}),
            'complement': forms.TextInput(attrs={'placeholder': _('Apto, Bloco, etc.')}),
            'cpf': forms.TextInput(attrs={'class': 'mask-cpf', 'placeholder': '000.000.000-00'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if not isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.update({'class': 'form-control'})

class CompanionForm(forms.ModelForm):
    class Meta:
        model = Companion
        fields = ['name', 'rg']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': _('Nome do acompanhante'), 'class': 'form-control'}),
            'rg': forms.TextInput(attrs={'placeholder': _('RG'), 'class': 'form-control'}),
        }

class BaseCompanionFormSet(forms.BaseInlineFormSet):
    def __init__(self, *args, **kwargs):
        # We don't pop extra here because we want to use the class-level 'extra' 
        # or we can pass it to the factory dynamically in the view.
        super().__init__(*args, **kwargs)

def get_companion_formset(extra=0):
    return inlineformset_factory(
        Reservation,
        Companion,
        form=CompanionForm,
        formset=BaseCompanionFormSet,
        extra=extra,
        can_delete=False
    )
