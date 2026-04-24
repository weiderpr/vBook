from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
import uuid

class Property(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='properties',
        verbose_name=_("Proprietário")
    )
    name = models.CharField(max_length=255, verbose_name=_("Nome da propriedade"))
    description = models.TextField(verbose_name=_("Descrição da propriedade"))
    condo_phone = models.CharField(max_length=20, blank=True, null=True, verbose_name=_("Telefone do Condomínio"))
    
    # Address structured fields
    address_street = models.CharField(max_length=255, verbose_name=_("Rua"))
    address_number = models.CharField(max_length=20, verbose_name=_("Número"))
    address_complement = models.CharField(max_length=255, blank=True, null=True, verbose_name=_("Complemento"))
    address_city = models.CharField(max_length=100, verbose_name=_("Cidade"))
    address_state = models.CharField(max_length=100, verbose_name=_("Estado"))
    
    acquisition_date = models.DateField(verbose_name=_("Data da aquisição"))
    acquisition_value = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
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

    class Meta:
        verbose_name = _("Propriedade")
        verbose_name_plural = _("Propriedades")
        ordering = ['-created_at']

    def __str__(self):
        return self.name

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
        verbose_name=_("Usuário")
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
