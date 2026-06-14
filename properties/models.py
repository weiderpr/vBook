from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
import uuid
import os
from PIL import Image
from io import BytesIO
from django.core.files.base import ContentFile

class Property(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='properties',
        verbose_name=_("Proprietário")
    )
    name = models.CharField(max_length=255, verbose_name=_("Nome da propriedade"))
    description = models.TextField(blank=True, null=True, verbose_name=_("Descrição da propriedade"))
    condo_phone = models.CharField(max_length=20, blank=True, null=True, verbose_name=_("Telefone do Condomínio"))
    condo = models.ForeignKey(
        'administration.Condo', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='properties',
        verbose_name=_("Condomínio")
    )
    
    # Address structured fields
    address_street = models.CharField(max_length=255, blank=True, null=True, verbose_name=_("Rua"))
    address_number = models.CharField(max_length=20, blank=True, null=True, verbose_name=_("Número"))
    address_neighborhood = models.CharField(max_length=100, blank=True, null=True, verbose_name=_("Bairro"))
    address_complement = models.CharField(max_length=255, blank=True, null=True, verbose_name=_("Complemento"))
    address_city = models.CharField(max_length=100, blank=True, null=True, verbose_name=_("Cidade"))
    address_state = models.CharField(max_length=100, blank=True, null=True, verbose_name=_("Estado"))
    
    acquisition_date = models.DateField(blank=True, null=True, verbose_name=_("Data da aquisição"))
    acquisition_value = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        blank=True,
        null=True,
        verbose_name=_("Valor da aquisição")
    )
    image = models.ImageField(
        upload_to='properties/', 
        null=True, 
        blank=True, 
        verbose_name=_("Foto de Capa")
    )
    signature = models.ImageField(
        upload_to='property_signatures/',
        null=True,
        blank=True,
        verbose_name=_("Assinatura do Proprietário")
    )
    
    reservation_instructions = models.TextField(blank=True, null=True, verbose_name=_("Instruções de Reserva"))
    authorization_template = models.TextField(blank=True, null=True, verbose_name=_("Modelo de Autorização"))
    share_client_phone = models.BooleanField(
        default=False, 
        verbose_name=_("Enviar telefone do cliente para o prestador em caso de serviço")
    )
    default_checkin_time = models.TimeField(blank=True, null=True, verbose_name=_("Horário padrão de check-in"))
    default_checkout_time = models.TimeField(blank=True, null=True, verbose_name=_("Horário padrão de check-out"))
    color = models.CharField(max_length=7, default='#3b82f6', verbose_name=_("Cor no Calendário"))
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def display_name(self):
        try:
            if hasattr(self, 'portaria_custom') and self.portaria_custom and self.portaria_custom.nome_portaria:
                return self.portaria_custom.nome_portaria
        except Exception:
            pass
        return self.name

    @property
    def display_complement(self):
        try:
            if hasattr(self, 'portaria_custom') and self.portaria_custom:
                parts = []
                if self.address_complement:
                    parts.append(self.address_complement)
                if self.portaria_custom.bloco:
                    parts.append(self.portaria_custom.bloco)
                if parts:
                    return " - ".join(parts)
        except Exception:
            pass
        return self.address_complement or ""

    @property
    def display_owner_name(self):
        try:
            if hasattr(self, 'portaria_custom') and self.portaria_custom and self.portaria_custom.nome_proprietario:
                return self.portaria_custom.nome_proprietario
        except Exception:
            pass
        return self.user.full_name if self.user else ""

    class Meta:
        verbose_name = _("Propriedade")
        verbose_name_plural = _("Propriedades")
        ordering = ['-created_at']

    def __str__(self):
        return self.name

class PortariaCustomProperty(models.Model):
    property = models.OneToOneField(
        Property,
        on_delete=models.CASCADE,
        related_name='portaria_custom',
        verbose_name=_("Propriedade")
    )
    nome_portaria = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name=_("Nome da Portaria")
    )
    bloco = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name=_("Bloco")
    )
    nome_proprietario = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name=_("Nome do Proprietário (Portaria)")
    )
    telefone_proprietario = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name=_("Telefone do Proprietário")
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Customização da Portaria")
        verbose_name_plural = _("Customizações da Portaria")

    def __str__(self):
        return f"Portaria Custom - {self.property.name}"

