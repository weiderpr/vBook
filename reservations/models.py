import uuid
from django.db import models
from django.core.validators import MinValueValidator
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from properties.models import Property

_property = property

class Client(models.Model):
    name = models.CharField(max_length=255, verbose_name=_("Nome Completo"))
    phone = models.CharField(max_length=20, verbose_name=_("Telefone"))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Cliente")
        verbose_name_plural = _("Clientes")
        ordering = ['name']

    def __str__(self):
        return self.name

class ClientComplement(models.Model):
    STATE_CHOICES = [
        ('AC', 'Acre'), ('AL', 'Alagoas'), ('AP', 'Amapá'), ('AM', 'Amazonas'),
        ('BA', 'Bahia'), ('CE', 'Ceará'), ('DF', 'Distrito Federal'), ('ES', 'Espírito Santo'),
        ('GO', 'Goiás'), ('MA', 'Maranhão'), ('MT', 'Mato Grosso'), ('MS', 'Mato Grosso do Sul'),
        ('MG', 'Minas Gerais'), ('PA', 'Pará'), ('PB', 'Paraíba'), ('PR', 'Paraná'),
        ('PE', 'Pernambuco'), ('PI', 'Piauí'), ('RJ', 'Rio de Janeiro'), ('RN', 'Rio Grande do Norte'),
        ('RS', 'Rio Grande do Sul'), ('RO', 'Rondônia'), ('RR', 'Roraima'), ('SC', 'Santa Catarina'),
        ('SP', 'São Paulo'), ('SE', 'Sergipe'), ('TO', 'Tocantins'),
    ]

    client = models.OneToOneField(
        Client, 
        on_delete=models.CASCADE, 
        related_name='complement',
        verbose_name=_("Cliente")
    )
    street = models.CharField(max_length=255, verbose_name=_("Rua"))
    number = models.CharField(max_length=20, verbose_name=_("Número"))
    complement = models.CharField(max_length=255, blank=True, null=True, verbose_name=_("Complemento"))
    neighborhood = models.CharField(max_length=100, verbose_name=_("Bairro"))
    city = models.CharField(max_length=100, verbose_name=_("Cidade"))
    state = models.CharField(
        max_length=2, 
        choices=STATE_CHOICES, 
        default='SP',
        verbose_name=_("Estado")
    )
    cpf = models.CharField(max_length=14, verbose_name=_("CPF"))
    rg = models.CharField(max_length=20, verbose_name=_("RG"))
    
    car_model = models.CharField(max_length=100, blank=True, null=True, verbose_name=_("Modelo do Carro"))
    car_plate = models.CharField(max_length=10, blank=True, null=True, verbose_name=_("Placa do Carro"))
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Complemento de Cliente")
        verbose_name_plural = _("Complementos de Cliente")

    def __str__(self):
        return f"Complemento: {self.client.name}"

