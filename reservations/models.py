from django.db import models
from django.core.validators import MinValueValidator
from django.utils.translation import gettext_lazy as _
from properties.models import Property

class Reservation(models.Model):
    property = models.ForeignKey(
        Property, 
        on_delete=models.CASCADE, 
        related_name='reservations',
        verbose_name=_("Propriedade")
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
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Reserva")
        verbose_name_plural = _("Reservas")
        ordering = ['-start_date']

    def __str__(self):
        return f"{self.client_name} - {self.property.name} ({self.start_date})"

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
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Custo da Reserva")
        verbose_name_plural = _("Custos da Reserva")

    def __str__(self):
        return f"{self.description}: {self.value} ({self.reservation})"