class PropertyCost(models.Model):
    FREQUENCY_CHOICES = [
        ('daily', _('Diário')),
        ('monthly', _('Mensal')),
        ('yearly', _('Anual')),
        ('per_booking', _('Por reserva')),
        ('one_time', _('Único')),
    ]
    
    AMOUNT_TYPE_CHOICES = [
        ('fixed', _('Valor Fixo (R$)')),
        ('percentage', _('Percentual (%)')),
    ]

    RECIPIENT_CHOICES = [
        ('none', _('Nenhum / Próprio')),
        ('platform', _('Plataforma (Booking/Airbnb/etc)')),
        ('broker', _('Corretor / Terceiro')),
        ('provider', _('Prestador')),
        ('other', _('Outro')),
    ]
    
    MONTH_CHOICES = [
        (1, _('Janeiro')), (2, _('Fevereiro')), (3, _('Março')), (4, _('Abril')),
        (5, _('Maio')), (6, _('Junho')), (7, _('Julho')), (8, _('Agosto')),
        (9, _('Setembro')), (10, _('Outubro')), (11, _('Novembro')), (12, _('Dezembro')),
    ]

    property = models.ForeignKey(
        Property, 
        on_delete=models.CASCADE, 
        related_name='costs',
        verbose_name=_("Propriedade")
    )
    name = models.CharField(max_length=255, verbose_name=_("Nome do custo"))
    amount = models.DecimalField(max_digits=12, decimal_places=2, verbose_name=_("Valor"))
    amount_type = models.CharField(
        max_length=20, 
        choices=AMOUNT_TYPE_CHOICES, 
        default='fixed',
        verbose_name=_("Tipo de Valor")
    )
    frequency = models.CharField(
        max_length=20, 
        choices=FREQUENCY_CHOICES, 
        default='monthly',
        verbose_name=_("Frequência")
    )
    month = models.IntegerField(
        choices=MONTH_CHOICES,
        null=True,
        blank=True,
        verbose_name=_("Mês")
    )
    year = models.IntegerField(
        null=True,
        blank=True,
        verbose_name=_("Ano")
    )
    payment_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("Data do Pagamento")
    )
    recipient = models.CharField(
        max_length=20, 
        choices=RECIPIENT_CHOICES, 
        default='none',
        verbose_name=_("Beneficiário / Destinatário")
    )
    provider = models.ForeignKey(
        'ServiceProvider',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='property_costs',
        verbose_name=_("Prestador Associado")
    )
    description = models.TextField(blank=True, null=True, verbose_name=_("Descrição"))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def get_period_display(self):
        if self.frequency == 'monthly' and self.month and self.year:
            return f"{self.get_month_display()} {self.year:d}"
        elif self.frequency == 'yearly' and self.year:
            return f"{self.year:d}"
        return ""

    class Meta:
        verbose_name = _("Custo da Propriedade")
        verbose_name_plural = _("Custos da Propriedade")
        ordering = ['name']

    def __str__(self):
        return f"{self.name} - {self.property.name}"

class FinancialHistory(models.Model):
    property = models.ForeignKey(
        Property, 
        on_delete=models.CASCADE, 
        related_name='financial_histories',
        verbose_name=_("Propriedade")
    )
    month = models.IntegerField(verbose_name=_("Mês"))
    year = models.IntegerField(verbose_name=_("Ano"))
    gross_value = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name=_("Valor Bruto"))
    costs = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name=_("Custos"))
    net_value = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name=_("Valor Líquido"))
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Histórico Financeiro")
        verbose_name_plural = _("Históricos Financeiros")
        unique_together = ['property', 'month', 'year']
        ordering = ['-year', '-month']

    def __str__(self):
        return f"{self.property.name} - {self.month}/{self.year}"

