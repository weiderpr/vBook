from django import forms
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
import os
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
            'name', 'condo', 'description', 'image', 'signature', 'address_street', 'address_number',
            'address_neighborhood', 'address_complement', 'address_city', 'address_state',
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
        self.fields['address_neighborhood'].widget.attrs.update({'placeholder': _("Bairro")})
        self.fields['address_city'].widget.attrs.update({'placeholder': _("Sua cidade")})
        self.fields['address_state'].widget.attrs.update({'placeholder': _("Seu estado")})
        self.fields['condo_phone'].widget.attrs.update({'placeholder': _("(00) 00000-0000"), 'class': 'phone-mask'})
        self.fields['condo'].empty_label = _("Sem condomínio (Independente)")
        self.fields['condo'].widget.attrs.update({'class': 'form-select'})
        
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

    month = forms.CharField(required=False, widget=forms.HiddenInput(), label=_("Mês (Ajuste)"))
    year = forms.CharField(required=False, widget=forms.HiddenInput(), label=_("Ano (Ajuste)"))

    class Meta:
        model = PropertyCost
        fields = ['name', 'amount', 'amount_type', 'frequency', 'payment_date', 'month', 'year', 'recipient', 'provider', 'description']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 2, 'placeholder': _("Opcional: Detalhes sobre este custo")}),
            'name': forms.TextInput(attrs={'placeholder': _("Ex: Condomínio, IPTU, Limpeza")}),
            'provider': forms.HiddenInput(),
            'payment_date': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'amount_type': forms.HiddenInput(),
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
            self.fields['payment_date'].initial = timezone.localtime(timezone.now()).date()

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
        
        # Handle string inputs for month and year
        def to_int_or_none(val):
            if val in [None, '', '0', 'None']:
                return None
            try:
                return int(str(val).replace('.', '').replace(',', ''))
            except (ValueError, TypeError):
                return None

        m = to_int_or_none(cleaned_data.get('month'))
        y = to_int_or_none(cleaned_data.get('year'))

        if frequency != 'per_booking':
            if not payment_date:
                self.add_error('payment_date', _("A data do pagamento é obrigatória."))
            else:
                # Sync month and year from payment_date
                cleaned_data['month'] = payment_date.month
                cleaned_data['year'] = payment_date.year
        else:
            # For per-booking costs, we don't need payment_date, month or year
            cleaned_data['month'] = None
            cleaned_data['year'] = None
            cleaned_data['payment_date'] = None
        
        # Final safety check
        if frequency != 'per_booking' and not cleaned_data.get('month'):
            cleaned_data['month'] = m
            cleaned_data['year'] = y
            
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

from .models import Property, PropertyCost, Service, ServiceProvider, PropertyDocument


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
        # Services are now global, no need to filter by user
        self.fields['services'].queryset = Service.objects.all()

class PropertyDocumentForm(forms.ModelForm):
    class Meta:
        model = PropertyDocument
        fields = ['name', 'document_date', 'description', 'file']
        widgets = {
            'document_date': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'description': forms.Textarea(attrs={'rows': 2, 'placeholder': _("Opcional: Detalhes sobre este documento")}),
            'name': forms.TextInput(attrs={'placeholder': _("Ex: Escritura, Contrato de Compra e Venda")}),
            'file': forms.FileInput(attrs={'accept': 'application/pdf,image/*'}),
        }

    def clean_file(self):
        file = self.cleaned_data.get('file')
        if file:
            extension = os.path.splitext(file.name)[1].lower()
            size_mb = file.size / 1024 / 1024
            
            if extension in ['.jpg', '.jpeg', '.png', '.webp']:
                if size_mb > 2:
                    raise forms.ValidationError(_("Imagens não podem ser maiores que 2MB (elas serão compactadas automaticamente)."))
            elif extension == '.pdf':
                if size_mb > 10:
                    raise forms.ValidationError(_("Arquivos PDF não podem ser maiores que 10MB."))
            else:
                if size_mb > 5:
                    raise forms.ValidationError(_("O arquivo não pode ser maior que 5MB."))
        return file

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            current_classes = field.widget.attrs.get('class', '')
            field.widget.attrs.update({'class': f'{current_classes} form-control'.strip()})
        
        # Ensure description follows the same pattern without breaking colors
        self.fields['description'].widget.attrs.update({
            'rows': 3,
            'placeholder': _("Opcional: Detalhes sobre este documento"),
            'maxlength': '500'
        })
        self.fields['name'].widget.attrs.update({
            'maxlength': '255'
        })