class Reservation(models.Model):
    property = models.ForeignKey(
        Property, 
        on_delete=models.CASCADE, 
        related_name='reservations',
        verbose_name=_("Propriedade")
    )
    client = models.ForeignKey(
        Client,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reservations',
        verbose_name=_("Cliente (Registro)")
    )
    start_date = models.DateField(verbose_name=_("Data inicial"))
    end_date = models.DateField(verbose_name=_("Data final"))
    client_name = models.CharField(max_length=255, verbose_name=_("Nome do cliente"))
    client_phone = models.CharField(max_length=20, verbose_name=_("Telefone"))
    total_value = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        verbose_name=_("Valor total")
    )
    guests_count = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        verbose_name=_("Quantidade de hóspedes")
    )
    notes = models.TextField(blank=True, null=True, verbose_name=_("Observações"))
    
    checkin_token = models.UUIDField(
        default=uuid.uuid4, 
        editable=False, 
        unique=True, 
        null=True, 
        blank=True,
        verbose_name=_("Token de Check-in")
    )
    
    welcome_message_sent = models.BooleanField(
        default=False, 
        verbose_name=_("Boas-vindas enviada")
    )
    
    checkin_completed = models.BooleanField(
        default=False,
        verbose_name=_("Check-in Realizado")
    )
    
    authorization_sent = models.BooleanField(
        default=False,
        verbose_name=_("Autorização Enviada")
    )
    is_cancelled = models.BooleanField(
        default=False,
        verbose_name=_("Reserva Cancelada")
    )
    
    authorization_sent_at = models.DateTimeField(
        null=True, 
        blank=True,
        verbose_name=_("Data de Envio da Autorização")
    )

    checkin_time = models.TimeField(null=True, blank=True, verbose_name=_("Horário de check-in"))
    checkout_time = models.TimeField(null=True, blank=True, verbose_name=_("Horário de check-out"))
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Reserva")
        verbose_name_plural = _("Reservas")
        ordering = ['-start_date']

    def __str__(self):
        return f"{self.client_name} ({self.start_date} - {self.end_date})"

    @_property
    def first_name(self):
        if self.client_name:
            return self.client_name.split()[0]
        return ""

    def get_status(self):
        from django.utils import timezone
        import datetime
        
        if self.is_cancelled:
            return 'cancelled'
            
        now = timezone.now()
        
        # Fallback to property defaults or fixed times if everything is missing
        checkin_t = self.checkin_time or self.property.default_checkin_time or datetime.time(14, 0)
        checkout_t = self.checkout_time or self.property.default_checkout_time or datetime.time(11, 0)
        
        # Combine date and time
        start_dt = datetime.datetime.combine(self.start_date, checkin_t)
        end_dt = datetime.datetime.combine(self.end_date, checkout_t)
        
        if timezone.is_aware(now):
            tz = timezone.get_current_timezone()
            start_dt = timezone.make_aware(start_dt, tz)
            end_dt = timezone.make_aware(end_dt, tz)
            
        if now < start_dt:
            return 'upcoming'
        elif now > end_dt:
            return 'past'
        else:
            return 'active'

    @_property
    def total_paid(self):
        from django.db.models import Sum
        return self.payments.aggregate(total=Sum('value'))['total'] or 0

    @_property
    def remaining_balance(self):
        return self.total_value - self.total_paid

    def get_checkin_url(self):
        """Generates the absolute check-in URL"""
        return f"https://verticesistemas.tech/book/checkin/{self.checkin_token}/"

class ReservationCost(models.Model):
    reservation = models.ForeignKey(
        Reservation, 
        on_delete=models.CASCADE, 
        related_name='costs',
        verbose_name=_("Reserva")
    )
    description = models.CharField(max_length=255, verbose_name=_("Descrição"))
    value = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        verbose_name=_("Valor")
    )
    property_cost = models.ForeignKey(
        'properties.PropertyCost',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reservation_instances',
        verbose_name=_("Custo de Referência")
    )
    provider = models.ForeignKey(
        'properties.ServiceProvider',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reservation_costs',
        verbose_name=_("Prestador")
    )
    
    is_completed = models.BooleanField(default=False, verbose_name=_("Realizado"))
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Realizado em"))
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Custo da Reserva")
        verbose_name_plural = _("Custos da Reserva")

    def __str__(self):
        return f"{self.description}: {self.value} ({self.reservation})"

class Companion(models.Model):
    reservation = models.ForeignKey(
        Reservation,
        on_delete=models.CASCADE,
        related_name='companions',
        verbose_name=_("Reserva")
    )
    name = models.CharField(max_length=255, verbose_name=_("Nome"))
    rg = models.CharField(max_length=20, blank=True, null=True, verbose_name=_("RG"))
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Acompanhante")
        verbose_name_plural = _("Acompanhantes")

    def __str__(self):
        return f"{self.name} (Acompação de {self.reservation})"

class ReservationPayment(models.Model):
    reservation = models.ForeignKey(
        Reservation, 
        on_delete=models.CASCADE, 
        related_name='payments',
        verbose_name=_("Reserva")
    )
    description = models.CharField(max_length=255, verbose_name=_("Descrição"))
    value = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        verbose_name=_("Valor")
    )
    payment_date = models.DateField(verbose_name=_("Data do Pagamento"))
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Pagamento da Reserva")
        verbose_name_plural = _("Pagamentos da Reserva")
        ordering = ['payment_date']

    def __str__(self):
        return f"{self.description}: {self.value} ({self.reservation})"