class Service(models.Model):
    name = models.CharField(max_length=100, verbose_name=_("Nome do Serviço"), unique=True)
    
    class Meta:
        verbose_name = _("Serviço")
        verbose_name_plural = _("Serviços")
        ordering = ['name']

    def __str__(self):
        return self.name

class ServiceProvider(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='service_providers', 
        verbose_name=_("Usuário"),
        null=True,
        blank=True
    )
    condo = models.ForeignKey(
        'administration.Condo',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='manual_service_providers',
        verbose_name=_("Condomínio")
    )
    name = models.CharField(max_length=255, verbose_name=_("Nome Completo"))
    cpf = models.CharField(max_length=14, blank=True, null=True, verbose_name=_("CPF"))
    phone = models.CharField(max_length=20, verbose_name=_("Telefone"))
    services = models.ManyToManyField(
        Service, 
        blank=True, verbose_name=_("Serviços Prestados")
    )
    access_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    is_active = models.BooleanField(default=True, verbose_name=_("Ativo"))
    photo = models.ImageField(upload_to="providers/", blank=True, null=True, verbose_name=_("Foto do Prestador"))
    
    THEME_CHOICES = [
        ('dark', _('Escuro')),
        ('light', _('Claro')),
    ]
    theme = models.CharField(max_length=10, choices=THEME_CHOICES, default='dark', verbose_name=_("Tema"))
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Prestador de Serviço")
        verbose_name_plural = _("Prestadores de Serviço")
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def average_rating(self):
        avg = self.evaluations.aggregate(models.Avg('rating'))['rating__avg']
        return round(float(avg), 1) if avg else 0

    @property
    def evaluation_count(self):
        return self.evaluations.count()

    @property
    def financial_balance(self):
        """
        Calculates balance: Credits (Payments) - Debits (Reservation Costs + Maintenance Execution).
        Negative balance means the user owes the provider.
        """
        from reservations.models import ReservationCost
        from maintenance.models import Maintenance
        from django.db.models import Sum
        
        # Debits: Completed Reservation Services
        res_debits = ReservationCost.objects.filter(
            provider=self, 
            is_completed=True
        ).aggregate(total=Sum('value'))['total'] or 0
        
        # Debits: Finished or In Progress Maintenances
        maint_debits = Maintenance.objects.filter(
            provider=self, 
            status__in=['in_progress', 'finished']
        ).aggregate(total=Sum('execution_value'))['total'] or 0
        
        # Debits: Monthly/Fixed Property Costs (Excluding per_booking to avoid double counting)
        prop_debits = self.property_costs.exclude(
            frequency='per_booking'
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        # Credits: Payments made to provider
        credits = self.payments.aggregate(total=Sum('value'))['total'] or 0
        
        return credits - (res_debits + maint_debits + prop_debits)

class ProviderPayment(models.Model):
    provider = models.ForeignKey(
        ServiceProvider, 
        on_delete=models.CASCADE, 
        related_name='payments', 
        verbose_name=_("Prestador")
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        verbose_name=_("Usuário")
    )
    date = models.DateField(verbose_name=_("Data"))
    value = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        verbose_name=_("Valor")
    )
    observations = models.TextField(blank=True, null=True, verbose_name=_("Observações"))
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Pagamento ao Prestador")
        verbose_name_plural = _("Pagamentos aos Prestadores")
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"Pagamento: R$ {self.value} para {self.provider.name} em {self.date}"

