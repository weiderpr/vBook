import builtins
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from properties.models import Property

class PortariaCheckinManual(models.Model):
    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name='manual_checkins',
        verbose_name=_("Unidade")
    )
    checkin_date = models.DateField(verbose_name=_("Data de Check-in"))
    checkout_date = models.DateField(verbose_name=_("Data de Check-out"))
    
    responsible_name = models.CharField(max_length=255, verbose_name=_("Nome do Responsável"))
    responsible_cpf = models.CharField(max_length=14, verbose_name=_("CPF do Responsável"))
    responsible_rg = models.CharField(max_length=20, verbose_name=_("RG do Responsável"))
    
    car_model = models.CharField(max_length=100, blank=True, null=True, verbose_name=_("Modelo do Veículo"))
    car_plate = models.CharField(max_length=10, blank=True, null=True, verbose_name=_("Placa do Veículo"))
    
    checkin_completed = models.BooleanField(default=True, verbose_name=_("Check-in Realizado"))
    checkout_completed = models.BooleanField(default=False, verbose_name=_("Check-out Realizado"))
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Criado em"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Atualizado em"))

    @builtins.property
    def client(self):
        class MockComplement:
            def __init__(self, car_model, car_plate):
                self.car_model = car_model
                self.car_plate = car_plate
        class MockClient:
            def __init__(self, car_model, car_plate):
                self.complement = MockComplement(car_model, car_plate)
        return MockClient(self.car_model, self.car_plate)

    class Meta:
        db_table = 'portaria_checkin_manual'
        verbose_name = _("Check-in Manual")
        verbose_name_plural = _("Check-ins Manuais")
        ordering = ['-checkin_date']

    def __str__(self):
        return f"{self.responsible_name} - {self.property.name} ({self.checkin_date} a {self.checkout_date})"


class PortariaCheckinManualGuest(models.Model):
    checkin_manual = models.ForeignKey(
        PortariaCheckinManual,
        on_delete=models.CASCADE,
        related_name='guests',
        verbose_name=_("Check-in Manual")
    )
    name = models.CharField(max_length=255, verbose_name=_("Nome Completo"))
    document = models.CharField(max_length=50, verbose_name=_("Documento"))
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Criado em"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Atualizado em"))

    class Meta:
        db_table = 'portaria_checkin_manual_hospede'
        verbose_name = _("Hóspede de Check-in Manual")
        verbose_name_plural = _("Hóspedes de Check-in Manual")

    def __str__(self):
        return f"{self.name} - {self.checkin_manual}"


class ServiceProviderAccessLog(models.Model):
    condo = models.ForeignKey(
        'administration.Condo',
        on_delete=models.CASCADE,
        related_name='provider_access_logs',
        verbose_name=_("Condomínio")
    )
    provider = models.ForeignKey(
        'properties.ServiceProvider',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='access_logs',
        verbose_name=_("Prestador")
    )
    
    # Denormalized fields for audit trail
    provider_name = models.CharField(max_length=255, verbose_name=_("Nome do Prestador"))
    provider_cpf = models.CharField(max_length=14, blank=True, null=True, verbose_name=_("CPF do Prestador"))
    provider_phone = models.CharField(max_length=20, blank=True, null=True, verbose_name=_("Telefone do Prestador"))
    
    checkin_time = models.DateTimeField(verbose_name=_("Hora de Entrada"))
    checkout_time = models.DateTimeField(verbose_name=_("Hora de Saída"), null=True, blank=True)
    
    reason = models.CharField(max_length=255, verbose_name=_("Motivo do Acesso"))
    properties = models.ManyToManyField(
        'properties.Property',
        blank=True,
        related_name='provider_access_logs',
        verbose_name=_("Unidades Visitadas")
    )
    
    car_model = models.CharField(max_length=100, blank=True, null=True, verbose_name=_("Modelo do Veículo"))
    car_plate = models.CharField(max_length=10, blank=True, null=True, verbose_name=_("Placa do Veículo"))
    
    operator_entry = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='provider_entries',
        verbose_name=_("Operador de Entrada")
    )
    operator_exit = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='provider_exits',
        verbose_name=_("Operador de Saída")
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'portaria_prestador_acesso'
        verbose_name = _("Acesso de Prestador")
        verbose_name_plural = _("Acessos de Prestadores")
        ordering = ['-checkin_time']

    def __str__(self):
        return f"{self.provider_name} - {self.condo.name} ({self.checkin_time})"


class PortariaCheckinVisitor(models.Model):
    reservation = models.ForeignKey(
        'reservations.Reservation',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='visitors',
        verbose_name=_("Reserva")
    )
    checkin_manual = models.ForeignKey(
        PortariaCheckinManual,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='visitors',
        verbose_name=_("Check-in Manual")
    )
    name = models.CharField(max_length=255, verbose_name=_("Nome Completo"))
    document = models.CharField(max_length=50, verbose_name=_("Documento"))
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Criado em"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Atualizado em"))

    class Meta:
        db_table = 'portaria_checkin_visitante'
        verbose_name = _("Visitante do Check-in")
        verbose_name_plural = _("Visitantes do Check-in")

    def __str__(self):
        return f"{self.name} - {self.document}"


class Notice(models.Model):
    condo = models.ForeignKey(
        'administration.Condo',
        on_delete=models.CASCADE,
        related_name='notices',
        verbose_name=_("Condomínio")
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='created_notices',
        verbose_name=_("Criado por")
    )
    message = models.TextField(verbose_name=_("Mensagem"))
    is_active = models.BooleanField(default=True, verbose_name=_("Ativo"))
    valid_until = models.DateField(verbose_name=_("Ativo até"), null=True, blank=True)
    all_owners = models.BooleanField(default=True, verbose_name=_("Para todos proprietários"))
    target_owners = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name='received_notices',
        verbose_name=_("Proprietários destino")
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Criado em"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Atualizado em"))

    @property
    def is_currently_active(self):
        if not self.is_active:
            return False
        if self.valid_until and self.valid_until < timezone.localtime(timezone.now()).date():
            return False
        return True

    class Meta:
        db_table = 'portaria_aviso'
        verbose_name = _("Aviso")
        verbose_name_plural = _("Avisos")
        ordering = ['-created_at']

    def __str__(self):
        return f"Aviso #{self.id} - {self.condo.name} ({self.created_at.strftime('%d/%m/%Y') if self.created_at else ''})"
