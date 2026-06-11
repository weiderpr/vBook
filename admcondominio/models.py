import builtins
from django.db import models
from django.utils.translation import gettext_lazy as _
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