class PropertyDocument(models.Model):
    property = models.ForeignKey(
        Property, 
        on_delete=models.CASCADE, 
        related_name='documents',
        verbose_name=_("Propriedade")
    )
    name = models.CharField(max_length=255, verbose_name=_("Nome do Documento"))
    document_date = models.DateField(verbose_name=_("Data do Documento"))
    description = models.TextField(blank=True, null=True, verbose_name=_("Descrição"))
    file = models.FileField(
        upload_to='property_documents/',
        verbose_name=_("Arquivo")
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Documento da Propriedade")
        verbose_name_plural = _("Documentos da Propriedade")
        ordering = ['-document_date', '-created_at']

    def __str__(self):
        return f"{self.name} - {self.property.name}"

    def save(self, *args, **kwargs):
        if self.file:
            extension = os.path.splitext(self.file.name)[1].lower()
            if extension in ['.jpg', '.jpeg', '.png', '.webp']:
                try:
                    img = Image.open(self.file)
                    
                    # Convert to RGB if necessary
                    if img.mode in ("RGBA", "P"):
                        img = img.convert("RGB")
                    
                    # Resize if too large
                    max_size = 1920
                    if img.width > max_size or img.height > max_size:
                        img.thumbnail((max_size, max_size), Image.LANCZOS)
                    
                    # Compress
                    output = BytesIO()
                    img.save(output, format='JPEG', quality=70, optimize=True)
                    output.seek(0)
                    
                    # Update filename to .jpg
                    name_without_ext = os.path.splitext(os.path.basename(self.file.name))[0]
                    new_name = f"{name_without_ext}.jpg"
                    self.file.save(new_name, ContentFile(output.read()), save=False)
                except Exception as e:
                    print(f"Error compressing image: {e}")
        
        super().save(*args, **kwargs)


class PropertySpecification(models.Model):
    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name='specifications',
        verbose_name=_("Propriedade")
    )
    description = models.CharField(max_length=255, verbose_name=_("Descrição"))
    brand = models.CharField(max_length=255, verbose_name=_("Marca"))
    model = models.CharField(max_length=255, verbose_name=_("Modelo"))
    dimensions = models.CharField(max_length=255, verbose_name=_("Dimensões"))
    purchase_location = models.CharField(max_length=255, blank=True, null=True, verbose_name=_("Local da compra"))
    purchase_date = models.DateField(blank=True, null=True, verbose_name=_("Data da compra"))
    purchase_value = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name=_("Valor da compra")
    )
    product_link = models.URLField(blank=True, null=True, verbose_name=_("Link do produto"))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Especificação da Propriedade")
        verbose_name_plural = _("Especificações da Propriedade")
        ordering = ['description']

    def __str__(self):
        return f"{self.description} - {self.property.name}"


class PropertySpecificationPhoto(models.Model):
    specification = models.ForeignKey(
        PropertySpecification,
        on_delete=models.CASCADE,
        related_name='photos',
        verbose_name=_("Especificação")
    )
    image = models.ImageField(
        upload_to='property_specifications/',
        verbose_name=_("Imagem")
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Foto da Especificação")
        verbose_name_plural = _("Fotos da Especificação")

    def save(self, *args, **kwargs):
        if self.image:
            try:
                img = Image.open(self.image)
                # Convert to RGB if necessary
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")

                # Target file size <= 100KB (102400 bytes)
                quality = 85
                max_dim = 1200

                while True:
                    # Resize if too large
                    if img.width > max_dim or img.height > max_dim:
                        img_temp = img.copy()
                        img_temp.thumbnail((max_dim, max_dim), Image.LANCZOS)
                    else:
                        img_temp = img

                    output = BytesIO()
                    img_temp.save(output, format='JPEG', quality=quality, optimize=True)
                    size = output.tell()

                    # Stop if size is <= 100KB, or quality / dimension is minimized
                    if size <= 102400 or quality <= 20 or max_dim <= 400:
                        output.seek(0)
                        name_without_ext = os.path.splitext(os.path.basename(self.image.name))[0]
                        new_name = f"{name_without_ext}.jpg"
                        self.image.save(new_name, ContentFile(output.read()), save=False)
                        break

                    # Reduce quality or dimension
                    if quality > 40:
                        quality -= 10
                    else:
                        max_dim -= 200
                        quality = 60
            except Exception as e:
                print(f"Error compressing image: {e}")

        super().save(*args, **kwargs)


class PropertyChecklist(models.Model):
    STATUS_CHOICES = [
        ('active', _('Ativo')),
        ('inactive', _('Inativo')),
    ]

    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name='checklists',
        verbose_name=_("Propriedade")
    )
    description = models.CharField(max_length=255, verbose_name=_("Descrição"))
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='active',
        verbose_name=_("Status")
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Checklist da Propriedade")
        verbose_name_plural = _("Checklists da Propriedade")
        ordering = ['description']

    def __str__(self):
        return f"{self.description} - {self.property.name}"