from .models import PropertySpecification, PropertySpecificationPhoto

class PropertySpecificationForm(forms.ModelForm):
    purchase_value = forms.CharField(
        required=False,
        label=_("Valor da compra"),
        widget=forms.TextInput(attrs={'placeholder': '0,00', 'class': 'money-mask'})
    )

    class Meta:
        model = PropertySpecification
        fields = [
            'description', 'brand', 'model', 'dimensions',
            'purchase_location', 'purchase_date', 'purchase_value', 'product_link'
        ]
        widgets = {
            'purchase_date': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'product_link': forms.URLInput(attrs={'placeholder': 'https://...', 'class': 'form-control'}),
            'description': forms.TextInput(attrs={'placeholder': _("Ex: Geladeira Frost Free"), 'class': 'form-control'}),
            'brand': forms.TextInput(attrs={'placeholder': _("Ex: Brastemp"), 'class': 'form-control'}),
            'model': forms.TextInput(attrs={'placeholder': _("Ex: BRM44HB"), 'class': 'form-control'}),
            'dimensions': forms.TextInput(attrs={'placeholder': _("Ex: 176x62x69 cm"), 'class': 'form-control'}),
            'purchase_location': forms.TextInput(attrs={'placeholder': _("Ex: Magazine Luiza"), 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name != 'purchase_value':
                current_classes = field.widget.attrs.get('class', '')
                field.widget.attrs.update({'class': f'{current_classes} form-control'.strip()})
        
        # Ensure purchase_value is formatted for initial display
        if self.instance and self.instance.pk and self.instance.purchase_value:
            self.initial['purchase_value'] = f"{self.instance.purchase_value:.2f}".replace('.', ',')

    def clean_purchase_value(self):
        value = self.cleaned_data.get('purchase_value')
        if not value:
            return None
        if isinstance(value, str):
            import re
            clean_value = re.sub(r'[^\d.,]', '', value)
            if ',' in clean_value:
                clean_value = clean_value.replace('.', '').replace(',', '.')
            try:
                from decimal import Decimal
                return Decimal(clean_value)
            except (ValueError, ArithmeticError):
                raise forms.ValidationError(_("Valor inválido."))
        return value


from .models import PropertyChecklist, PropertyChecklistItem

class PropertyChecklistForm(forms.ModelForm):
    class Meta:
        model = PropertyChecklist
        fields = ['description', 'status']
        widgets = {
            'description': forms.TextInput(attrs={'placeholder': _("Ex: Conferência de Entrada"), 'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
        }

class PropertyChecklistItemForm(forms.ModelForm):
    class Meta:
        model = PropertyChecklistItem
        fields = ['description', 'default_quantity', 'default_status', 'evaluation_type', 'photo_required']
        widgets = {
            'description': forms.TextInput(attrs={'placeholder': _("Ex: Toalhas de Banho"), 'class': 'form-control'}),
            'default_quantity': forms.NumberInput(attrs={'min': 0, 'class': 'form-control'}),
            'default_status': forms.Select(attrs={'class': 'form-select'}),
            'evaluation_type': forms.Select(attrs={'class': 'form-select'}),
            'photo_required': forms.CheckboxInput(attrs={'class': 'form-check-input', 'style': 'width: 20px !important; height: 20px !important; flex-shrink: 0; cursor: pointer;'}),
        }