class PropertyChecklistItem(models.Model):
    STATUS_CHOICES = [
        ('bad', _('Ruim')),
        ('regular', _('Regular')),
        ('good', _('Bom')),
    ]

    EVALUATION_CHOICES = [
        ('quantity', _('Apenas Quantidade')),
        ('quality', _('Apenas Qualidade')),
        ('both', _('Quantidade e Qualidade')),
    ]

    checklist = models.ForeignKey(
        PropertyChecklist,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name=_("Checklist")
    )
    description = models.CharField(max_length=255, verbose_name=_("Descrição"))
    default_quantity = models.IntegerField(default=1, verbose_name=_("Quantidade Padrão"))
    default_status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='good',
        verbose_name=_("Estado Padrão")
    )
    evaluation_type = models.CharField(
        max_length=20,
        choices=EVALUATION_CHOICES,
        default='both',
        verbose_name=_("Tipo de Avaliação")
    )
    photo_required = models.BooleanField(
        default=False,
        verbose_name=_("Registro fotográfico obrigatório?")
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Item do Checklist")
        verbose_name_plural = _("Itens do Checklist")
        ordering = ['description']

    def __str__(self):
        return f"{self.description} ({self.checklist.description})"


class PropertyChecklistResponse(models.Model):
    checklist = models.ForeignKey(
        'PropertyChecklist',
        on_delete=models.CASCADE,
        related_name='responses',
        verbose_name=_("Checklist")
    )
    reservation = models.ForeignKey(
        'reservations.Reservation',
        on_delete=models.CASCADE,
        related_name='checklist_responses',
        verbose_name=_("Reserva")
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='checklist_responses',
        verbose_name=_("Usuário")
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Data da Resposta"))

    class Meta:
        verbose_name = _("Resposta do Checklist")
        verbose_name_plural = _("Respostas dos Checklists")
        unique_together = ['reservation', 'checklist']

    def __str__(self):
        return f"Resposta de {self.checklist.description} para Reserva #{self.reservation.id}"

    @property
    def has_attention_items(self):
        return any(resp.is_below_default for resp in self.item_responses.all())


class PropertyChecklistItemResponse(models.Model):
    response = models.ForeignKey(
        PropertyChecklistResponse,
        on_delete=models.CASCADE,
        related_name='item_responses',
        verbose_name=_("Resposta do Checklist")
    )
    item = models.ForeignKey(
        'PropertyChecklistItem',
        on_delete=models.CASCADE,
        related_name='responses',
        verbose_name=_("Item do Checklist")
    )
    quantity = models.IntegerField(null=True, blank=True, verbose_name=_("Quantidade"))
    quality = models.CharField(
        max_length=10,
        choices=PropertyChecklistItem.STATUS_CHOICES,
        null=True,
        blank=True,
        verbose_name=_("Estado/Qualidade")
    )
    photo = models.ImageField(
        upload_to='checklist_responses/',
        null=True,
        blank=True,
        verbose_name=_("Foto / Registro Fotográfico")
    )

    class Meta:
        verbose_name = _("Resposta de Item do Checklist")
        verbose_name_plural = _("Respostas dos Itens do Checklist")

    def __str__(self):
        return f"{self.item.description}: Qtd={self.quantity}, Qualidade={self.quality}"

    @property
    def is_below_default(self):
        # Quantity comparison
        if self.item.evaluation_type in ('quantity', 'both'):
            if self.quantity is not None and self.quantity < self.item.default_quantity:
                return True
        # Quality comparison
        if self.item.evaluation_type in ('quality', 'both'):
            status_map = {'bad': 1, 'regular': 2, 'good': 3}
            resp_val = status_map.get(self.quality)
            def_val = status_map.get(self.item.default_status)
            if resp_val is not None and def_val is not None and resp_val < def_val:
                return True
        return False

    def save(self, *args, **kwargs):
        if self.photo:
            try:
                # Validate image file extension
                ext = os.path.splitext(self.photo.name)[1].lower()
                if ext not in ['.png', '.jpg', '.jpeg', '.webp']:
                    raise ValueError("Format file not supported.")

                img = Image.open(self.photo)
                # Convert to RGB if necessary
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")

                # Target file size <= 100KB (102400 bytes)
                quality = 85
                max_dim = 1200

                while True:
                    # Resize if too large
                    if img.width > max_dim or img.height > max_dim:
                        img_temp = img.copy()
                        img_temp.thumbnail((max_dim, max_dim), Image.LANCZOS)
                    else:
                        img_temp = img

                    output = BytesIO()
                    img_temp.save(output, format='JPEG', quality=quality, optimize=True)
                    size = output.tell()

                    # Stop if size is <= 100KB, or quality / dimension is minimized
                    if size <= 102400 or quality <= 20 or max_dim <= 400:
                        output.seek(0)
                        new_name = f"{uuid.uuid4().hex}.jpg"
                        self.photo.save(new_name, ContentFile(output.read()), save=False)
                        break

                    # Reduce quality or dimension
                    if quality > 40:
                        quality -= 10
                    else:
                        max_dim -= 200
                        quality = 60
            except Exception as e:
                print(f"Error compressing image: {e}")

        super().save(*args, **kwargs)



class ProviderNonConformity(models.Model):
    provider = models.ForeignKey(
        ServiceProvider,
        on_delete=models.CASCADE,
        related_name='non_conformities',
        verbose_name=_("Prestador"),
        null=True,
        blank=True
    )
    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name='non_conformities',
        verbose_name=_("Propriedade")
    )
    description = models.TextField(verbose_name=_("Relato da Inconformidade"))
    photo = models.ImageField(
        upload_to='non_conformities/',
        null=True,
        blank=True,
        verbose_name=_("Registro Fotográfico")
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Registrado em"))
    is_read = models.BooleanField(default=False, verbose_name=_("Lido / Verificado"))

    class Meta:
        verbose_name = _("Inconformidade do Prestador")
        verbose_name_plural = _("Inconformidades dos Prestadores")
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.property.name} - {self.provider.name} - {self.created_at.strftime('%d/%m/%Y')}"

    def save(self, *args, **kwargs):
        if self.photo:
            try:
                # Security: validate image file extension
                ext = os.path.splitext(self.photo.name)[1].lower()
                if ext not in ['.png', '.jpg', '.jpeg', '.webp']:
                    raise ValueError("Format file not supported.")

                img = Image.open(self.photo)
                # Convert to RGB if necessary
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")

                # Target file size <= 100KB (102400 bytes)
                quality = 85
                max_dim = 1200

                while True:
                    # Resize if too large
                    if img.width > max_dim or img.height > max_dim:
                        img_temp = img.copy()
                        img_temp.thumbnail((max_dim, max_dim), Image.LANCZOS)
                    else:
                        img_temp = img

                    output = BytesIO()
                    img_temp.save(output, format='JPEG', quality=quality, optimize=True)
                    size = output.tell()

                    # Stop if size is <= 100KB, or quality / dimension is minimized
                    if size <= 102400 or quality <= 20 or max_dim <= 400:
                        output.seek(0)
                        # Security: use unique UUID for filename
                        new_name = f"{uuid.uuid4().hex}.jpg"
                        self.photo.save(new_name, ContentFile(output.read()), save=False)
                        break

                    # Reduce quality or dimension
                    if quality > 40:
                        quality -= 10
                    else:
                        max_dim -= 200
                        quality = 60
            except Exception as e:
                # TODO(security): handle exception gracefully without exposing system internals to front users
                print(f"Error compressing image: {e}")

        super().save(*args, **kwargs)

